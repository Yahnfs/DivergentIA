"""Contas de usuário: cadastro, login (e-mail/senha ou Google), recuperação de senha.

Criar conta é OPCIONAL — o chat (POST /chat) funciona sem login. A conta existe para quem quiser
salvar/participar da pesquisa da extensão (os dados socioeconômicos só servem para isso, ver o
termo de consentimento em GET /auth/termo-lgpd).
"""
import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import TokenContaDB, UsuarioDB, get_db
from app.models.schemas import (
    AdminLoginRequest, CadastroRequest, LoginGoogleRequest, LoginRequest, RecuperarSenhaRequest,
    RedefinirSenhaRequest, UsuarioOut,
)
from app.services import auth_service
from app.services.email_sender import enviar_email

router = APIRouter(prefix="/auth", tags=["contas"])
log = logging.getLogger("divergentia.auth")

VERSAO_TERMO_LGPD = "2026-10-17"
VALIDADE_TOKEN = {"verificar_email": datetime.timedelta(days=3), "redefinir_senha": datetime.timedelta(hours=2)}


def _usuario_logado(request: Request, db: Session = Depends(get_db)) -> UsuarioDB:
    usuario_id = auth_service.usuario_id_da_sessao(request)
    usuario = db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first() if usuario_id else None
    if usuario is None:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    return usuario


def _criar_token(db: Session, usuario: UsuarioDB, tipo: str) -> str:
    bruto, hash_ = auth_service.gerar_token()
    db.add(TokenContaDB(
        usuario_id=usuario.id, token_hash=hash_, tipo=tipo,
        expira_em=datetime.datetime.utcnow() + VALIDADE_TOKEN[tipo],
    ))
    db.commit()
    return bruto


