import datetime

from sqlalchemy import create_engine, Column, DateTime, ForeignKey, Integer, String, Boolean, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class LocalAcessivelDB(Base):
    __tablename__ = "locais_acessiveis"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    municipio = Column(String, nullable=False, index=True)
    endereco = Column(String, nullable=False)
    tipo = Column(String, nullable=False, index=True)
    recursos_acessibilidade = Column(JSON, default=list)
    observacoes = Column(String, nullable=True)
    reportado_por = Column(String, nullable=True)
    verificado = Column(Boolean, default=False)


class UsuarioDB(Base):
    """Conta da pessoa usuária. Os dados socioeconômicos só existem para a análise agregada da extensão
    (ver o termo de consentimento no cadastro); nenhum deles é obrigatório para usar o chat sem conta."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    senha_hash = Column(String, nullable=True)   # nulo quando a conta só tem login via Google
    google_sub = Column(String, nullable=True, unique=True)  # id estável da conta Google, se usada

    nome_completo = Column(String, nullable=False)
    ano_nascimento = Column(Integer, nullable=True)
    sexo = Column(String, nullable=True)
    etnia = Column(String, nullable=True)
    cpf_rg = Column(String, nullable=True)
    estado = Column(String, nullable=True)
    cidade = Column(String, nullable=True)
    endereco = Column(String, nullable=True)
    grau_escolaridade = Column(String, nullable=True)
    integrantes_familia = Column(Integer, nullable=True)
    renda_faixa = Column(String, nullable=True)
    renda_familiar_faixa = Column(String, nullable=True)
    condicoes_acessibilidade = Column(JSON, default=list)  # lista de códigos (ver CONDICOES_ACESSIBILIDADE)

    consentimento_lgpd_em = Column(DateTime, nullable=True)
    consentimento_lgpd_versao = Column(String, nullable=True)

    email_verificado = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.datetime.utcnow)

    tokens = relationship("TokenContaDB", back_populates="usuario", cascade="all, delete-orphan")


class TokenContaDB(Base):
    """Token de uso único para confirmar e-mail ou redefinir senha (enviado por e-mail, nunca mostrado na tela)."""
    __tablename__ = "tokens_conta"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    tipo = Column(String, nullable=False)  # "verificar_email" | "redefinir_senha"
    expira_em = Column(DateTime, nullable=False)
    usado = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.datetime.utcnow)

    usuario = relationship("UsuarioDB", back_populates="tokens")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
