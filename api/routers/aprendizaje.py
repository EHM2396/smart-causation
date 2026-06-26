"""
Router: /aprendizaje – reglas de clasificación e historial de decisiones.
Requiere autenticación; el historial filtra por empresa activa.
Las reglas de clasificación son globales (definidas por el admin de la plataforma).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_empresa_activa
from api.schemas import DecisionOut, ReglaCreate, ReglaOut
from db.models.aprendizaje import HistorialDecision, ReglaClasificacion
from db.models.auth import Empresa, Usuario
from db.session import get_db
from services import aprendizaje_service

router = APIRouter(prefix="/aprendizaje", tags=["Aprendizaje"])

DB = Annotated[Session, Depends(get_db)]
EmpresaActiva = Annotated[Empresa, Depends(get_empresa_activa)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


# ── Reglas de clasificación (globales, visibles por todos) ─────────────────────

@router.get("/reglas", response_model=list[ReglaOut])
def get_reglas(db: DB, _user: CurrentUser, solo_activas: bool = True):
    stmt = select(ReglaClasificacion).order_by(ReglaClasificacion.prioridad.desc())
    if solo_activas:
        stmt = stmt.where(ReglaClasificacion.activa == True)
    return db.scalars(stmt).all()


@router.post("/reglas", response_model=ReglaOut, status_code=201)
def post_regla(body: ReglaCreate, db: DB, _user: CurrentUser):
    regla = aprendizaje_service.crear_regla(db, **body.model_dump())
    db.commit()
    return regla


# ── Historial de decisiones (por empresa) ─────────────────────────────────────

@router.get("/historial", response_model=list[DecisionOut])
def get_historial(
    db: DB,
    empresa: EmpresaActiva,
    current_user: CurrentUser,
    nit: Annotated[str | None, Query()] = None,
    solo_corregidas: bool = False,
    limit: int = 100,
):
    stmt = (
        select(HistorialDecision)
        .where(
            HistorialDecision.empresa_id == empresa.id,
            HistorialDecision.usuario_id == current_user.id,
        )
        .order_by(HistorialDecision.created_at.desc())
        .limit(limit)
    )
    if nit:
        stmt = stmt.where(HistorialDecision.nit_proveedor == nit)
    if solo_corregidas:
        stmt = stmt.where(HistorialDecision.fue_corregida == True)
    return db.scalars(stmt).all()
