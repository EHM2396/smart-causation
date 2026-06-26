"""
TiposComprobanteService – consultas sobre tipos de comprobante contable SIIGO.
Todas las queries filtran por empresa_id (None = sin filtro, para compat. con Streamlit).
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.catalogo import TipoComprobante


def listar_todos(db: Session, empresa_id: int | None = None) -> Sequence[TipoComprobante]:
    stmt = select(TipoComprobante).where(TipoComprobante.activo == True).order_by(TipoComprobante.codigo)
    if empresa_id is not None:
        stmt = stmt.where(TipoComprobante.empresa_id == empresa_id)
    return db.scalars(stmt).all()


def buscar_por_codigo(db: Session, codigo: str, empresa_id: int | None = None) -> TipoComprobante | None:
    stmt = select(TipoComprobante).where(TipoComprobante.codigo == codigo.strip())
    if empresa_id is not None:
        stmt = stmt.where(TipoComprobante.empresa_id == empresa_id)
    return db.scalar(stmt)


def listar_como_opciones(db: Session, empresa_id: int | None = None) -> list[dict]:
    return [
        {
            "codigo": t.codigo,
            "titulo": t.titulo,
            "label":  f"{t.codigo} – {t.titulo}",
        }
        for t in listar_todos(db, empresa_id=empresa_id)
    ]


def crear_tipo(db: Session, *, codigo: str, titulo: str, empresa_id: int | None = None) -> TipoComprobante:
    tipo = TipoComprobante(codigo=codigo.strip(), titulo=titulo.strip(), empresa_id=empresa_id)
    db.add(tipo)
    db.flush()
    return tipo


def upsert_tipo(db: Session, *, codigo: str, titulo: str, empresa_id: int) -> tuple[TipoComprobante, bool]:
    """Inserta o actualiza un tipo por (codigo, empresa_id). Retorna (objeto, creado)."""
    existing = buscar_por_codigo(db, codigo, empresa_id=empresa_id)
    if existing:
        existing.titulo = titulo.strip()
        db.flush()
        return existing, False
    return crear_tipo(db, codigo=codigo, titulo=titulo, empresa_id=empresa_id), True
