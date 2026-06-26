"""
ConsecutivosService – gestiona los consecutivos por prefijo de comprobante.
Reemplaza db/memory.py: get/set_ultimo_consecutivo().
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.contabilidad import Consecutivo


def get_ultimo(db: Session, prefijo: str, empresa_id: int | None = None) -> int:
    stmt = select(Consecutivo).where(Consecutivo.prefijo == prefijo.upper())
    if empresa_id is not None:
        stmt = stmt.where(Consecutivo.empresa_id == empresa_id)
    else:
        stmt = stmt.where(Consecutivo.empresa_id.is_(None))
    row = db.scalar(stmt)
    return row.ultimo_num if row else 0


def set_ultimo(db: Session, prefijo: str, numero: int, empresa_id: int | None = None) -> None:
    stmt = select(Consecutivo).where(Consecutivo.prefijo == prefijo.upper())
    if empresa_id is not None:
        stmt = stmt.where(Consecutivo.empresa_id == empresa_id)
    else:
        stmt = stmt.where(Consecutivo.empresa_id.is_(None))
    row = db.scalar(stmt)
    if row:
        row.ultimo_num = numero
    else:
        db.add(Consecutivo(prefijo=prefijo.upper(), ultimo_num=numero, empresa_id=empresa_id))
    db.flush()


def siguiente(db: Session, prefijo: str, empresa_id: int | None = None) -> int:
    """Incrementa y retorna el próximo consecutivo (atómico dentro de la sesión)."""
    actual = get_ultimo(db, prefijo, empresa_id=empresa_id)
    nuevo = actual + 1
    set_ultimo(db, prefijo, nuevo, empresa_id=empresa_id)
    return nuevo
