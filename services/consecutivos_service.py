"""
ConsecutivosService – gestiona los consecutivos por prefijo de comprobante.
Reemplaza db/memory.py: get/set_ultimo_consecutivo().
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.contabilidad import Consecutivo


def get_ultimo(db: Session, prefijo: str) -> int:
    row = db.scalar(
        select(Consecutivo).where(Consecutivo.prefijo == prefijo.upper())
    )
    return row.ultimo_num if row else 0


def set_ultimo(db: Session, prefijo: str, numero: int) -> None:
    row = db.scalar(
        select(Consecutivo).where(Consecutivo.prefijo == prefijo.upper())
    )
    if row:
        row.ultimo_num = numero
    else:
        db.add(Consecutivo(prefijo=prefijo.upper(), ultimo_num=numero))
    db.flush()


def siguiente(db: Session, prefijo: str) -> int:
    """Incrementa y retorna el próximo consecutivo (atómico dentro de la sesión)."""
    actual = get_ultimo(db, prefijo)
    nuevo = actual + 1
    set_ultimo(db, prefijo, nuevo)
    return nuevo
