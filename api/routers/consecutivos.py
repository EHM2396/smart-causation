"""
Router: /consecutivos – consulta y ajuste del último consecutivo por tipo de comprobante.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from services import consecutivos_service

router = APIRouter(prefix="/consecutivos", tags=["Consecutivos"])

DB = Annotated[Session, Depends(get_db)]


class ConsecutivoOut(BaseModel):
    tipo_comp: str
    ultimo: int
    proximo: int


class ConsecutivoSetBody(BaseModel):
    nuevo_valor: int


@router.get("/{tipo_comp}", response_model=ConsecutivoOut)
def get_consecutivo(tipo_comp: str, db: DB):
    """Retorna el último consecutivo registrado y el próximo a usar."""
    ultimo = consecutivos_service.get_ultimo(db, tipo_comp)
    return ConsecutivoOut(tipo_comp=tipo_comp.upper(), ultimo=ultimo, proximo=ultimo + 1)


@router.put("/{tipo_comp}", response_model=ConsecutivoOut)
def set_consecutivo(tipo_comp: str, body: ConsecutivoSetBody, db: DB):
    """
    Ajusta el consecutivo manualmente.
    `nuevo_valor` es el **próximo** número que se usará (se guarda como nuevo_valor - 1).
    """
    consecutivos_service.set_ultimo(db, tipo_comp, body.nuevo_valor - 1)
    db.commit()
    ultimo = consecutivos_service.get_ultimo(db, tipo_comp)
    return ConsecutivoOut(tipo_comp=tipo_comp.upper(), ultimo=ultimo, proximo=ultimo + 1)
