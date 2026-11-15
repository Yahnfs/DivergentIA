"""Chat do DivergentIA.

Divisão de trabalho:

  - O SERVIDOR escolhe as fontes (ranking da busca + etiquetas exatas, com a IA como último recurso quando a
    busca não acha nada), monta o roteiro com os passos oficiais da base, anexa links e contatos verificados
    e decide o que perguntar (município, rede de ensino, laudo).
  - O MODELO de IA escreve a resposta em texto, mas só pode afirmar o que estiver nos fatos verificados que o
    servidor entrega a ela (resumo, passos, trechos de lei) — nunca completa com conhecimento geral próprio, e
    diz quando não tem um detalhe específico. Por isso a tela mostra sempre o aviso "pode cometer erros": o
    texto é gerado, mesmo que baseado em fatos verificados. Se o modelo estiver fora do ar, o chat continua
    funcionando (cai para o resumo puro da base).
"""
import datetime
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import ConversaDB, MensagemConversaDB, UsuarioDB, get_db
from app.models.schemas import (
    ChatRequest, ChatResponse, ConversaOut, ConversaResumo, ContatoOut, DireitoOut, FonteOut, MensagemChat,
    OpcaoResposta, PassoOut, PerguntaOut, RoteiroOut,
)
from app.services import auth_service
from app.services.llm_provider import LLMProviderError, get_llm_provider
from app.services.rag_engine import (
    MUNICIPIO_OUTRO, MUNICIPIOS_COBERTOS, base, detectar_municipio, detectar_rede, normalizar,
)

router = APIRouter(prefix="/chat", tags=["chat"])
log = logging.getLogger("divergentia.chat")

LIMITE_CONFIANCA = 0.12          # abaixo disso a resposta nunca é tratada como "completa"
MAX_SERVICOS_POR_TURNO = 2       # serviços que uma mesma pergunta pode acrescentar
MAX_SERVICOS_ROTEIRO = 4         # o roteiro acumula os assuntos da conversa, até este limite
MAX_LEIS_ROTEIRO = 3
LIMITE_LEI = 0.15
MAX_HISTORICO = 4

ESCOLAS_MUNICIPAIS = {"educacao-apoio-escolar-vitoria", "educacao-apoio-escolar-serra", "educacao-apoio-escolar-vila-velha"}
ESCOLA_ESTADUAL = "educacao-apoio-escolar-estadual"
EDUCACAO = ESCOLAS_MUNICIPAIS | {ESCOLA_ESTADUAL}

SAUDACAO = re.compile(
    r"^\s*(oi+|ol[aá]|bom dia|boa tarde|boa noite|e a[ií]|opa|tudo bem\??)([\s,!.?]+(tudo bem\??|td bem\??))?[\s!?.]*$",
    re.I,
)
AGRADECIMENTO = re.compile(
    r"^\s*((ok|okay|certo|entendi|beleza|blz|show|t[aá] bom|t[aá] certo)[\s,!.]+)*"
    r"((muito|mto)\s+)?(obrigad[oa]s?|valeu|agrade[cç]o|brigad[oa]|tchau|at[eé] mais)\b[\s!?.,a-zçãõé]*$", re.I)
SO_RESPOSTA = re.compile(r"^\s*(moro|sou d[aeo]|estou)\b|escola [ée] d[ae]|(j[aá]|ainda n[aã]o) (tem|existe)\b.*laudo", re.I)
# Pergunta sobre a PRÓPRIA conversa (resumir, relembrar, voltar a um ponto) — checado no texto já normalizado
# (sem acento), antes da busca por palavras, para o contexto da conversa não "puxar" um assunto qualquer.
SOBRE_CONVERSA = re.compile(
    r"\b(resum[ae]|resumir|relembr[ae]|relembrar|repit[ae]|repetir)\b.{0,25}\b(pergunta|chat|conversa|mensage)"
    r"|\b(quais|que)\s+perguntas\s+(eu\s+)?(te\s+)?fiz\b"
    r"|\bo\s+que\s+(eu\s+)?(ja\s+)?(te\s+)?perguntei\b"
    r"|\bhistorico\s+(da\s+conversa|de\s+perguntas)\b",
)

