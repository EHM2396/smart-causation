"""
Router: /aprendizaje – reglas de clasificación e historial de decisiones.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import DecisionOut, ReglaCreate, ReglaOut
from db.models.aprendizaje import HistorialDecision, ReglaClasificacion
from db.session import get_db
from services import aprendizaje_service

router = APIRouter(prefix="/aprendizaje", tags=["Aprendizaje"])

DB = Annotated[Session, Depends(get_db)]


# ── Reglas de clasificación ────────────────────────────────────────────────────

@router.get("/reglas", response_model=list[ReglaOut])
def get_reglas(db: DB, solo_activas: bool = True):
    stmt = select(ReglaClasificacion).order_by(
        ReglaClasificacion.prioridad.desc()
    )
    if solo_activas:
        stmt = stmt.where(ReglaClasificacion.activa == True)
    return db.scalars(stmt).all()


@router.post("/reglas", response_model=ReglaOut, status_code=201)
def post_regla(body: ReglaCreate, db: DB):
    regla = aprendizaje_service.crear_regla(db, **body.model_dump())
    db.commit()
    return regla


# ── Historial de decisiones ────────────────────────────────────────────────────

@router.get("/historial", response_model=list[DecisionOut])
def get_historial(
    db: DB,
    nit: Annotated[str | None, Query()] = None,
    solo_corregidas: bool = False,
    limit: int = 100,
):
    stmt = (
        select(HistorialDecision)
        .order_by(HistorialDecision.created_at.desc())
        .limit(limit)
    )
    if nit:
        stmt = stmt.where(HistorialDecision.nit_proveedor == nit)
    if solo_corregidas:
        stmt = stmt.where(HistorialDecision.fue_corregida == True)
    return db.scalars(stmt).all()
