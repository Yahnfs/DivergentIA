"""Chat do DivergentIA.

Regra de ouro: o assistente não inventa. Por isso a divisão de trabalho é esta:

  - O SERVIDOR escolhe as fontes (ranking da busca + etiquetas exatas), monta o roteiro com os passos oficiais
    da base, anexa links e contatos verificados e decide o que perguntar (município, rede de ensino, laudo).
  - O MODELO de IA escreve só uma frase curta reconhecendo o que a pessoa disse. Ele nunca afirma fatos: os
    fatos vêm do resumo verificado da base. Se o modelo estiver fora do ar, o chat continua funcionando.
"""
import json
import logging
import re

from fastapi import APIRouter

from app.models.schemas import (
    ChatRequest, ChatResponse, ContatoOut, DireitoOut, FonteOut, MensagemChat, OpcaoResposta, PassoOut,
    PerguntaOut, RoteiroOut,
)
from app.services.llm_provider import LLMProviderError, get_llm_provider
from app.services.rag_engine import (
    MUNICIPIO_OUTRO, MUNICIPIOS_COBERTOS, base, detectar_municipio, detectar_rede, normalizar, radical,
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

SYSTEM_ABERTURA = """\
Você ajuda a entender o que uma pessoa quer. Complete a frase "Você quer ..." resumindo o PEDIDO dela em até 20 \
palavras, usando só o que ela disse. Comece por um verbo no infinitivo (pedir, saber, conseguir...). Não acrescente \
leis, direitos, prazos, valores, números, telefones nem links. Não dê instruções e não faça perguntas.

Exemplos:
- Pessoa: "Meu filho é autista e quero pedir mediador na escola" -> "pedir apoio na escola para o seu filho autista"
- Pessoa: "como faço isenção de imposto para comprar carro, tenho deficiência física" -> "conseguir isenção de impostos para comprar um carro, por causa da sua deficiência física"
- Pessoa: "e se a escola negar?" -> "saber o que fazer se a escola negar o pedido"
Assunto do roteiro: {foco}.
"""
ESQUEMA_ABERTURA = {
    "type": "object",
    "properties": {"complemento": {"type": "string"}},
    "required": ["complemento"],
}
PALAVRAS_DE_PERGUNTA = {"como", "qual", "quais", "onde", "quando", "que", "porque", "por", "quem", "quanto"}
# Palavras de "fato" que a frase de abertura não pode conter (fatos só vêm do texto verificado da base).
PALAVRAS_DE_FATO = re.compile(r"\b(lei|leis|artigo|garant\w*|estabelec\w*|determin\w*|obrigat\w*|prazo|gratuit\w*|"
                              r"direitos?|deve|devem|precisa|precisam|necess[aá]ri\w*)\b", re.I)
# Palavras neutras que a frase pode usar mesmo sem a pessoa tê-las dito.
PALAVRAS_NEUTRAS = {radical(p)[:5] for p in ("voce", "quer", "quero", "querer", "saber", "fazer", "pedir", "obter",
                                             "conseguir", "entender", "devido", "sobre", "porque", "causa", "tirar",
                                             "situacao", "informacao", "informacoes", "ajuda", "apoio", "apoiar",
                                             "morando", "morar", "cidade", "municipio", "vivendo", "solicitar")}


def _radicais_de_conteudo(texto: str) -> set[str]:
    """Radicais (5 letras) das palavras longas do texto: 'autista' e 'autismo' contam como a mesma."""
    return {radical(p)[:5] for p in re.findall(r"[a-z0-9]+", normalizar(texto)) if len(p) > 4}

SAUDACAO = re.compile(
    r"^\s*(oi+|ol[aá]|bom dia|boa tarde|boa noite|e a[ií]|opa|tudo bem\??)([\s,!.?]+(tudo bem\??|td bem\??))?[\s!?.]*$",
    re.I,
)
AGRADECIMENTO = re.compile(r"^\s*((muito|mto)\s+)?(obrigad[oa]s?|valeu|agrade[cç]o|brigad[oa]|tchau|at[eé] mais)\b[\s!?.,a-zçãõé]*$", re.I)
SO_RESPOSTA = re.compile(r"^\s*(moro|sou d[aeo]|estou)\b|escola [ée] d[ae]|(j[aá]|ainda n[aã]o) (tem|existe)\b.*laudo", re.I)

TEMAS_INICIAIS = [
    "Como pedir mediador ou apoio para meu filho na escola?",
    "Como conseguir o BPC?",
    "Como pedir isenção de impostos na compra de um carro?",
    "Como tirar a credencial de estacionamento?",
]

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


def _abertura(payload: ChatRequest, foco: str, textos_da_pessoa: str) -> str:
    """Uma frase do modelo reconhecendo a fala da pessoa. Vazia se o modelo falhar ou fugir das regras."""
    try:
        bruto = get_llm_provider().generate(
            SYSTEM_ABERTURA.format(foco=foco), _historico_para_llm(payload.historico, payload.mensagem), ESQUEMA_ABERTURA
        )
        complemento = str(json.loads(re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.M))["complemento"])
    except (LLMProviderError, ValueError, KeyError, TypeError) as exc:
        log.warning("Modelo indisponível para a frase de abertura (%s): usando só o texto da base.", exc)
        return ""
    # O servidor escreve o começo ("Entendi: você quer ..."); o modelo só completa. Tolera se ele repetir o começo.
    complemento = re.sub(r"^(você\s+)?(quer\s+)?", "", complemento.strip(" .!?\"'“”"), flags=re.I).strip()
    palavras = complemento.split()
    primeira_palavra = normalizar(palavras[0]) if palavras else ""
    numeros_da_pessoa = set(re.findall(r"\d+", textos_da_pessoa))
    inventadas = _radicais_de_conteudo(complemento) - _radicais_de_conteudo(textos_da_pessoa) - PALAVRAS_NEUTRAS
    # Só vale se começar por um verbo no infinitivo (o pedido foi um complemento de "você quer ..."), tiver mais de
    # uma palavra, não trouxer fatos, números novos, links ou perguntas, nem palavras que a pessoa não usou
    # (ex.: "seu filho" quando ela disse "minha filha"; "interestadual" quando ela não falou disso), e não repetir a fala dela.
    if (len(palavras) < 2 or not re.match(r"^\w{3,}(ar|er|ir)$", primeira_palavra)
            or len(complemento) > 150 or "?" in complemento or URL.search(complemento)
            or primeira_palavra in PALAVRAS_DE_PERGUNTA or PALAVRAS_DE_FATO.search(complemento)
            or any(n not in numeros_da_pessoa for n in re.findall(r"\d+", complemento))
            or inventadas or normalizar(complemento) == normalizar(payload.mensagem.strip(" .!?"))):
        log.warning("Frase de abertura descartada (%s): %r", ", ".join(sorted(inventadas)) or "regras", complemento[:120])
        return ""
    return f"Entendi: você quer {complemento}."


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