# Perguntas de triagem: o texto e os botões são fixos; o servidor decide QUANDO perguntar.
PERGUNTAS = {
    "municipio": PerguntaOut(id="municipio", pergunta="Em qual município você mora?", opcoes=[
        OpcaoResposta(rotulo="Vitória", mensagem="Moro em Vitória"),
        OpcaoResposta(rotulo="Serra", mensagem="Moro na Serra"),
        OpcaoResposta(rotulo="Vila Velha", mensagem="Moro em Vila Velha"),
        OpcaoResposta(rotulo="Outro município", mensagem="Moro em outro município"),
    ]),
    "rede_ensino": PerguntaOut(id="rede_ensino", pergunta="A escola é da rede municipal ou estadual?", opcoes=[
        OpcaoResposta(rotulo="Municipal", mensagem="A escola é da rede municipal"),
        OpcaoResposta(rotulo="Estadual", mensagem="A escola é da rede estadual"),
    ]),
    "laudo": PerguntaOut(id="laudo", pergunta="Já existe laudo médico?", opcoes=[
        OpcaoResposta(rotulo="Sim, já tem", mensagem="Já existe laudo médico"),
        OpcaoResposta(rotulo="Ainda não", mensagem="Ainda não existe laudo médico"),
    ]),
}


# ---------------------------------------------------------------------------
# Proteção contra telefones e links inventados pelo modelo
# ---------------------------------------------------------------------------

TELEFONE = re.compile(r"(?<!\d)(?:\(?\d{2}\)?[\s-]?)?9?\d{4}[\s-]?\d{4}(?!\d)|0800[\s-]?\d{3}[\s-]?\d{3,4}")
URL = re.compile(r"https?://\S+|www\.\S+")


def _numeros_validos() -> set[str]:
    """Os 8 dígitos finais de todo telefone que existe na base verificada."""
    validos: set[str] = set()
    for c in base.contatos.values():
        numeros = [t["numero"] for t in c.get("telefones", []) + c.get("whatsapp", [])]
        numeros += [t for u in c.get("unidades", []) for t in u.get("telefones", [])]
        validos.update(re.sub(r"\D", "", n)[-8:] for n in numeros if len(re.sub(r"\D", "", n)) >= 8)
    return validos


def _sanear(texto: str, validos: set[str]) -> str:
    """Remove links e telefones que não existem na base. Contatos só aparecem vindos da base, nos cartões."""
    def trocar_telefone(m: re.Match) -> str:
        if re.sub(r"\D", "", m.group(0))[-8:] in validos:
            return m.group(0)
        log.warning("Telefone fora da base removido do texto do modelo: %s", m.group(0))
        return "(veja o número nos contatos)"

    return TELEFONE.sub(trocar_telefone, URL.sub("(veja o link nas fontes)", texto)).strip()


# ---------------------------------------------------------------------------
# Frase de abertura (o único texto livre do modelo)
# ---------------------------------------------------------------------------

def _historico_para_llm(historico: list[MensagemChat], mensagem: str) -> list[dict]:
    """Últimas mensagens no formato do LLM: começa numa fala do usuário, alterna papéis, termina na pergunta atual."""
    mensagens: list[dict] = []
    for m in historico[-MAX_HISTORICO:]:
        papel = "user" if m.papel == "usuario" else "assistant"
        if not mensagens and papel == "assistant":
            continue
        if mensagens and mensagens[-1]["role"] == papel:
            mensagens[-1]["content"] += "\n" + m.conteudo[:400]
        else:
            mensagens.append({"role": papel, "content": m.conteudo[:400]})
    if mensagens and mensagens[-1]["role"] == "user":
        mensagens.pop()  # pergunta anterior sem resposta: descarta para manter a alternância
    mensagens.append({"role": "user", "content": mensagem})
    return mensagens


def _fatos_para_ia(itens: list[dict]) -> str:
    """Texto com os fatos já verificados (resumo, passos, trechos de lei) que a IA pode usar para responder.
    É o único material que ela pode tratar como fato — tudo fora daqui é "não tenho essa informação"."""
    blocos = []
    for item in itens:
        linhas = [f"### {item.get('titulo_curto') or item['titulo']}"]
        if item.get("resumo"):
            linhas.append(item["resumo"])
        for p in item.get("passos", []):
            linhas.append(f"- {p['titulo']}: {p['texto']}")
        for t in item.get("trechos", []):
            linhas.append(f"- {t}")
        if item.get("atencao"):
            linhas.append(f"Atenção: {item['atencao']}")
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


SYSTEM_RESPONDER = """\
Você é o assistente do DivergentIA, especializado em direitos e serviços para pessoas com deficiência e \
neurodivergentes na Grande Vitória (ES). Responda à ÚLTIMA mensagem da pessoa de forma natural, direta e \
acolhedora, levando em conta o que já foi dito antes na conversa.

Use SÓ os fatos verificados abaixo para qualquer informação específica (valor, prazo, documento, nome de lei, \
procedimento, telefone, link). Se a pergunta pedir algo que não está nestes fatos — por exemplo um valor de \
indenização, um prazo que não foi informado, ou um órgão que não está listado — diga com clareza que você não \
tem essa informação específica; nunca complete com conhecimento geral seu nem invente um número, link ou valor. \
Não diga "veja ao lado" nem fale do roteiro — isso é adicionado automaticamente depois da sua resposta.

As mensagens suas que aparecem no histórico da conversa JÁ FORAM enviadas por completo — nunca estão cortadas \
ou incompletas, mesmo que os "fatos verificados" abaixo pareçam ter mais detalhes do que você disse antes. Não \
diga que uma resposta sua "ficou cortada" ou "incompleta". Se a pessoa só agradeceu ou confirmou que entendeu, \
responda de forma breve — não repita um passo a passo que você já deu, a não ser que ela peça de novo.

Fatos verificados disponíveis:
{fatos}
"""


