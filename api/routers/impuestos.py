"""
Router: /impuestos – CRUD sobre códigos de impuesto SIIGO.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import ImpuestoCreate, ImpuestoOut
from db.session import get_db
from services import impuestos_service

router = APIRouter(prefix="/impuestos", tags=["Códigos de Impuesto"])

DB = Annotated[Session, Depends(get_db)]


@router.get("/", response_model=list[ImpuestoOut])
def get_impuestos(db: DB):
    return impuestos_service.listar_todos(db)


@router.get("/{codigo}", response_model=ImpuestoOut)
def get_impuesto(codigo: str, db: DB):
    imp = impuestos_service.buscar_por_codigo(db, codigo)
    if not imp:
        raise HTTPException(404, f"Impuesto {codigo!r} no encontrado")
    return imp


@router.post("/", response_model=ImpuestoOut, status_code=201)
def post_impuesto(body: ImpuestoCreate, db: DB):
    if impuestos_service.buscar_por_codigo(db, body.codigo):
        raise HTTPException(409, f"El código {body.codigo!r} ya existe")
    imp = impuestos_service.crear_impuesto(db, **body.model_dump())
    db.commit()
    return imp


# Los registros del catálogo son de solo lectura; no se expone PATCH ni DELETE.
