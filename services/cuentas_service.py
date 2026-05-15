"""
CuentasService – todas las consultas sobre el plan de cuentas PUC.

Reemplaza las funciones de core/mapper.py que leían Cuentas_contables.xlsx.
Recibe una sesión SQLAlchemy; nunca abre conexión propia.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.catalogo import CuentaContable


def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto).lower())
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", sin_acentos).strip()


# ── Consultas base ─────────────────────────────────────────────────────────────

def listar_todas(db: Session) -> Sequence[CuentaContable]:
    """Retorna todas las cuentas activas."""
    return db.scalars(
        select(CuentaContable).where(CuentaContable.activo == True)
    ).all()


def buscar_por_codigo(db: Session, codigo: str) -> CuentaContable | None:
    return db.scalar(
        select(CuentaContable).where(CuentaContable.codigo == codigo.strip())
    )


# ── Selectores para la UI ─────────────────────────────────────────────────────

def listar_cuentas_gasto(db: Session) -> list[dict]:
    """
    Cuentas de gastos y costos (clases 5, 6, 7) de nivel auxiliar (8 dígitos).
    Excluye las marcadas como fiscales.
    Equivalente a core.mapper.listar_cuentas_gasto().
    """
    rows = db.scalars(
        select(CuentaContable).where(
            CuentaContable.activo == True,
            CuentaContable.nivel == 8,
            CuentaContable.clase.in_([5, 6, 7]),
            CuentaContable.fiscal == False,
        )
    ).all()

    return [
        {"codigo": r.codigo, "nombre": r.nombre, "label": f"{r.codigo} – {r.nombre}"}
        for r in rows
    ]


def listar_metodos_pago(db: Session) -> list[dict]:
    """
    Cuentas de activo/pasivo (clases 1, 2) de nivel auxiliar (8 dígitos).
    Se usan para registrar el método de pago / cuenta por pagar del proveedor.
    Equivalente a core.mapper.listar_metodos_pago().
    """
    rows = db.scalars(
        select(CuentaContable).where(
            CuentaContable.activo == True,
            CuentaContable.nivel == 8,
            CuentaContable.clase.in_([1, 2]),
            CuentaContable.fiscal == False,
        )
    ).all()

    return [
        {"codigo": r.codigo, "nombre": r.nombre, "label": f"{r.codigo} – {r.nombre}"}
        for r in rows
    ]


def buscar_cuentas_sugeridas(
    db: Session, descripcion: str, max_sugerencias: int = 3
) -> list[dict]:
    """
    Busca en el PUC cuentas cuyo nombre contenga palabras de la descripción.
    Retorna lista ordenada por relevancia.
    Equivalente a core.mapper.buscar_cuentas_sugeridas().
    """
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]
    if not palabras:
        return []

    todas = db.scalars(
        select(CuentaContable).where(
            CuentaContable.activo == True,
            CuentaContable.nivel == 8,
        )
    ).all()

    scored = []
    for cuenta in todas:
        nombre_n = _norm(cuenta.nombre)
        score = sum(1 for p in palabras if p in nombre_n)
        if score > 0:
            scored.append({"codigo": cuenta.codigo, "nombre": cuenta.nombre, "score": score})

    scored.sort(key=lambda x: -x["score"])
    return scored[:max_sugerencias]


# ── CRUD ─────────────────────────────────────────────────────────────────────

def crear_cuenta(
    db: Session,
    *,
    codigo: str,
    nombre: str,
    nivel: int | None = None,
    fiscal: bool = False,
) -> CuentaContable:
    nivel = nivel or len(codigo)
    clase_digit = int(codigo[0]) if codigo and codigo[0].isdigit() else None
    cuenta = CuentaContable(
        codigo=codigo.strip(),
        nombre=nombre.strip(),
        clase=clase_digit,
        nivel=nivel,
        fiscal=fiscal,
    )
    db.add(cuenta)
    db.flush()
    return cuenta


def actualizar_cuenta(
    db: Session, codigo: str, **campos
) -> CuentaContable | None:
    cuenta = buscar_por_codigo(db, codigo)
    if not cuenta:
        return None
    for k, v in campos.items():
        if hasattr(cuenta, k):
            setattr(cuenta, k, v)
    db.flush()
    return cuenta