def _compor_resposta(payload: ChatRequest, itens: list[dict], validos: set[str]) -> str:
    """A resposta de verdade da conversa: a IA lê a pergunta atual + o histórico e responde usando só os fatos
    já reunidos no roteiro. Nunca solta telefone/link que não esteja na base (ver _sanear). Se a IA falhar,
    cai para o resumo verificado puro — o chat nunca trava por causa disso."""
    fatos = _fatos_para_ia(itens)
    try:
        bruto = get_llm_provider().generate(
            SYSTEM_RESPONDER.format(fatos=fatos), _historico_para_llm(payload.historico, payload.mensagem),
        )
    except LLMProviderError as exc:
        log.warning("IA indisponível para compor a resposta (%s): usando o resumo verificado puro.", exc)
        return itens[0]["resumo"] if len(itens) == 1 else " ".join(_primeira_frase(i["resumo"]) for i in itens)
    return _sanear(bruto.strip(), validos)


SYSTEM_CONVERSA = """\
A pessoa está perguntando sobre a PRÓPRIA conversa — pedir um resumo do que já perguntou, relembrar algo que \
você disse antes, ou pedir uma síntese / "o melhor caminho" com base no que já foi discutido — não um direito \
ou serviço novo. Responda com base no histórico da conversa abaixo e, quando ajudar a responder com mais \
precisão, também nos fatos verificados do roteiro já montado. Não invente nenhuma lei, serviço, telefone ou \
link que não esteja no histórico ou nestes fatos; se faltar um dado para dizer qual é "o melhor" caminho \
(ex.: renda, se já tem laudo), diga isso e pergunte.

Fatos verificados do roteiro já montado nesta conversa (pode estar vazio, se nada foi montado ainda):
{fatos}
"""


def _responder_sobre_conversa(payload: ChatRequest) -> str:
    """Pergunta sobre a conversa em si (ex.: "resuma minhas perguntas", "qual o melhor resultado pra mim") —
    usa o histórico e, quando já existe, também os fatos verificados do roteiro montado até agora."""
    servicos, leis = _itens_do_roteiro(payload.roteiro_atual)
    fatos = _fatos_para_ia([*servicos, *leis]) or "(nenhum roteiro montado ainda)"
    try:
        bruto = get_llm_provider().generate(
            SYSTEM_CONVERSA.format(fatos=fatos), _historico_para_llm(payload.historico, payload.mensagem),
        )
    except LLMProviderError as exc:
        log.warning("IA indisponível para responder sobre a conversa (%s).", exc)
        return "No momento não consigo acessar o histórico para responder isso. Tente de novo em instantes."
    return _sanear(bruto.strip(), _numeros_validos())


# ---------------------------------------------------------------------------
# Último recurso: a busca por palavras não achou nada. Antes de dizer "não sei", pergunta a uma IA se o pedido
# (dito com as palavras da pessoa) corresponde a algum assunto da base — ela só pode apontar um id de uma lista
# fechada, nunca escrever um fato novo. O roteiro continua vindo 100% do JSON verificado; a IA só aponta ONDE olhar.
# ---------------------------------------------------------------------------

def _catalogo_assuntos() -> str:
    linhas = []
    for item in base.itens:
        titulo = item.get("titulo_curto") or item["titulo"]
        resumo = (item.get("resumo") or "").strip()
        if len(resumo) > 160:
            resumo = resumo[:160].rsplit(" ", 1)[0] + "…"
        etiquetas = ", ".join(item.get("tags", [])[:8])
        linhas.append(f"- {item['id']}: {titulo}. {resumo} (etiquetas: {etiquetas})")
    return "\n".join(linhas)


CATALOGO_ASSUNTOS = _catalogo_assuntos()