def _acumular(roteiro: RoteiroOut | None, novos: list[dict], leis_novas: list[dict],
              filtro: str | None) -> tuple[list[dict], list[dict]]:
    """Junta o roteiro da conversa com o que veio agora.

    Assuntos diferentes se somam (BPC + passe livre). Variantes do mesmo assunto (escola de Vitória, da Serra,
    estadual...) se substituem, para o roteiro acompanhar o município e a rede que a pessoa foi informando.
    """
    antigos: list[dict] = []
    antigas_leis: list[dict] = []
    if roteiro:
        ids = dict.fromkeys(p.fonte_id for p in roteiro.passos if p.fonte_id)
        antigos = [base.por_id[i] for i in ids if i in base.por_id]
        antigas_leis = [base.por_id[d.fonte_id] for d in roteiro.direitos if d.fonte_id in base.por_id]
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


def _montar_roteiro(servicos: list[dict], leis: list[dict], filtro: str | None,
                    titulo: str, resumo: str, aviso: str | None) -> RoteiroOut | None:
    """Passos oficiais (palavra por palavra) dos serviços + base legal das leis."""
    passos: list[PassoOut] = []
    for item in servicos:
        contatos = base.contatos_do_item(item, filtro)[:3]
        for k, p in enumerate(item["passos"]):
            primeiro = k == 0  # links, contatos, documentos e alertas ficam no 1º passo de cada fonte
            passos.append(PassoOut(
                ordem=len(passos) + 1, titulo=p["titulo"], descricao=p["texto"], fonte_id=item["id"],
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


@router.post("", response_model=ChatResponse)
def conversar(payload: ChatRequest) -> ChatResponse:
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
            "links oficiais e telefones. Sobre o que você quer falar?", "completa", sugestoes=TEMAS_INICIAIS, **ctx)
    if AGRADECIMENTO.match(payload.mensagem):
        return _resposta("Por nada! Se precisar de mais alguma coisa, é só me chamar. O roteiro fica ao lado para você "
                         "consultar e baixar em PDF.", "completa", **ctx)

    # 2) Pergunta que a base sabidamente NÃO responde (ex.: lista de escolas com rampa): resposta honesta e fixa,
    #    com o contato de quem sabe.
    lacuna = base.detectar_lacuna(payload.mensagem)
    if lacuna:
        contatos = [c for c in lacuna["contatos"] if base.contatos[c].get("municipio") in (None, filtro)]
        if lacuna["contatos"]:  # lacuna sem contatos (ex.: locais acessíveis) remete à seção da página, não a um órgão
            contatos = contatos or base.contatos_gerais(filtro)
        faltando = [p for p in lacuna.get("perguntas", []) if not (p == "municipio" and municipio)]
        return _resposta(lacuna["mensagem"] + nota, "nenhuma", perguntas=faltando, sugestoes=lacuna.get("sugestoes", []),
                         apoio=contatos[:4], **ctx)

    # 3) Busca na base (a mensagem atual pesa mais que as anteriores).
    consulta = f"{payload.mensagem} {payload.mensagem} " + " ".join(anteriores[-2:])
    encontrados = base.buscar(consulta, top_k=8, municipio=filtro, mensagem_atual=payload.mensagem)
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
            return _resposta("Anotei! Sobre o que você quer falar?", "completa", sugestoes=TEMAS_INICIAIS, **ctx)
        return _resposta(
            "Não encontrei na minha base informações sobre isso, e prefiro não te passar nada incerto." + nota +
            " Veja abaixo quem pode te orientar. Se quiser, reformule a pergunta com outras palavras (por exemplo, "
            "o nome do benefício ou do documento).", "nenhuma", sugestoes=TEMAS_INICIAIS[:3],
            apoio=base.contatos_gerais(filtro), **ctx)

    # 4) Seleção determinística + roteiro que acumula os assuntos da conversa.
    novos, leis_novas = _selecionar(itens, payload.mensagem)
    servicos, leis = _acumular(payload.roteiro_atual, novos, leis_novas, filtro)
    if not servicos and not leis:  # só apareceram leis abaixo do limite
        leis = [i for i in itens if i["origem"] != "servico"][:1]

    cobertura = "completa"
    if (municipio and municipio not in MUNICIPIOS_COBERTOS) or municipais_pendentes or itens[0]["score"] < LIMITE_CONFIANCA:
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

    # 6) Mensagem: frase do modelo (opcional) + resumo verificado da base do que entrou agora no roteiro.
    if novos:
        em_foco, final = novos, ("Montei o passo a passo ao lado." if len(novos) == 1 else "Montei o passo a passo dos dois ao lado.")
    elif leis_novas or not payload.roteiro_atual:
        em_foco, final = (leis_novas or leis)[:1], "Veja ao lado o que a lei garante."
    else:
        em_foco, final = [], ""
    if em_foco:
        corpo = em_foco[0]["resumo"] if len(em_foco) == 1 else " ".join(_primeira_frase(i["resumo"]) for i in em_foco)
        abertura = _abertura(payload, em_foco[0].get("titulo_curto") or em_foco[0]["titulo"], textos)
        mensagem = " ".join(p for p in (abertura, corpo, final) if p) + nota
    else:
        # Nada novo na base sobre esta pergunta: o roteiro que a pessoa já tem continua valendo (não é reenviado).
        mensagem = ("Não achei nada novo sobre isso na minha base. O roteiro ao lado continua valendo; para mais "
                    "detalhes, use os contatos indicados." + nota)
        roteiro = None
        cobertura = "parcial"

    apoio = _contatos_de_apoio(servicos, cobertura, filtro) if "municipio" not in perguntas or servicos else []
    # Atalho "E se negarem?": faz sentido para pedidos (benefícios, documentos, apoio escolar), não para CRAS ou Defensoria.
    pedidos = [s for s in servicos if s["tipo"] in ("beneficio", "documento") or s.get("topico") == "apoio-escolar"]
    sugestoes = ["E se o pedido for negado?"] if pedidos and all(s["id"] != "defensoria-es" for s in servicos) else []
    return _resposta(
        mensagem, cobertura, perguntas=perguntas, sugestoes=sugestoes, roteiro=roteiro, apoio=apoio,
        fontes=_fontes_out([*servicos, *leis]), **ctx,
    )