def _consumir_token(db: Session, token: str, tipo: str) -> UsuarioDB:
    registro = (
        db.query(TokenContaDB)
        .filter(TokenContaDB.token_hash == auth_service.hash_token(token), TokenContaDB.tipo == tipo)
        .first()
    )
    if (
        registro is None or registro.usado
        or registro.expira_em < datetime.datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Peça um novo.")
    registro.usado = True
    db.commit()
    return db.query(UsuarioDB).filter(UsuarioDB.id == registro.usuario_id).first()


@router.get("/opcoes")
def opcoes() -> dict:
    """Informa ao frontend se o login com Google e o captcha estão configurados neste servidor."""
    return {
        "google_client_id": settings.google_client_id if auth_service.google_configurado() else None,
        "recaptcha_site_key": settings.recaptcha_site_key if auth_service.captcha_configurado() else None,
    }


@router.get("/termo-lgpd")
def termo_lgpd() -> dict:
    return {"versao": VERSAO_TERMO_LGPD, "texto": TEXTO_TERMO_LGPD}


@router.post("/cadastro", response_model=UsuarioOut, status_code=201)
def cadastro(payload: CadastroRequest, response: Response, db: Session = Depends(get_db)) -> UsuarioDB:
    if not auth_service.verificar_captcha(payload.captcha_token):
        raise HTTPException(status_code=400, detail="Não foi possível confirmar o captcha. Tente de novo.")
    if db.query(UsuarioDB).filter(UsuarioDB.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="Já existe uma conta com este e-mail. Tente entrar ou recuperar a senha.")

    usuario = UsuarioDB(
        email=payload.email.lower(), senha_hash=auth_service.hash_senha(payload.senha),
        nome_completo=payload.nome_completo.strip(), ano_nascimento=payload.ano_nascimento,
        sexo=payload.sexo, etnia=payload.etnia, cpf_rg=payload.cpf_rg,
        estado=payload.estado, cidade=payload.cidade, endereco=payload.endereco,
        grau_escolaridade=payload.grau_escolaridade, integrantes_familia=payload.integrantes_familia,
        renda_faixa=payload.renda_faixa, renda_familiar_faixa=payload.renda_familiar_faixa,
        condicoes_acessibilidade=payload.condicoes_acessibilidade,
        consentimento_lgpd_em=datetime.datetime.utcnow(), consentimento_lgpd_versao=VERSAO_TERMO_LGPD,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    token = _criar_token(db, usuario, "verificar_email")
    link = f"{settings.app_base_url}/verificar-email.html?token={token}"
    enviar_email(
        usuario.email, "Confirme sua conta no DivergentIA",
        f"Olá, {usuario.nome_completo}!\n\nConfirme seu e-mail clicando no link abaixo (vale por 3 dias):\n{link}\n\n"
        "Se você não pediu esse cadastro, ignore esta mensagem.",
    )
    auth_service.definir_cookie_sessao(response, usuario.id)
    return usuario


@router.post("/login", response_model=UsuarioOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UsuarioDB:
    if not auth_service.verificar_captcha(payload.captcha_token):
        raise HTTPException(status_code=400, detail="Não foi possível confirmar o captcha. Tente de novo.")
    usuario = db.query(UsuarioDB).filter(UsuarioDB.email == payload.email.lower()).first()
    if usuario is None or not usuario.senha_hash or not auth_service.senha_confere(payload.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    auth_service.definir_cookie_sessao(response, usuario.id)
    return usuario


@router.post("/login/google", response_model=UsuarioOut)
def login_google(payload: LoginGoogleRequest, response: Response, db: Session = Depends(get_db)) -> UsuarioDB:
    dados = auth_service.verificar_token_google(payload.credential)
    if dados is None:
        raise HTTPException(status_code=401, detail="Não foi possível confirmar sua conta Google.")
    usuario = (
        db.query(UsuarioDB).filter(UsuarioDB.google_sub == dados["sub"]).first()
        or db.query(UsuarioDB).filter(UsuarioDB.email == dados["email"].lower()).first()
    )
    if usuario is None:
        usuario = UsuarioDB(
            email=dados["email"].lower(), google_sub=dados["sub"], nome_completo=dados["nome"],
            email_verificado=True,
        )
        db.add(usuario)
    elif not usuario.google_sub:
        usuario.google_sub = dados["sub"]
        usuario.email_verificado = True
    db.commit()
    db.refresh(usuario)
    auth_service.definir_cookie_sessao(response, usuario.id)
    return usuario


@router.post("/logout")
def logout(response: Response) -> dict:
    auth_service.limpar_cookie_sessao(response)
    auth_service.limpar_cookie_admin(response)
    return {"ok": True}


@router.get("/eu", response_model=UsuarioOut)
def eu(usuario: UsuarioDB = Depends(_usuario_logado)) -> UsuarioDB:
    return usuario


@router.post("/admin-login")
def admin_login(payload: AdminLoginRequest, response: Response) -> dict:
    """Login do painel de administração (cadastrar/verificar locais acessíveis) — usuário e senha
    fixos no .env, sem relação com as contas de usuário comuns."""
    if not auth_service.credenciais_admin_corretas(payload.usuario, payload.senha):
        raise HTTPException(status_code=401, detail="Usuário ou senha de administrador incorretos.")
    auth_service.definir_cookie_admin(response)
    return {"admin": True}


@router.get("/admin-eu")
def admin_eu(request: Request) -> dict:
    if not auth_service.admin_logado(request):
        raise HTTPException(status_code=401, detail="Não autenticado como administrador.")
    return {"admin": True}


@router.get("/verificar-email")
def verificar_email(token: str, db: Session = Depends(get_db)) -> dict:
    usuario = _consumir_token(db, token, "verificar_email")
    usuario.email_verificado = True
    db.commit()
    return {"ok": True}


@router.post("/recuperar-senha")
def recuperar_senha(payload: RecuperarSenhaRequest, db: Session = Depends(get_db)) -> dict:
    if not auth_service.verificar_captcha(payload.captcha_token):
        raise HTTPException(status_code=400, detail="Não foi possível confirmar o captcha. Tente de novo.")
    usuario = db.query(UsuarioDB).filter(UsuarioDB.email == payload.email.lower()).first()
    # Mensagem igual exista ou não a conta, para não revelar quais e-mails estão cadastrados.
    if usuario is not None and usuario.senha_hash is not None:
        token = _criar_token(db, usuario, "redefinir_senha")
        link = f"{settings.app_base_url}/redefinir-senha.html?token={token}"
        enviar_email(
            usuario.email, "Redefinir sua senha no DivergentIA",
            f"Olá, {usuario.nome_completo}!\n\nClique no link abaixo para escolher uma nova senha (vale por 2 horas):\n{link}\n\n"
            "Se você não pediu essa troca, ignore esta mensagem — sua senha continua a mesma.",
        )
    return {"mensagem": "Se este e-mail tiver uma conta, enviamos um link de redefinição para ele."}


@router.post("/redefinir-senha")
def redefinir_senha(payload: RedefinirSenhaRequest, db: Session = Depends(get_db)) -> dict:
    usuario = _consumir_token(db, payload.token, "redefinir_senha")
    usuario.senha_hash = auth_service.hash_senha(payload.nova_senha)
    db.commit()
    return {"ok": True}


TEXTO_TERMO_LGPD = """\
Ao criar sua conta no DivergentIA, você concorda com o uso dos seus dados nos termos da Lei Geral de \
Proteção de Dados (Lei nº 13.709/2018):

FINALIDADE: os dados pessoais e socioeconômicos deste cadastro (idade, sexo, etnia, escolaridade, renda, \
composição familiar e condição de acessibilidade) são usados apenas de forma agregada e anonimizada, para \
avaliar o impacto social do projeto de extensão DivergentIA junto ao público que ele atende. Nome, e-mail, \
CPF/RG e endereço servem só para identificar e dar suporte à sua conta, e não entram nessa análise agregada.

BASE LEGAL: consentimento (art. 7º, I) para a análise socioeconômica; execução de contrato (art. 7º, V) para \
a criação e manutenção da conta. Sexo, etnia e condição de acessibilidade são dados sensíveis (art. 5º, II); \
por isso este consentimento é específico para esse uso, e não serve para nenhuma outra finalidade.

COMPARTILHAMENTO: seus dados não são vendidos nem repassados a terceiros. Resultados de pesquisa são sempre \
divulgados de forma agregada, sem identificar nenhuma pessoa.

SEUS DIREITOS: a qualquer momento você pode pedir para ver, corrigir ou apagar seus dados, ou revogar este \
consentimento, falando com a equipe do projeto. Revogar o consentimento não apaga dados de conversas que \
você já teve com o assistente, pois essas conversas não ficam gravadas no servidor.

ARMAZENAMENTO: os dados ficam no banco do projeto (ainda em fase de desenvolvimento e extensão universitária) \
enquanto sua conta existir ou até você pedir a exclusão.

Você pode ler a íntegra da LGPD em https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm.\
"""
