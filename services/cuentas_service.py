"""
CuentasService – todas las consultas sobre el plan de cuentas PUC.

Reemplaza las funciones de core/mapper.py que leían Cuentas_contables.xlsx.
Recibe una sesión SQLAlchemy; nunca abre conexión propia.
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

# Tags visuales para cuentas fuera del rango gasto/costo estándar
_TAGS_GASTO_EXT: dict[str, str] = {
    "14": "[Inv] ",
    "15": "[PP&E] ",
    "16": "[Intang] ",
    "17": "[Diferi] ",
}


def listar_cuentas_gasto(db: Session) -> list[dict]:
    """
    Cuentas de gasto/costo para la causación de facturas.

    Prioridad 1 (gastos y costos): clases 5, 6, 7.
    Prioridad 2 (inventarios y activos): cuentas 14xxx y 15xxx.
    Opcional (diferidos e intangibles): cuentas 16xxx y 17xxx.
    Solo nivel auxiliar (8 dígitos), activas y no fiscales.
    """
    rows_std = db.scalars(
        select(CuentaContable).where(
            CuentaContable.activo == True,
            CuentaContable.nivel == 8,
            CuentaContable.clase.in_([5, 6, 7]),
            CuentaContable.fiscal == False,
        ).order_by(CuentaContable.codigo)
    ).all()

    rows_ext = db.scalars(
        select(CuentaContable).where(
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
    ).all()

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


def listar_metodos_pago(db: Session) -> list[dict]:
    """
    Cuentas de pago de nivel auxiliar (8 dígitos), activas y no fiscales.

    Incluye:
      - Clase 2 completa: proveedores, cuentas por pagar, obligaciones.
      - Clase 1, grupos 11 (Disponible) y 12 (Inversiones/bancos): efectivo
        y equivalentes usados para registrar pagos directos.

    Excluye el resto de clase 1 (inventarios 14, PP&E 15, etc.) porque
    no son cuentas de pago en el contexto de causación de facturas.
    """
    rows = db.scalars(
        select(CuentaContable).where(
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
