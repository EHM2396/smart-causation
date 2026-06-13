"""
Router: /tipos-comprobante – gestión de tipos de comprobante contable.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import TipoComprobanteCreate, TipoComprobanteOut
from api.deps import AuthUser
from db.session import get_db
from services import tipos_service

router = APIRouter(prefix="/tipos-comprobante", tags=["Tipos de Comprobante"])

DB = Annotated[Session, Depends(get_db)]


@router.get("/", response_model=list[TipoComprobanteOut])
def get_tipos(db: DB, user: AuthUser):
    return tipos_service.listar_todos(db)


@router.get("/opciones", response_model=list[dict])
def get_opciones(db: DB, user: AuthUser):
    """Formato compacto {codigo, titulo, label} para la UI."""
    return tipos_service.listar_como_opciones(db)


@router.post("/", response_model=TipoComprobanteOut, status_code=201)
def post_tipo(body: TipoComprobanteCreate, db: DB):
    if tipos_service.buscar_por_codigo(db, body.codigo):
        raise HTTPException(409, f"El código {body.codigo!r} ya existe")
    tipo = tipos_service.crear_tipo(db, codigo=body.codigo, titulo=body.titulo)
    db.commit()
    return tipo
