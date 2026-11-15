"""Tudo relacionado a contas: hash de senha, cookie de sessão, verificação do captcha e do login
com Google. Nada aqui decide o que a pessoa pode ou não fazer sem login — o chat continua livre;
isso só cria a conta de quem decide se cadastrar (ver app/routers/auth.py)."""
import datetime
import hashlib
import logging
import secrets

import bcrypt
import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import UsuarioDB, get_db

log = logging.getLogger("divergentia.auth")

COOKIE_SESSAO = "dv_sessao"
COOKIE_ADMIN = "dv_admin"

# ---------------------------------------------------------------------------
# Senha
# ---------------------------------------------------------------------------

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def senha_confere(senha: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        return False  # hash corrompido/formato inesperado


# ---------------------------------------------------------------------------
# Cookie de sessão (JWT simples, assinado com a secret_key do .env)
# ---------------------------------------------------------------------------

def criar_sessao(usuario_id: int) -> str:
    expira = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(usuario_id), "exp": expira}, settings.secret_key, algorithm="HS256")


def usuario_id_da_sessao(request: Request) -> int | None:
    token = request.cookies.get(COOKIE_SESSAO)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def definir_cookie_sessao(response, usuario_id: int) -> None:
    response.set_cookie(
        COOKIE_SESSAO, criar_sessao(usuario_id),
        max_age=settings.access_token_expire_minutes * 60, httponly=True,
        secure=settings.cookie_secure, samesite="lax", path="/",
    )


def limpar_cookie_sessao(response) -> None:
    response.delete_cookie(COOKIE_SESSAO, path="/")


def usuario_logado(request: Request, db: Session = Depends(get_db)) -> UsuarioDB:
    """Dependência de rota: exige login (401 sem sessão válida). Usada por /auth/eu e pelo histórico do chat."""
    usuario_id = usuario_id_da_sessao(request)
    usuario = db.query(UsuarioDB).filter(UsuarioDB.id == usuario_id).first() if usuario_id else None
    if usuario is None:
        raise HTTPException(status_code=401, detail="Faça login para continuar.")
    return usuario


# ---------------------------------------------------------------------------
# Painel de administração (usuário/senha fixos no .env — não é uma conta de usuário comum).
# Protege quem pode cadastrar/verificar locais acessíveis: ver app/routers/locais.py.
# ---------------------------------------------------------------------------

def credenciais_admin_corretas(usuario: str, senha: str) -> bool:
    return secrets.compare_digest(usuario, settings.admin_usuario) and secrets.compare_digest(senha, settings.admin_senha)


def definir_cookie_admin(response) -> None:
    expira = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=settings.access_token_expire_minutes)
    token = jwt.encode({"admin": True, "exp": expira}, settings.secret_key, algorithm="HS256")
    response.set_cookie(
        COOKIE_ADMIN, token,
        max_age=settings.access_token_expire_minutes * 60, httponly=True,
        secure=settings.cookie_secure, samesite="lax", path="/",
    )


def limpar_cookie_admin(response) -> None:
    response.delete_cookie(COOKIE_ADMIN, path="/")


def admin_logado(request: Request) -> bool:
    token = request.cookies.get(COOKIE_ADMIN)
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return bool(payload.get("admin"))
    except jwt.PyJWTError:
        return False


def exigir_admin(request: Request) -> None:
    if not admin_logado(request):
        raise HTTPException(status_code=401, detail="Só o administrador pode fazer isso.")


# ---------------------------------------------------------------------------
# Tokens de uso único (link de e-mail: confirmar conta / redefinir senha)
# ---------------------------------------------------------------------------

def gerar_token() -> tuple[str, str]:
    """Devolve (token para o link do e-mail, hash para guardar no banco). Só o hash fica no banco,
    como se fosse uma senha: um vazamento do banco não dá acesso aos links já enviados."""
    bruto = secrets.token_urlsafe(32)
    return bruto, hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Captcha (Google reCAPTCHA v2) — pulado (sem erro) enquanto não houver chave configurada,
# para dar pra testar o projeto localmente antes de criar uma conta no reCAPTCHA.
# ---------------------------------------------------------------------------

def captcha_configurado() -> bool:
    return bool(settings.recaptcha_secret_key)


def verificar_captcha(token: str | None) -> bool:
    if not captcha_configurado():
        return True
    if not token:
        return False
    try:
        r = httpx.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.recaptcha_secret_key, "response": token}, timeout=10,
        )
        return bool(r.json().get("success"))
    except httpx.HTTPError as exc:
        log.warning("Falha ao verificar o captcha com o Google (%s): tratando como inválido.", exc)
        return False


# ---------------------------------------------------------------------------
# Login com Google: confere a assinatura do token que o botão "Entrar com Google" devolve
# ---------------------------------------------------------------------------

def google_configurado() -> bool:
    return bool(settings.google_client_id)


def verificar_token_google(credential: str) -> dict | None:
    """Confere a assinatura e o destinatário do token do Google. Devolve {email, nome, sub} ou None."""
    if not google_configurado():
        return None
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        dados = google_id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_client_id)
    except Exception as exc:  # token inválido, expirado, assinatura errada etc.
        log.warning("Token do Google rejeitado: %s", exc)
        return None
    if not dados.get("email_verified", True):
        return None
    return {"email": dados["email"], "nome": dados.get("name") or dados["email"].split("@")[0], "sub": dados["sub"]}
