from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import LocalAcessivelDB, get_db
from app.models.schemas import LocalAcessivelCreate, LocalAcessivelOut

router = APIRouter(prefix="/locais", tags=["locais-acessiveis"])


@router.post("", response_model=LocalAcessivelOut)
def cadastrar_local(payload: LocalAcessivelCreate, db: Session = Depends(get_db)) -> LocalAcessivelDB:
    novo_local = LocalAcessivelDB(**payload.model_dump(), verificado=False)
    db.add(novo_local)
    db.commit()
    db.refresh(novo_local)
    return novo_local


@router.get("", response_model=list[LocalAcessivelOut])
def listar_locais(
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    apenas_verificados: bool = False,
    db: Session = Depends(get_db),
) -> list[LocalAcessivelDB]:
    query = db.query(LocalAcessivelDB)
    if municipio:
        query = query.filter(LocalAcessivelDB.municipio.ilike(municipio))
    if tipo:
        query = query.filter(LocalAcessivelDB.tipo == tipo)
    if apenas_verificados:
        query = query.filter(LocalAcessivelDB.verificado.is_(True))
    return query.all()


@router.patch("/{local_id}/verificar", response_model=LocalAcessivelOut)
def verificar_local(local_id: int, db: Session = Depends(get_db)) -> LocalAcessivelDB:
    local = db.query(LocalAcessivelDB).filter(LocalAcessivelDB.id == local_id).first()
    if local is None:
        raise HTTPException(status_code=404, detail="Local não encontrado")
    local.verificado = True
    db.commit()
    db.refresh(local)
    return local
