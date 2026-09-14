from sqlalchemy import create_engine, Column, Integer, String, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
