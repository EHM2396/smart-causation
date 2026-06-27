"""
ImpuestosService – consultas sobre códigos de impuesto SIIGO.
Todas las queries filtran por empresa_id (None = sin filtro, para compat. con Streamlit).
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.catalogo import CodigoImpuesto


# ── Consultas ─────────────────────────────────────────────────────────────────

def listar_todos(db: Session, empresa_id: int | None = None) -> Sequence[CodigoImpuesto]:
    stmt = select(CodigoImpuesto).where(CodigoImpuesto.activo == True)
    if empresa_id is not None:
        stmt = stmt.where(CodigoImpuesto.empresa_id == empresa_id)
    return db.scalars(stmt).all()


def buscar_por_codigo(db: Session, codigo: str, empresa_id: int | None = None) -> CodigoImpuesto | None:
    stmt = select(CodigoImpuesto).where(CodigoImpuesto.codigo == codigo.strip())
    if empresa_id is not None:
        stmt = stmt.where(CodigoImpuesto.empresa_id == empresa_id)
    return db.scalar(stmt)


def buscar_por_tarifa(db: Session, tarifa: float, empresa_id: int | None = None) -> CodigoImpuesto | None:
    stmt = select(CodigoImpuesto).where(
        CodigoImpuesto.activo == True,
        CodigoImpuesto.tarifa.between(tarifa - 0.5, tarifa + 0.5),
    )
    if empresa_id is not None:
        stmt = stmt.where(CodigoImpuesto.empresa_id == empresa_id)
    candidatos = db.scalars(stmt).all()

    for imp in candidatos:
        if imp.tipo_impuesto and "iva" in imp.tipo_impuesto.lower():
            return imp
    return candidatos[0] if candidatos else None


def listar_como_dict(db: Session, empresa_id: int | None = None) -> list[dict]:
    return [
        {
            "cod":            imp.codigo,
            "porcentaje":     float(imp.tarifa or 0),
            "cuenta_debito":  imp.cuenta_debito,
            "cuenta_credito": imp.cuenta_credito,
            "naturaleza":     imp.tipo_impuesto or "",
        }
        for imp in listar_todos(db, empresa_id=empresa_id)
    ]


def buscar_como_dict(db: Session, codigo: str, empresa_id: int | None = None) -> dict | None:
    imp = buscar_por_codigo(db, codigo, empresa_id=empresa_id)
    if not imp:
        return None
    return {
        "cod":            imp.codigo,
        "porcentaje":     float(imp.tarifa or 0),
        "cuenta_debito":  imp.cuenta_debito,
        "cuenta_credito": imp.cuenta_credito,
        "naturaleza":     imp.tipo_impuesto or "",
    }


# ── CRUD ─────────────────────────────────────────────────────────────────────

def crear_impuesto(db: Session, empresa_id: int | None = None, **campos) -> CodigoImpuesto:
    imp = CodigoImpuesto(empresa_id=empresa_id, **campos)
    db.add(imp)
    db.flush()
    return imp


def upsert_impuesto(db: Session, empresa_id: int, **campos) -> tuple[CodigoImpuesto, bool]:
    """Inserta o actualiza un impuesto por (codigo, empresa_id). Retorna (objeto, creado).
    Si existe pero estaba inactivo (soft-deleted), lo reactiva.
    """
    codigo = str(campos.get("codigo", "")).strip()
    existing = buscar_por_codigo(db, codigo, empresa_id=empresa_id)
    if existing:
        creado = not existing.activo
        for k, v in campos.items():
            if k != "codigo" and hasattr(existing, k) and v not in (None, ""):
                setattr(existing, k, v)
        existing.activo = True
        db.flush()
        return existing, creado
    imp = CodigoImpuesto(empresa_id=empresa_id, **campos)
    db.add(imp)
    db.flush()
    return imp, True


def actualizar_impuesto(db: Session, codigo: str, empresa_id: int | None = None, **campos) -> CodigoImpuesto | None:
    imp = buscar_por_codigo(db, codigo, empresa_id=empresa_id)
    if not imp:
        return None
    for k, v in campos.items():
        if hasattr(imp, k):
            setattr(imp, k, v)
    db.flush()
    return imp