SYSTEM_CLASSIFICAR = """\
A busca por palavras-chave não achou nada para o que a pessoa escreveu. Veja se o pedido dela, dito do jeito \
dela, corresponde a UM dos assuntos abaixo — mesmo sem nenhuma palavra do título ou do resumo em comum. Pense na \
necessidade por trás da frase (ex.: "não me deixaram entrar por causa da cadeira de rodas" é sobre discriminação \
e denúncia, mesmo sem citar essas palavras).

Se a pergunta não for sobre nenhum direito/serviço, mas sim sobre a PRÓPRIA CONVERSA (pedir um resumo do que já \
foi perguntado, relembrar algo já dito, voltar a um ponto anterior), responda "conversa".

Responda só com o id do assunto escolhido. Se não tiver certeza de que é EXATAMENTE aquele assunto, ou se nenhum \
da lista nem "conversa" servir, responda "nenhum". Nunca responda um id que não esteja nesta lista.

Assuntos:
{catalogo}
"""
CONVERSA = "conversa"
NENHUM = "nenhum"
ESQUEMA_CLASSIFICAR = {
    "type": "object",
    "properties": {"id": {"type": "string", "enum": [*(i["id"] for i in base.itens), CONVERSA, NENHUM]}},
    "required": ["id"],
}


def _classificar_por_ia(mensagem: str) -> dict | str | None:
    """Devolve um item da base, a string CONVERSA (pergunta sobre a própria conversa) ou None (nada encontrado)."""
    try:
        bruto = get_llm_provider().generate(
            SYSTEM_CLASSIFICAR.format(catalogo=CATALOGO_ASSUNTOS), [{"role": "user", "content": mensagem[:500]}],
            ESQUEMA_CLASSIFICAR,
        )
        id_escolhido = str(json.loads(re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.M))["id"]).strip()
    except (LLMProviderError, ValueError, KeyError, TypeError) as exc:
        log.warning("Classificador por IA indisponível (%s): segue sem achar nada na base.", exc)
        return None
    if id_escolhido == CONVERSA:
        return CONVERSA
    item = base.por_id.get(id_escolhido)
    if item is None and id_escolhido != NENHUM:
        log.warning("Classificador por IA respondeu um id fora da lista: %r", id_escolhido[:60])
    elif item is not None:
        log.info("Classificador por IA achou %r para uma pergunta que a busca por palavras não achou.", id_escolhido)
    return item


# ---------------------------------------------------------------------------
# Escolha das fontes e montagem do roteiro (tudo determinístico, a partir da base verificada)
# ---------------------------------------------------------------------------

def _leis_dominantes(itens: list[dict], mensagem: str) -> list[dict]:
    """Leis relevantes à pergunta: a mais parecida sempre entra; as demais só com uma etiqueta exata da MENSAGEM
    ATUAL (não do histórico), para não anexar uma lei de assunto vizinho por pura semelhança de vocabulário
    (ex.: a lei do TDAH aparecer numa pergunta só sobre autismo, porque ambas falam em "escola" e "aprendizagem").
    """
    candidatas = [i for i in itens if i["origem"] != "servico" and i["score"] >= LIMITE_LEI]
    if not candidatas:
        return []
    extras = [i for i in candidatas[1:] if base.etiquetas_batem(i["id"], mensagem) > 0]
    return [candidatas[0], *extras][:MAX_LEIS_ROTEIRO]


def _selecionar(itens: list[dict], mensagem: str) -> tuple[list[dict], list[dict]]:
    """Serviços e leis desta pergunta: o serviço mais parecido; um 2º só se a própria mensagem o cita."""
    # Um serviço só entra se não for muito menos parecido do que o melhor item: quando a resposta é uma lei
    # (ex.: "o laudo precisa ser renovado?"), não se acrescenta um serviço qualquer.
    melhor = itens[0]["score"]
    servicos = [i for i in itens if i["origem"] == "servico" and i["score"] >= 0.75 * melhor]
    leis = _leis_dominantes(itens, mensagem)
    escolhidos: list[dict] = servicos[:1]
    if servicos:
        for s in servicos[1:]:
            if (len(escolhidos) < MAX_SERVICOS_POR_TURNO and s["score"] >= 0.5 * servicos[0]["score"]
                    and s["id"] not in servicos[0].get("inclui", []) and base.etiquetas_batem(s["id"], mensagem) > 0):
                escolhidos.append(s)
    return escolhidos, leis


def _itens_do_roteiro(roteiro: RoteiroOut | None) -> tuple[list[dict], list[dict]]:
    """Os serviços e leis por trás de um roteiro já montado, a partir dos fonte_id guardados em passos/direitos."""
    if not roteiro:
        return [], []
    ids_servicos = dict.fromkeys(p.fonte_id for p in roteiro.passos if p.fonte_id)
    servicos = [base.por_id[i] for i in ids_servicos if i in base.por_id]
    leis = [base.por_id[d.fonte_id] for d in roteiro.direitos if d.fonte_id in base.por_id]
    return servicos, leis


