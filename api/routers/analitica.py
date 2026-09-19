"""
Router: /analitica – cómo van los costos, gastos e ingresos según los documentos
electrónicos DIAN ya causados.

El alcance depende de quién pregunta, sin endpoints separados:
  · causador  → sus propias empresas
  · admin     → todas las empresas de la cuenta (la mirada global de lo que
                causa cada uno de sus usuarios)

Con `empresa_id` se acota a una sola, siempre dentro de lo que ese usuario
puede ver: si pide una empresa ajena, no se le devuelve nada de ella.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from db.models.auth import Empresa, Usuario
from db.session import get_db
from services import analitica_service

router = APIRouter(prefix="/analitica", tags=["Analítica"])

DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


def _parse_rango(desde: str | None, hasta: str | None) -> tuple[date, date]:
    """Rango del informe. Por defecto: el año en curso (una serie mensual de un
    solo mes no dice nada)."""
    hoy = date.today()
    try:
        d = date.fromisoformat(desde) if desde else date(hoy.year, 1, 1)
    except ValueError:
        d = date(hoy.year, 1, 1)
    try:
        h = date.fromisoformat(hasta) if hasta else hoy
    except ValueError:
        h = hoy
    if h < d:
        d, h = h, d
    return d, h


@router.get("/resumen")
def resumen(
    db: DB,
    current_user: CurrentUser,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: int | None = None,
    campo_fecha: str | None = None,
):
    d, h = _parse_rango(desde, hasta)
    visibles = analitica_service.empresas_visibles(db, current_user, current_user.cuenta_id)

    if empresa_id is not None:
        if empresa_id not in visibles:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        visibles = [empresa_id]

    datos = analitica_service.resumen(
        db, empresa_ids=visibles, desde=d, hasta=h, campo_fecha=campo_fecha
    )
    es_admin = current_user.rol in ("org_admin", "admin")
    return {
        "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
        "campo_fecha": "emision" if campo_fecha == "emision" else "causacion",
        "alcance": "cuenta" if es_admin and empresa_id is None else "empresa",
        "empresas": len(visibles),
        **datos,
    }


@router.get("/empresas")
def empresas(db: DB, current_user: CurrentUser):
    """Empresas que este usuario puede filtrar en la analítica."""
    ids = analitica_service.empresas_visibles(db, current_user, current_user.cuenta_id)
    if not ids:
        return []
    filas = db.execute(
        select(Empresa.id, Empresa.nombre, Empresa.nit)
        .where(Empresa.id.in_(ids), Empresa.activa.is_(True))
        .order_by(Empresa.nombre)
    ).all()
    return [{"id": i, "nombre": n, "nit": nit} for (i, n, nit) in filas]
