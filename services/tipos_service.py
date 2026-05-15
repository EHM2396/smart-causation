"""
TiposComprobanteService – consultas sobre tipos de comprobante contable SIIGO.

Reemplaza las funciones de core/mapper.py que leían Tipos_comprobante_contable.xlsx.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.catalogo import TipoComprobante


def listar_todos(db: Session) -> Sequence[TipoComprobante]:
    return db.scalars(
        select(TipoComprobante)
        .where(TipoComprobante.activo == True)
        .order_by(TipoComprobante.codigo)
    ).all()


def buscar_por_codigo(db: Session, codigo: str) -> TipoComprobante | None:
    return db.scalar(
        select(TipoComprobante).where(TipoComprobante.codigo == codigo.strip())
    )


def listar_como_opciones(db: Session) -> list[dict]:
    """Retorna lista [{codigo, titulo, label}] para selectbox en la UI."""
    return [
        {
            "codigo": t.codigo,
            "titulo": t.titulo,
            "label":  f"{t.codigo} – {t.titulo}",
        }
        for t in listar_todos(db)
    ]


def crear_tipo(db: Session, *, codigo: str, titulo: str) -> TipoComprobante:
    tipo = TipoComprobante(codigo=codigo.strip(), titulo=titulo.strip())
    db.add(tipo)
    db.flush()
    return tipo