def _acumular(roteiro: RoteiroOut | None, novos: list[dict], leis_novas: list[dict],
              filtro: str | None) -> tuple[list[dict], list[dict]]:
    """Junta o roteiro da conversa com o que veio agora.

    Assuntos diferentes se somam (BPC + passe livre). Variantes do mesmo assunto (escola de Vitória, da Serra,
    estadual...) se substituem, para o roteiro acompanhar o município e a rede que a pessoa foi informando.
    """
    antigos, antigas_leis = _itens_do_roteiro(roteiro)
    antigos = [a for a in antigos if not a.get("municipio") or a["municipio"] == filtro]

    pendentes = list(novos)
    final: list[dict] = []
    for antigo in antigos:
        substituto = next((n for n in pendentes if n["id"] == antigo["id"]
                           or (n.get("topico") and n.get("topico") == antigo.get("topico"))), None)
        if substituto:
            final.append(substituto)
            pendentes.remove(substituto)
        else:
            final.append(antigo)
    final += pendentes

    leis: list[dict] = []
    for lei in [*antigas_leis, *leis_novas]:
        if all(lei["id"] != x["id"] for x in leis):
            leis.append(lei)
    return final[-MAX_SERVICOS_ROTEIRO:], leis[-MAX_LEIS_ROTEIRO:]


def _titulo_e_resumo(servicos: list[dict], leis: list[dict]) -> tuple[str, str]:
    if not servicos:
        return "Seus direitos", "O que a lei garante, para você citar no atendimento."
    nomes = [s.get("titulo_curto") or s["titulo"] for s in servicos]
    if len(servicos) == 1:
        return nomes[0], servicos[0]["resumo"]
    titulo = " + ".join(nomes) if len(servicos) == 2 else f"Meu roteiro ({len(servicos)} assuntos)"
    return titulo, "Reúne o passo a passo de: " + "; ".join(nomes) + "."


def _sem_titulo_repetido(titulo: str, texto: str) -> str:
    """Tira do texto do passo o título repetido no começo, que na tela aparece logo acima dele.

    "Agende pelo site" + "Agende pelo site: em defensoria.es.def.br, faça..." -> "Em defensoria.es.def.br, faça...".
    Só corta quando o título vem seguido de ":" ou "." (senão a frase ficaria sem sujeito, ex.: "Acompanhe o pedido no...").
    """
    if not texto.lower().startswith(titulo.lower()) or texto[len(titulo):len(titulo) + 1] not in (":", "."):
        return texto
    resto = texto[len(titulo) + 1:].strip()
    return resto[:1].upper() + resto[1:] if resto else texto


def _montar_roteiro(servicos: list[dict], leis: list[dict], filtro: str | None,
                    titulo: str, resumo: str, aviso: str | None) -> RoteiroOut | None:
    """Passos oficiais (palavra por palavra) dos serviços + base legal das leis."""
    passos: list[PassoOut] = []
    for item in servicos:
        contatos = base.contatos_do_item(item, filtro)[:3]
        for k, p in enumerate(item["passos"]):
            primeiro = k == 0  # links, contatos, documentos e alertas ficam no 1º passo de cada fonte
            passos.append(PassoOut(
                ordem=len(passos) + 1, titulo=p["titulo"], descricao=_sem_titulo_repetido(p["titulo"], p["texto"]),
                fonte_id=item["id"],
                fonte_titulo=item.get("titulo_curto"),
                documentos=item.get("documentos", []) if primeiro else [],
                links=item.get("links", []) if primeiro else [],
                contato_ids=contatos if primeiro else [],
                atencao=item.get("atencao") if primeiro else None,
            ))
    direitos = [DireitoOut(fonte_id=l["id"], titulo=l["titulo"], numero=l.get("numero"), trechos=l.get("trechos", []),
                           links=l.get("links", []), projeto=l["origem"] == "projeto") for l in leis]
    if not passos and not direitos:
        return None
    return RoteiroOut(titulo=titulo, resumo=resumo, passos=passos, direitos=direitos, aviso=aviso)


# ---------------------------------------------------------------------------
# Montagem da resposta
# ---------------------------------------------------------------------------

def _contato_out(contato_id: str, textos_usuario: str) -> ContatoOut:
    contato = ContatoOut(**base.contatos[contato_id])
    if contato.unidades:
        contato.unidade_destaque = base.unidade_do_bairro(contato_id, textos_usuario)
    return contato


def _contatos_de_apoio(servicos: list[dict], cobertura: str, filtro: str | None) -> list[str]:
    ids: list[str] = []
    for item in servicos:
        for cid in base.contatos_do_item(item, filtro):
            if cid not in ids:
                ids.append(cid)
    ids = ids[:3]
    if cobertura != "completa" or not ids:
        ids += [c for c in base.contatos_gerais(filtro) if c not in ids]
    return ids[:4]


