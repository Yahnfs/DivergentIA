from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    mensagem: str = Field(..., description="Pergunta do usuário em linguagem natural")
    municipio: Optional[str] = Field(None, description="Município para filtrar serviços/leis locais")


class FonteConsultada(BaseModel):
    id: str
    tipo: str  # "lei" ou "servico"
    titulo: str
    score: float


class PassoRoteiro(BaseModel):
    ordem: int
    titulo: str
    descricao: str
    documentos: list[str] = []
    orgao_responsavel: Optional[str] = None


class Roteiro(BaseModel):
    resumo: str
    passos: list[PassoRoteiro]
    aviso: Optional[str] = None
    fontes_citadas: list[str] = []


class ChatResponse(BaseModel):
    resposta_texto: str
    roteiro: Optional[Roteiro] = None
    fontes_consultadas: list[FonteConsultada] = []


class LocalAcessivelCreate(BaseModel):
    nome: str
    municipio: str
    endereco: str
    tipo: str = Field(..., description="Ex: comercio, saude, educacao, lazer, orgao_publico")
    recursos_acessibilidade: list[str] = Field(
        default=[],
        description="Ex: rampa, banheiro_adaptado, braille, baixo_estimulo_sensorial, atendimento_preferencial",
    )
    observacoes: Optional[str] = None
    reportado_por: Optional[str] = None


class LocalAcessivelOut(LocalAcessivelCreate):
    id: int
    verificado: bool

    class Config:
        from_attributes = True
