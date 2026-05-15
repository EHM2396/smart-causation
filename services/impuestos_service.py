"""
ImpuestosService – consultas sobre códigos de impuesto SIIGO.

Reemplaza las funciones de core/mapper.py que leían codigos_impuestos.xlsx.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.catalogo import CodigoImpuesto


# ── Consultas ─────────────────────────────────────────────────────────────────

def listar_todos(db: Session) -> Sequence[CodigoImpuesto]:
    """Retorna todos los códigos activos."""
    return db.scalars(
        select(CodigoImpuesto).where(CodigoImpuesto.activo == True)
    ).all()


def buscar_por_codigo(db: Session, codigo: str) -> CodigoImpuesto | None:
    return db.scalar(
        select(CodigoImpuesto).where(CodigoImpuesto.codigo == codigo.strip())
    )


def buscar_por_tarifa(db: Session, tarifa: float) -> CodigoImpuesto | None:
    """
    Busca el impuesto de tipo IVA o Impoconsumo cuya tarifa coincida
    con el porcentaje dado (tolerancia ±0.5).
    Útil para inferir el código a partir del porcentaje del XML DIAN.
    """
    candidatos = db.scalars(
        select(CodigoImpuesto).where(
            CodigoImpuesto.activo == True,
            CodigoImpuesto.tarifa.between(tarifa - 0.5, tarifa + 0.5),
        )
    ).all()

    # Preferir IVA sobre otros tipos
    for imp in candidatos:
        if imp.tipo_impuesto and "iva" in imp.tipo_impuesto.lower():
            return imp
    return candidatos[0] if candidatos else None


def listar_como_dict(db: Session) -> list[dict]:
    """
    Retorna lista de dicts compatible con la UI y con core.mapper.listar_impuestos().
    Equivalente a core.mapper.listar_impuestos().
    """
    return [
        {
            "cod":            imp.codigo,
            "porcentaje":     float(imp.tarifa or 0),
            "cuenta_debito":  imp.cuenta_debito,
            "cuenta_credito": imp.cuenta_credito,
            "naturaleza":     imp.tipo_impuesto or "",
        }
        for imp in listar_todos(db)
    ]


def buscar_como_dict(db: Session, codigo: str) -> dict | None:
    """
    Retorna dict compatible con core.mapper.buscar_impuesto().
    Equivalente directo para sustituir el mapper.
    """
    imp = buscar_por_codigo(db, codigo)
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

def crear_impuesto(db: Session, **campos) -> CodigoImpuesto:
    imp = CodigoImpuesto(**campos)
    db.add(imp)
    db.flush()
    return imp


def actualizar_impuesto(db: Session, codigo: str, **campos) -> CodigoImpuesto | None:
    imp = buscar_por_codigo(db, codigo)
    if not imp:
        return None
    for k, v in campos.items():
        if hasattr(imp, k):
            setattr(imp, k, v)
    db.flush()
    return imp
