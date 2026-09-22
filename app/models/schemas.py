from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Peças que vêm SEMPRE da base de conhecimento verificada (nunca do texto do LLM)
# ---------------------------------------------------------------------------

class Link(BaseModel):
    titulo: str
    url: str


class Telefone(BaseModel):
    numero: str
    rotulo: Optional[str] = None


class UnidadeContato(BaseModel):
    nome: str
    endereco: Optional[str] = None
    telefones: list[str] = []
    bairros: Optional[str] = None


class ContatoOut(BaseModel):
    id: str
    nome: str
    municipio: Optional[str] = None
    telefones: list[Telefone] = []
    whatsapp: list[Telefone] = []
    email: Optional[str] = None
    site: Optional[str] = None
    endereco: Optional[str] = None
    horario: Optional[str] = None
    observacao: Optional[str] = None
    fonte_url: Optional[str] = None
    verificado_em: Optional[str] = None
    unidades: list[UnidadeContato] = []
    unidade_destaque: Optional[str] = None   # unidade (ex.: CRAS) que atende o bairro citado pelo usuário


class FonteOut(BaseModel):
    id: str
    tipo: Literal["lei", "servico", "projeto"]
    titulo: str
    esfera: Optional[str] = None
    municipio: Optional[str] = None
    links: list[Link] = []
    verificado_em: Optional[str] = None
    atencao: Optional[str] = None
    citada: bool = False


# ---------------------------------------------------------------------------
# Roteiro (a "task list") e resposta do chat
# ---------------------------------------------------------------------------

class PassoOut(BaseModel):
    ordem: int
    titulo: str
    descricao: str
    documentos: list[str] = []
    fonte_id: Optional[str] = None
    fonte_titulo: Optional[str] = None   # nome curto do serviço de onde vem o passo
    # Preenchidos pelo servidor a partir da fonte do passo (só no 1º passo de cada fonte):
    links: list[Link] = []
    contato_ids: list[str] = []
    atencao: Optional[str] = None


class DireitoOut(BaseModel):
    """Trecho de lei (da base verificada) que apoia o pedido: a pessoa pode citá-lo ao atendente."""
    fonte_id: str
    titulo: str
    numero: Optional[str] = None
    trechos: list[str] = []
    links: list[Link] = []
    projeto: bool = False   # True quando é só um projeto de lei (ainda não é lei)


class RoteiroOut(BaseModel):
    titulo: str
    resumo: str
    passos: list[PassoOut] = []
    direitos: list[DireitoOut] = []
    aviso: Optional[str] = None


Cobertura = Literal["completa", "parcial", "nenhuma"]


class MensagemChat(BaseModel):
    papel: Literal["usuario", "assistente"]
    conteudo: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=1500, description="Mensagem do usuário")
    municipio: Optional[str] = Field(None, description="Município escolhido pelo usuário")
    historico: list[MensagemChat] = Field(
        default_factory=list, max_length=20,
        description="Mensagens anteriores da conversa (o servidor não guarda conversas)",
    )
    roteiro_atual: Optional[RoteiroOut] = Field(
        None, description="Último roteiro mostrado ao usuário, para o assistente atualizá-lo",
    )


class OpcaoResposta(BaseModel):
    rotulo: str      # texto do botão
    mensagem: str    # o que é enviado ao chat quando a pessoa clica


class PerguntaOut(BaseModel):
    """Pergunta de triagem do assistente, com respostas em botões."""
    id: str
    pergunta: str
    opcoes: list[OpcaoResposta]


class ChatResponse(BaseModel):
    mensagem: str
    cobertura: Cobertura
    perguntas: list[PerguntaOut] = []        # dados que faltam para melhorar o roteiro
    sugestoes: list[str] = []                # atalhos: mensagens que a pessoa pode enviar
    roteiro: Optional[RoteiroOut] = None
    contatos: list[ContatoOut] = []          # todos os cartões de contato citados nesta resposta
    contatos_de_apoio: list[str] = []        # ids dos contatos para "Quem pode ajudar agora"
    fontes: list[FonteOut] = []
    municipio_detectado: Optional[str] = None


class PdfRequest(BaseModel):
    roteiro: RoteiroOut
    contatos: list[ContatoOut] = []
    contatos_de_apoio: list[str] = []
    fontes: list[FonteOut] = []


# ---------------------------------------------------------------------------
# Mapeamento colaborativo de locais acessíveis
# ---------------------------------------------------------------------------

class LocalAcessivelCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=120)
    municipio: str = Field(..., min_length=1, max_length=60)
    endereco: str = Field(..., min_length=1, max_length=200)
    tipo: str = Field(..., max_length=40, description="Ex: comercio, saude, educacao, lazer, orgao_publico")
    recursos_acessibilidade: list[str] = Field(
        default=[], max_length=12,
        description="Ex: rampa, banheiro_adaptado, braille, baixo_estimulo_sensorial, atendimento_preferencial",
    )
    observacoes: Optional[str] = Field(None, max_length=500)
    reportado_por: Optional[str] = Field(None, max_length=120)


class LocalAcessivelOut(LocalAcessivelCreate):
    id: int
    verificado: bool

    class Config:
        from_attributes = True
