"""
CuentasService – todas las consultas sobre el plan de cuentas PUC.
Todas las queries filtran por empresa_id (None = sin filtro, para compat. con Streamlit).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from db.models.catalogo import CuentaContable


def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto).lower())
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", sin_acentos).strip()


# ── Consultas base ─────────────────────────────────────────────────────────────

def listar_todas(db: Session, empresa_id: int | None = None) -> Sequence[CuentaContable]:
    stmt = select(CuentaContable).where(CuentaContable.activo == True)
    if empresa_id is not None:
        stmt = stmt.where(CuentaContable.empresa_id == empresa_id)
    return db.scalars(stmt).all()


def buscar_por_codigo(db: Session, codigo: str, empresa_id: int | None = None) -> CuentaContable | None:
    stmt = select(CuentaContable).where(CuentaContable.codigo == codigo.strip())
    if empresa_id is not None:
        stmt = stmt.where(CuentaContable.empresa_id == empresa_id)
    return db.scalar(stmt)


# ── Selectores para la UI ─────────────────────────────────────────────────────

_TAGS_GASTO_EXT: dict[str, str] = {
    "14": "[Inv] ",
    "15": "[PP&E] ",
    "16": "[Intang] ",
    "17": "[Diferi] ",
}


def listar_cuentas_gasto(db: Session, empresa_id: int | None = None) -> list[dict]:
    base = dict(
        activo=True,
        nivel=8,
        fiscal=False,
    )

    def _std_stmt():
        s = select(CuentaContable).where(
            CuentaContable.activo == True,
            CuentaContable.nivel == 8,
            CuentaContable.clase.in_([5, 6, 7]),
            CuentaContable.fiscal == False,
        ).order_by(CuentaContable.codigo)
        if empresa_id is not None:
            s = s.where(CuentaContable.empresa_id == empresa_id)
        return s

    def _ext_stmt():
        s = select(CuentaContable).where(
            CuentaContable.activo == True,
            CuentaContable.nivel == 8,
            CuentaContable.fiscal == False,
            or_(
                CuentaContable.codigo.like("14%"),
                CuentaContable.codigo.like("15%"),
                CuentaContable.codigo.like("16%"),
                CuentaContable.codigo.like("17%"),
            )
        ).order_by(CuentaContable.codigo)
        if empresa_id is not None:
            s = s.where(CuentaContable.empresa_id == empresa_id)
        return s

    rows_std = db.scalars(_std_stmt()).all()
    rows_ext = db.scalars(_ext_stmt()).all()

    result = [
        {"codigo": r.codigo, "nombre": r.nombre, "tag": "", "label": f"{r.codigo} – {r.nombre}"}
        for r in rows_std
    ]
    for r in rows_ext:
        tag = next((v for k, v in _TAGS_GASTO_EXT.items() if r.codigo.startswith(k)), "")
        result.append({
            "codigo": r.codigo,
            "nombre": r.nombre,
            "tag": tag,
            "label": f"{tag}{r.codigo} – {r.nombre}",
        })
    return result


def listar_metodos_pago(db: Session, empresa_id: int | None = None) -> list[dict]:
    stmt = select(CuentaContable).where(
        CuentaContable.activo == True,
        CuentaContable.nivel == 8,
        CuentaContable.fiscal == False,
        or_(
            CuentaContable.clase == 2,
            and_(
                CuentaContable.clase == 1,
                or_(
                    CuentaContable.codigo.like("11%"),
                    CuentaContable.codigo.like("12%"),
                )
            )
        )
    ).order_by(CuentaContable.codigo)
    if empresa_id is not None:
        stmt = stmt.where(CuentaContable.empresa_id == empresa_id)

    rows = db.scalars(stmt).all()
    return [
        {"codigo": r.codigo, "nombre": r.nombre, "label": f"{r.codigo} – {r.nombre}"}
        for r in rows
    ]


def buscar_cuentas_sugeridas(
    db: Session, descripcion: str, max_sugerencias: int = 3, empresa_id: int | None = None
) -> list[dict]:
    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]
    if not palabras:
        return []

    stmt = select(CuentaContable).where(
        CuentaContable.activo == True,
        CuentaContable.nivel == 8,
    )
    if empresa_id is not None:
        stmt = stmt.where(CuentaContable.empresa_id == empresa_id)

    todas = db.scalars(stmt).all()

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
    empresa_id: int | None = None,
) -> CuentaContable:
    nivel = nivel or len(codigo)
    clase_digit = int(codigo[0]) if codigo and codigo[0].isdigit() else None
    cuenta = CuentaContable(
        codigo=codigo.strip(),
        nombre=nombre.strip(),
        clase=clase_digit,
        nivel=nivel,
        fiscal=fiscal,
        empresa_id=empresa_id,
    )
    db.add(cuenta)
    db.flush()
    return cuenta


def upsert_cuenta(
    db: Session,
    *,
    codigo: str,
    nombre: str,
    fiscal: bool = False,
    empresa_id: int,
) -> tuple[CuentaContable, bool]:
    """Inserta o actualiza una cuenta por (codigo, empresa_id). Retorna (objeto, creado).
    Si la cuenta existe pero estaba inactiva (soft-deleted), la reactiva.
    """
    existing = buscar_por_codigo(db, codigo, empresa_id=empresa_id)
    if existing:
        creado = not existing.activo  # fue "creada" si estaba inactiva
        existing.nombre = nombre.strip()
        existing.fiscal = fiscal
        existing.activo = True
        db.flush()
        return existing, creado
    return crear_cuenta(db, codigo=codigo, nombre=nombre, fiscal=fiscal, empresa_id=empresa_id), True


def actualizar_cuenta(
    db: Session, codigo: str, empresa_id: int | None = None, **campos
) -> CuentaContable | None:
    cuenta = buscar_por_codigo(db, codigo, empresa_id=empresa_id)
    if not cuenta:
        return None
    for k, v in campos.items():
        if hasattr(cuenta, k):
            setattr(cuenta, k, v)
    db.flush()
    return cuenta