def _fontes_out(usadas: list[dict]) -> list[FonteOut]:
    """As fontes que geraram o roteiro, com todos os links para a pessoa se aprofundar."""
    return [
        FonteOut(id=i["id"], tipo=i["origem"], titulo=i["titulo"], esfera=i.get("esfera"), municipio=i.get("municipio"),
                 links=i.get("links", []), verificado_em=i.get("verificado_em"), atencao=i.get("atencao"), citada=True)
        for i in usadas
    ]


def _resposta(mensagem: str, cobertura: str, *, municipio: str | None, filtro: str | None, textos: str,
              perguntas: list[str] | None = None, sugestoes: list[str] | None = None,
              roteiro: RoteiroOut | None = None, fontes: list[FonteOut] | None = None,
              apoio: list[str] | None = None) -> ChatResponse:
    apoio = apoio or []
    ids = list(dict.fromkeys([*apoio, *(c for p in (roteiro.passos if roteiro else []) for c in p.contato_ids)]))
    return ChatResponse(
        mensagem=mensagem, cobertura=cobertura,
        perguntas=[PERGUNTAS[p] for p in dict.fromkeys(perguntas or []) if p in PERGUNTAS][:2],
        sugestoes=sugestoes or [], roteiro=roteiro,
        contatos=[_contato_out(c, textos) for c in ids], contatos_de_apoio=apoio,
        fontes=fontes or [], municipio_detectado=municipio,
    )


def _nota_municipio(municipio: str | None) -> str:
    if municipio and municipio not in MUNICIPIOS_COBERTOS:
        de = "do seu município" if municipio == MUNICIPIO_OUTRO else f"de {municipio}"
        return (f" Ainda não tenho dados municipais {de} (por enquanto cubro Vitória, Serra e Vila Velha), "
                "então os contatos abaixo são nacionais e estaduais; procure também a Prefeitura da sua cidade.")
    return ""


def _primeira_frase(texto: str) -> str:
    """Primeira frase de um resumo (não corta em números como '8.899/1994' nem em siglas minúsculas)."""
    return re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", texto.strip(), maxsplit=1)[0]


def _pede_laudo(item: dict) -> bool:
    texto = normalizar(" ".join([*item.get("documentos", []), *(p["titulo"] + " " + p["texto"] for p in item.get("passos", []))]))
    return "laudo" in texto or "relatorio medico" in texto


