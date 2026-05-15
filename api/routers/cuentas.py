"""
Router: /cuentas – CRUD sobre el plan de cuentas PUC.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas import CuentaCreate, CuentaOpcion, CuentaOut
from db.session import get_db
from services import cuentas_service

router = APIRouter(prefix="/cuentas", tags=["Cuentas Contables"])

DB = Annotated[Session, Depends(get_db)]


@router.get("/gasto", response_model=list[CuentaOpcion])
def get_cuentas_gasto(db: DB):
    """Cuentas de gastos y costos (clases 5/6/7, 8 dígitos, sin fiscal)."""
    return cuentas_service.listar_cuentas_gasto(db)


@router.get("/pago", response_model=list[CuentaOpcion])
def get_metodos_pago(db: DB):
    """Cuentas de activo/pasivo (clases 1/2, 8 dígitos, sin fiscal)."""
    return cuentas_service.listar_metodos_pago(db)


@router.get("/sugerencias", response_model=list[dict])
def get_sugerencias(
    descripcion: Annotated[str, Query(min_length=3)],
    db: DB,
    max: int = 3,
):
    """Busca cuentas PUC por palabras clave en la descripción del ítem."""
    return cuentas_service.buscar_cuentas_sugeridas(db, descripcion, max)


@router.get("/{codigo}", response_model=CuentaOut)
def get_cuenta(codigo: str, db: DB):
    cuenta = cuentas_service.buscar_por_codigo(db, codigo)
    if not cuenta:
        raise HTTPException(404, f"Cuenta {codigo!r} no encontrada")
    return cuenta


@router.post("/", response_model=CuentaOut, status_code=201)
def post_cuenta(body: CuentaCreate, db: DB):
    if cuentas_service.buscar_por_codigo(db, body.codigo):
        raise HTTPException(409, f"El código {body.codigo!r} ya existe")
    cuenta = cuentas_service.crear_cuenta(
        db,
        codigo=body.codigo,
        nombre=body.nombre,
        fiscal=body.fiscal,
    )
    db.commit()
    return cuenta


# Los registros del catálogo son de solo lectura; no se expone PATCH ni DELETE.
