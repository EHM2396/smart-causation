"""
Router: /formulario-300 – clasificación tributaria de las operaciones a tarifa
0%, previo al reporte del Formulario 300.

Por ahora es SOLO para el administrador de la cuenta (Dayana, en el caso de
Salamanca): es la pantalla donde se toman decisiones de clasificación
tributaria compartidas por toda la firma, y la restricción evita que un
causador clasifique algo sin que quien lleva impuestos lo haya visto. Abrirlo
a causadores más adelante es cambiar una dependencia, no rehacer el módulo.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from db.models.auth import CuentaCliente, Empresa, Usuario
from db.models.tributario import TRATAMIENTOS
from db.session import get_db
from services import formulario_300_service as f300

router = APIRouter(prefix="/formulario-300", tags=["Formulario 300"])

DB = Annotated[Session, Depends(get_db)]


def require_org_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if current_user.rol not in ("org_admin", "admin"):
        raise HTTPException(status_code=403, detail="Requiere permisos de administrador de la cuenta")
    return current_user


OrgAdmin = Annotated[Usuario, Depends(require_org_admin)]


def _cuenta_de(db: Session, user: Usuario) -> CuentaCliente:
    if not user.cuenta_id:
        raise HTTPException(status_code=400, detail="Tu usuario no está asociado a una cuenta")
    cuenta = db.get(CuentaCliente, user.cuenta_id)
    if cuenta is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return cuenta


def _empresas_de_cuenta(db: Session, cuenta_id: int) -> list[int]:
    return list(db.scalars(
        select(Empresa.id).where(Empresa.cuenta_id == cuenta_id, Empresa.activa.is_(True))
    ).all())


def _parse_rango(desde: str | None, hasta: str | None) -> tuple[date, date]:
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


@router.get("/proveedores")
def proveedores(
    db: DB,
    admin: OrgAdmin,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: int | None = None,
    tarifa: float = 0.0,
):
    """Proveedores con operaciones a la tarifa dada, con su concepto
    predominante y los secundarios, cada uno con su clasificación actual."""
    cuenta = _cuenta_de(db, admin)
    d, h = _parse_rango(desde, hasta)
    empresas = _empresas_de_cuenta(db, cuenta.id)

    if empresa_id is not None:
        if empresa_id not in empresas:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        empresas = [empresa_id]

    if not empresas:
        return {"periodo": {"desde": d.isoformat(), "hasta": h.isoformat()}, "proveedores": []}

    resultado = f300.resumen_por_proveedor(
        db, empresa_ids=empresas, desde=d, hasta=h, tarifa=tarifa, cuenta_id=cuenta.id,
    )

    def _concepto(c) -> dict:
        return {
            "concepto": c.concepto,
            "nit_proveedor": c.nit_proveedor,
            "base_acumulada": c.base_acumulada,
            "documentos": c.documentos,
            "participacion": c.participacion,
            "tratamiento": c.clasificacion.tratamiento,
            "estado": c.clasificacion.estado,
            "origen": c.clasificacion.origen,
            "requiere_revision": c.clasificacion.requiere_revision,
            "es_excepcion": c.clasificacion.es_excepcion,
            "articulo_et": c.clasificacion.articulo_et,
            "norma": c.clasificacion.norma,
        }

    return {
        "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
        "tarifa": tarifa,
        "proveedores": [
            {
                "nit": p.nit,
                "razon_social": p.razon_social,
                "base_total": p.base_total,
                "documentos": p.documentos,
                "pendientes": p.pendientes,
                "predominante": _concepto(p.predominante),
                "secundarios": [_concepto(c) for c in p.secundarios],
            }
            for p in resultado
        ],
    }


class ClasificarRequest(BaseModel):
    empresa_id: int
    concepto: str = Field(..., min_length=1)
    tratamiento: str
    # Con NIT: la decisión solo vale para ese proveedor (queda como excepción,
    # no se comparte). Sin NIT: es una regla general del concepto y se propone
    # también a las demás empresas de la firma.
    nit_tercero: str | None = None
    articulo_et: str | None = None
    norma: str | None = None


@router.post("/clasificar")
def clasificar_endpoint(body: ClasificarRequest, db: DB, admin: OrgAdmin):
    cuenta = _cuenta_de(db, admin)
    empresa = db.get(Empresa, body.empresa_id)
    if empresa is None or empresa.cuenta_id != cuenta.id:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if body.tratamiento not in TRATAMIENTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tratamiento inválido. Debe ser uno de: {', '.join(TRATAMIENTOS)}",
        )

    fila = f300.validar_clasificacion(
        db, empresa=empresa, usuario=admin, concepto=body.concepto,
        tratamiento=body.tratamiento, nit_tercero=body.nit_tercero,
        articulo_et=body.articulo_et, norma=body.norma,
    )
    return {
        "id": fila.id, "concepto": fila.concepto, "tratamiento": fila.tratamiento,
        "estado": fila.estado, "es_excepcion": fila.es_excepcion,
    }