def _gerar_resposta(payload: ChatRequest) -> ChatResponse:
    anteriores = [m.conteudo for m in payload.historico if m.papel == "usuario"]
    textos = " ".join([*anteriores[-3:], payload.mensagem])

    # Município: o escolhido na tela, o citado agora ou o citado antes. Só filtra a base se ela o cobre.
    municipio = payload.municipio or detectar_municipio(payload.mensagem) or detectar_municipio(" ".join(anteriores))
    filtro = municipio if municipio in MUNICIPIOS_COBERTOS else None
    nota = _nota_municipio(municipio)
    ctx = {"municipio": municipio, "filtro": filtro, "textos": textos}

    # 1) Cumprimento e agradecimento (sem gastar o modelo).
    if not payload.historico and SAUDACAO.match(payload.mensagem):
        return _resposta(
            "Olá! Sou o assistente do DivergentIA. Posso te orientar sobre direitos, benefícios e serviços para "
            "pessoas com deficiência e neurodivergentes na Grande Vitória, e montar um passo a passo com documentos, "
            "links oficiais e telefones. Sobre o que você quer falar?", "completa", **ctx)
    if AGRADECIMENTO.match(payload.mensagem):
        return _resposta("Por nada! Se precisar de mais alguma coisa, é só me chamar. O roteiro fica ao lado para você "
                         "consultar e baixar em PDF.", "completa", **ctx)
    if payload.historico and SOBRE_CONVERSA.search(normalizar(payload.mensagem)):
        # Pergunta sobre a conversa em si: checa ANTES da busca, senão o contexto acumulado (ex.: "BPC" dito
        # antes) "puxa" um assunto qualquer da base para dentro de uma pergunta que não é sobre nenhum assunto.
        return _resposta(_responder_sobre_conversa(payload), "completa", **ctx)

    # 2) Pergunta que a base sabidamente NÃO responde (ex.: lista de escolas com rampa): resposta honesta e fixa,
    #    com o contato de quem sabe.
    lacuna = base.detectar_lacuna(payload.mensagem)
    if lacuna:
        contatos = [c for c in lacuna["contatos"] if base.contatos[c].get("municipio") in (None, filtro)]
        if lacuna["contatos"]:  # lacuna sem contatos (ex.: locais acessíveis) remete à seção da página, não a um órgão
            contatos = contatos or base.contatos_gerais(filtro)
        faltando = [p for p in lacuna.get("perguntas", []) if not (p == "municipio" and municipio)]
        return _resposta(lacuna["mensagem"] + nota, "nenhuma", perguntas=faltando, apoio=contatos[:4], **ctx)

    # 3) Busca na base (a mensagem atual pesa mais que as anteriores).
    consulta = f"{payload.mensagem} {payload.mensagem} " + " ".join(anteriores[-2:])
    encontrados = base.buscar(consulta, top_k=8, municipio=filtro, mensagem_atual=payload.mensagem)
    via_ia = False
    if not encontrados:
        item_ia = _classificar_por_ia(payload.mensagem)
        if item_ia == CONVERSA:
            return _resposta(_responder_sobre_conversa(payload), "completa", **ctx)
        if item_ia:
            encontrados, via_ia = [{**item_ia, "score": 0.3}], True
    rede = detectar_rede(textos)

    # 3a) Triagem da escola: o caminho para pedir apoio muda entre a rede municipal (e a cidade) e a estadual.
    #     Antes de mostrar passos, pergunta o que falta e já entrega os direitos, que valem para todos.
    if encontrados and encontrados[0]["id"] in EDUCACAO and (rede is None or (rede == "municipal" and filtro is None)):
        leis = _leis_dominantes(encontrados, payload.mensagem)
        direitos = _montar_roteiro([], leis, filtro, "Seus direitos na escola",
                                   "O que a lei garante, para você citar na escola ou na Secretaria de Educação.", None)
        anota = f"Anotei que você mora em {municipio}. " if municipio in MUNICIPIOS_COBERTOS else ""
        if rede is None:
            texto, faltando = (anota + "Para te mostrar o passo a passo certo, preciso saber se a escola é da rede municipal "
                               "ou da estadual, porque o caminho para pedir apoio é diferente em cada uma. Enquanto isso, "
                               "veja ao lado o que a lei garante."), "rede_ensino"
        else:
            texto, faltando = ("Como a escola é da rede municipal, o caminho depende do município. Em qual município "
                               "você mora?"), "municipio"
        return _resposta(texto, "parcial", perguntas=[faltando], roteiro=direitos, fontes=_fontes_out(leis), **ctx)

    if rede == "estadual":
        encontrados = [i for i in encontrados if i["id"] not in ESCOLAS_MUNICIPAIS]
    elif rede == "municipal":
        encontrados = [i for i in encontrados if i["id"] != ESCOLA_ESTADUAL]
    # "Pendente" = há um item municipal quase tão relevante quanto o melhor, que só dá para mostrar sabendo a cidade.
    melhor_geral = encontrados[0]["score"] if encontrados else 0.0
    municipais_pendentes = filtro is None and any(i.get("municipio") and i["score"] >= 0.75 * melhor_geral for i in encontrados)
    itens = [i for i in encontrados if filtro or not i.get("municipio")]

    if not itens and municipais_pendentes:
        # O assunto só existe por município (ex.: credencial de estacionamento) e não sabemos o município.
        return _resposta("Para te mostrar o passo a passo certo, preciso saber em qual município você mora, porque o "
                         "caminho muda entre Vitória, Serra e Vila Velha.", "parcial", perguntas=["municipio"], **ctx)

    if not itens:
        if SO_RESPOSTA.search(payload.mensagem) and not payload.roteiro_atual:
            return _resposta("Anotei! Sobre o que você quer falar?", "completa", **ctx)
        return _resposta(
            "Não encontrei na minha base informações sobre isso, e prefiro não te passar nada incerto." + nota +
            " Veja abaixo quem pode te orientar. Se quiser, reformule a pergunta com outras palavras (por exemplo, "
            "o nome do benefício ou do documento).", "nenhuma",
            apoio=base.contatos_gerais(filtro), **ctx)

    # 4) Seleção determinística + roteiro que acumula os assuntos da conversa.
    novos, leis_novas = _selecionar(itens, payload.mensagem)
    servicos, leis = _acumular(payload.roteiro_atual, novos, leis_novas, filtro)
    if not servicos and not leis:  # só apareceram leis abaixo do limite
        leis = [i for i in itens if i["origem"] != "servico"][:1]

    cobertura = "completa"
    if (via_ia or (municipio and municipio not in MUNICIPIOS_COBERTOS) or municipais_pendentes
            or itens[0]["score"] < LIMITE_CONFIANCA):
        cobertura = "parcial"
    if any(s.get("cobertura") == "parcial" for s in servicos):
        cobertura = "parcial"  # a base só tem parte do que se costuma perguntar sobre esse assunto (ver "atencao")
    aviso = "Este roteiro pode não cobrir todos os detalhes. Confirme com os contatos indicados." if cobertura == "parcial" else None

    titulo, resumo = _titulo_e_resumo(servicos, leis)
    roteiro = _montar_roteiro(servicos, leis, filtro, titulo, resumo, aviso)

    # 5) Perguntas de triagem (no máximo 2). O laudo só é perguntado quando um serviço novo entra no roteiro.
    ids_antigos = {p.fonte_id for p in payload.roteiro_atual.passos} if payload.roteiro_atual else set()
    perguntas: list[str] = []
    if not municipio and (municipais_pendentes or any(base.tem_contato_municipal(s) for s in servicos)):
        perguntas.append("municipio")
    if any(s["id"] not in ids_antigos and _pede_laudo(s) for s in servicos) and "laudo" not in normalizar(textos):
        perguntas.append("laudo")

    # 6) Mensagem: a IA responde à pergunta de agora com base nos fatos já reunidos (nunca texto livre fora deles).
    algo_novo = bool(novos or leis_novas)
    ponteiro = ""
    if novos:
        ponteiro = " Montei o passo a passo ao lado." if len(novos) == 1 else " Montei o passo a passo dos dois ao lado."
    elif leis_novas or not payload.roteiro_atual:
        ponteiro = " Veja ao lado o que a lei garante."
    mensagem = _compor_resposta(payload, [*servicos, *leis], _numeros_validos()) + ponteiro + nota
    if not algo_novo and payload.roteiro_atual:
        # Nada novo no roteiro desta vez: não reenvia o mesmo roteiro (a resposta em texto continua respondendo).
        roteiro = None
        cobertura = "parcial"

    apoio = _contatos_de_apoio(servicos, cobertura, filtro) if "municipio" not in perguntas or servicos else []
    return _resposta(
        mensagem, cobertura, perguntas=perguntas, roteiro=roteiro, apoio=apoio,
        fontes=_fontes_out([*servicos, *leis]), **ctx,
    )


