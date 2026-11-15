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
    bairro = Column(String, nullable=True)
    endereco = Column(String, nullable=False)
    tipo = Column(String, nullable=False, index=True)
    recursos_acessibilidade = Column(JSON, default=list)
    telefones = Column(JSON, default=list)
    horario_funcionamento = Column(String, nullable=True)
    observacoes = Column(String, nullable=True)
    reportado_por = Column(String, nullable=True)
    verificado = Column(Boolean, default=False)
    fonte_url = Column(String, nullable=True)
    verificado_em = Column(String, nullable=True)  # data (ex.: "2026-11-08"), não a sessão de login


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
    conversas = relationship("ConversaDB", back_populates="usuario", cascade="all, delete-orphan")


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


class ConversaDB(Base):
    """Histórico de chat — só existe para quem está logado (ver app/routers/chat.py). Sem conta, o chat
    continua funcionando normalmente e nada é gravado."""
    __tablename__ = "conversas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    titulo = Column(String, nullable=False)
    roteiro_final = Column(JSON, nullable=True)  # último roteiro (RoteiroOut) devolvido nesta conversa
    criada_em = Column(DateTime, default=datetime.datetime.utcnow)
    atualizada_em = Column(DateTime, default=datetime.datetime.utcnow)

    usuario = relationship("UsuarioDB", back_populates="conversas")
    mensagens = relationship(
        "MensagemConversaDB", back_populates="conversa", cascade="all, delete-orphan",
        order_by="MensagemConversaDB.id",
    )


class MensagemConversaDB(Base):
    __tablename__ = "mensagens_conversa"

    id = Column(Integer, primary_key=True, index=True)
    conversa_id = Column(Integer, ForeignKey("conversas.id"), nullable=False, index=True)
    papel = Column(String, nullable=False)  # "usuario" | "assistente"
    conteudo = Column(String, nullable=False)
    criada_em = Column(DateTime, default=datetime.datetime.utcnow)

    conversa = relationship("ConversaDB", back_populates="mensagens")


def _adicionar_colunas_novas() -> None:
    """create_all() só cria tabela que não existe; se o arquivo .db já existia antes de uma coluna
    ser adicionada ao modelo acima, ela precisa entrar "na mão" — o SQLite aceita ADD COLUMN simples."""
    colunas_novas = {
        "locais_acessiveis": {
            "bairro": "VARCHAR", "telefones": "JSON", "horario_funcionamento": "VARCHAR",
            "fonte_url": "VARCHAR", "verificado_em": "VARCHAR",
        },
    }
    with engine.connect() as conn:
        for tabela, colunas in colunas_novas.items():
            existentes = {linha[1] for linha in conn.exec_driver_sql(f"PRAGMA table_info({tabela})")}
            if not existentes:
                continue  # tabela ainda não existe: create_all() já vai criá-la completa
            for nome, tipo in colunas.items():
                if nome not in existentes:
                    conn.exec_driver_sql(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")
        conn.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _adicionar_colunas_novas()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
