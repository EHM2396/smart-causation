"""
Script de migración: XLSX → PostgreSQL
=======================================

Lee los tres archivos Excel de catálogo que actualmente usa el sistema y los
inserta en las tablas de PostgreSQL.

Uso:
    python scripts/migrate_xlsx.py

Requiere que la base de datos ya exista y que DATABASE_URL esté en el .env.
Las tablas se crean automáticamente si no existen.

Idempotente: usa INSERT ... ON CONFLICT DO UPDATE para no duplicar registros.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path

# Agregar la raíz del proyecto al path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import Base, CuentaContable, CodigoImpuesto, TipoComprobante
from db.session import SessionLocal, engine

# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = PROJECT_ROOT

_RUTA_CUENTAS   = BASE_DIR / "Cuentas_contables.xlsx"
_RUTA_IMPUESTOS = BASE_DIR / "codigos_impuestos.xlsx"
_RUTA_TIPOS     = BASE_DIR / "Tipos_comprobante_contable.xlsx"


def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto).lower())
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", sin_acentos).strip()


def _detectar_col(cols, candidatos: list[str]) -> str | None:
    norms = {c: _norm(c) for c in cols}
    for cand in candidatos:
        for col, n in norms.items():
            if cand in n:
                return col
    return None


def _to_float(valor) -> float | None:
    if pd.isna(valor):
        return None
    try:
        return float(str(valor).replace(",", ".").strip())
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Migración de cuentas contables
# ─────────────────────────────────────────────────────────────────────────────

def migrar_cuentas() -> int:
    print("→ Migrando cuentas contables...")

    if not _RUTA_CUENTAS.exists():
        print(f"  ⚠  Archivo no encontrado: {_RUTA_CUENTAS}")
        return 0

    hojas = pd.read_excel(_RUTA_CUENTAS, sheet_name=None, dtype=str)
    df = pd.concat(hojas.values(), ignore_index=True)

    col_cod = _detectar_col(df.columns, ["codigo", "cuenta", "puc", "code", "c digo"])
    col_nom = _detectar_col(df.columns, ["nombre", "descripcion", "detalle", "name"])

    if not col_cod:
        print("  ✗  No se encontró columna de código en Cuentas_contables.xlsx")
        return 0

    registros = []
    for _, row in df.iterrows():
        cod = str(row[col_cod]).strip()
        if not cod or cod.lower() in ("nan", ""):
            continue
        # Solo aceptar códigos estrictamente numéricos (PUC real)
        if not cod.isdigit():
            continue
        nom = str(row[col_nom]).strip() if col_nom and not pd.isna(row[col_nom]) else ""
        clase = int(cod[0]) if cod[0].isdigit() else None
        nivel = len(cod)
        fiscal = "fiscal" in nom.lower()

        registros.append({
            "codigo": cod,
            "nombre": nom,
            "clase": clase,
            "nivel": nivel,
            "fiscal": fiscal,
            "activo": True,
        })

    if not registros:
        return 0

    with SessionLocal() as session:
        stmt = pg_insert(CuentaContable).values(registros)
        stmt = stmt.on_conflict_do_update(
            index_elements=["codigo"],
            set_={"nombre": stmt.excluded.nombre, "fiscal": stmt.excluded.fiscal},
        )
        session.execute(stmt)
        session.commit()

    print(f"  ✓  {len(registros)} cuentas migradas")
    return len(registros)


# ─────────────────────────────────────────────────────────────────────────────
# Migración de códigos de impuesto
# ─────────────────────────────────────────────────────────────────────────────

def migrar_impuestos() -> int:
    print("→ Migrando códigos de impuesto...")

    if not _RUTA_IMPUESTOS.exists():
        print(f"  ⚠  Archivo no encontrado: {_RUTA_IMPUESTOS}")
        return 0

    hojas = pd.read_excel(_RUTA_IMPUESTOS, sheet_name=None, dtype=str)
    df = pd.concat(hojas.values(), ignore_index=True)
    df.columns = [_norm(c) for c in df.columns]

    def _find(cond) -> str | None:
        return next((c for c in df.columns if cond(c)), None)

    col_cod     = _find(lambda n: n in ("codigo", "cod"))
    col_nombre  = _find(lambda n: "nombre" in n)
    col_tipo    = _find(lambda n: "tipo" in n and "impuesto" in n)
    col_tarifa  = _find(lambda n: "tarifa" in n and "descripcion" not in n)
    col_cta_ven = _find(lambda n: "ventas" in n and "dev" not in n and "descripcion" not in n)
    col_cta_com = _find(lambda n: "compras" in n and "dev" not in n and "descripcion" not in n)
    col_dev_ven = _find(lambda n: "dev" in n and "ventas" in n and "descripcion" not in n)
    col_dev_com = _find(lambda n: "dev" in n and "compras" in n and "descripcion" not in n)

    if not col_cod:
        print("  ✗  No se encontró columna de código en codigos_impuestos.xlsx")
        return 0

    registros = []
    for _, row in df.iterrows():
        cod = str(row[col_cod]).strip()
        if not cod or cod.lower() in ("nan", ""):
            continue

        def _val(col):
            if col and col in row and not pd.isna(row[col]):
                return str(row[col]).strip() or None
            return None

        registros.append({
            "codigo":          cod,
            "nombre":          _val(col_nombre),
            "tipo_impuesto":   _val(col_tipo),
            "tarifa":          _to_float(row[col_tarifa]) if col_tarifa else None,
            "cta_ventas":      _val(col_cta_ven),
            "cta_compras":     _val(col_cta_com),
            "cta_dev_ventas":  _val(col_dev_ven),
            "cta_dev_compras": _val(col_dev_com),
            "activo":          True,
        })

    if not registros:
        return 0

    with SessionLocal() as session:
        stmt = pg_insert(CodigoImpuesto).values(registros)
        stmt = stmt.on_conflict_do_update(
            index_elements=["codigo"],
            set_={
                "tarifa":        stmt.excluded.tarifa,
                "cta_compras":   stmt.excluded.cta_compras,
                "cta_ventas":    stmt.excluded.cta_ventas,
                "tipo_impuesto": stmt.excluded.tipo_impuesto,
            },
        )
        session.execute(stmt)
        session.commit()

    print(f"  ✓  {len(registros)} impuestos migrados")
    return len(registros)


# ─────────────────────────────────────────────────────────────────────────────
# Migración de tipos de comprobante
# ─────────────────────────────────────────────────────────────────────────────

def migrar_tipos_comprobante() -> int:
    print("→ Migrando tipos de comprobante...")

    if not _RUTA_TIPOS.exists():
        print(f"  ⚠  Archivo no encontrado: {_RUTA_TIPOS}")
        return 0

    # Detectar fila de encabezado (igual que en mapper.py)
    raw = pd.read_excel(_RUTA_TIPOS, header=None, dtype=str)
    header_row = None
    for i, row in raw.iterrows():
        vals = [_norm(str(v)) for v in row if not pd.isna(v)]
        if any("codigo" in v for v in vals):
            header_row = i
            break

    if header_row is None:
        print("  ✗  No se encontró fila de encabezado en Tipos_comprobante_contable.xlsx")
        return 0

    df = pd.read_excel(_RUTA_TIPOS, skiprows=header_row, dtype=str)
    col_cod  = _detectar_col(df.columns, ["codigo", "cod"])
    col_tit  = _detectar_col(df.columns, ["titulo", "nombre", "descripcion", "name"])

    if not col_cod:
        print("  ✗  No se encontró columna de código")
        return 0

    registros = []
    for _, row in df.iterrows():
        cod = str(row[col_cod]).strip()
        if not cod or cod.lower() in ("nan", ""):
            continue
        # Solo aceptar códigos numéricos (filtrar filas de pie de página)
        if not cod.isdigit():
            continue
        tit = str(row[col_tit]).strip() if col_tit and not pd.isna(row[col_tit]) else ""
        registros.append({"codigo": cod, "titulo": tit, "activo": True})

    if not registros:
        return 0

    with SessionLocal() as session:
        stmt = pg_insert(TipoComprobante).values(registros)
        stmt = stmt.on_conflict_do_update(
            index_elements=["codigo"],
            set_={"titulo": stmt.excluded.titulo},
        )
        session.execute(stmt)
        session.commit()

    print(f"  ✓  {len(registros)} tipos de comprobante migrados")
    return len(registros)


# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Migración XLSX → PostgreSQL")
    print("=" * 60)

    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    print("  Tablas verificadas/creadas en PostgreSQL\n")

    total = 0
    total += migrar_cuentas()
    total += migrar_impuestos()
    total += migrar_tipos_comprobante()

    print(f"\n{'=' * 60}")
    print(f"  Migración completada: {total} registros insertados/actualizados")
    print("=" * 60)


if __name__ == "__main__":
    main()