# ---------------------------------------------------------------------------
# Histórico: só existe para quem está logado. Sem login, nada muda (ver GET /chat/opcoes-lgpd na home).
# ---------------------------------------------------------------------------

def _salvar_turno(db: Session, usuario_id: int, payload: ChatRequest, resposta: ChatResponse) -> int:
    conversa = None
    if payload.conversa_id:
        conversa = (
            db.query(ConversaDB)
            .filter(ConversaDB.id == payload.conversa_id, ConversaDB.usuario_id == usuario_id)
            .first()
        )
    if conversa is None:
        conversa = ConversaDB(usuario_id=usuario_id, titulo=payload.mensagem.strip()[:80])
        db.add(conversa)

    conversa.mensagens.append(MensagemConversaDB(papel="usuario", conteudo=payload.mensagem))
    conversa.mensagens.append(MensagemConversaDB(papel="assistente", conteudo=resposta.mensagem))
    if resposta.roteiro:
        conversa.roteiro_final = resposta.roteiro.model_dump(mode="json")
    conversa.atualizada_em = datetime.datetime.utcnow()
    db.commit()
    db.refresh(conversa)
    return conversa.id


@router.post("", response_model=ChatResponse)
def conversar(payload: ChatRequest, request: Request, db: Session = Depends(get_db)) -> ChatResponse:
    resposta = _gerar_resposta(payload)
    usuario_id = auth_service.usuario_id_da_sessao(request)
    if usuario_id:
        resposta.conversa_id = _salvar_turno(db, usuario_id, payload, resposta)
    return resposta


@router.get("/conversas", response_model=list[ConversaResumo])
def listar_conversas(
    usuario: UsuarioDB = Depends(auth_service.usuario_logado), db: Session = Depends(get_db),
) -> list[ConversaDB]:
    return (
        db.query(ConversaDB).filter(ConversaDB.usuario_id == usuario.id)
        .order_by(ConversaDB.atualizada_em.desc()).all()
    )


@router.get("/conversas/{conversa_id}", response_model=ConversaOut)
def obter_conversa(
    conversa_id: int, usuario: UsuarioDB = Depends(auth_service.usuario_logado), db: Session = Depends(get_db),
) -> ConversaDB:
    conversa = db.query(ConversaDB).filter(ConversaDB.id == conversa_id, ConversaDB.usuario_id == usuario.id).first()
    if conversa is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return conversa


@router.delete("/conversas/{conversa_id}")
def apagar_conversa(
    conversa_id: int, usuario: UsuarioDB = Depends(auth_service.usuario_logado), db: Session = Depends(get_db),
) -> dict:
    apagadas = (
        db.query(ConversaDB).filter(ConversaDB.id == conversa_id, ConversaDB.usuario_id == usuario.id).delete()
    )
    db.commit()
    if not apagadas:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return {"ok": True}
