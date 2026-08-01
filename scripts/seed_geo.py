"""
Script de siembra: carga paises, departamentos y ciudades desde
Paises-Departamentos-Ciudades.xlsx a la base de datos.

Ejecución:
    docker exec <api_container> python scripts/seed_geo.py
    -- o --
    python scripts/seed_geo.py   (desde la raíz del proyecto con PYTHONPATH configurado)

El script es idempotente: usa ON CONFLICT DO NOTHING, por lo que puede
ejecutarse varias veces sin duplicar datos.
"""

from __future__ import annotations

import os
import sys

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unicodedata

import openpyxl
from sqlalchemy import text

from db.session import SessionLocal

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RUTA_XLSX = os.path.join(BASE_DIR, "0111 paises.xlsx")

# Colombia tiene código "Co" en el xlsx pero Siigo usa "Col"
_PATCH_PAIS = {"Co": "Col"}


def _clean(val) -> str:
    """Normaliza un valor de celda a string limpio."""
    if val is None:
        return ""
    s = str(val).strip()
    # Normalizar Unicode a NFC para almacenamiento consistente
    return unicodedata.normalize("NFC", s)


def _codigo(val) -> str:
    """Convierte un valor de celda (int o str) a código string."""
    if val is None:
        return ""
    return str(val).strip()


def seed(db_session=None):
    rows_paises = 0
    rows_depts = 0
    rows_ciudades = 0

    wb = openpyxl.load_workbook(RUTA_XLSX, read_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))

    # Datos comienzan en fila 6 (índice 5)
    data = [r for r in all_rows[5:] if r[0] and r[3]]

    paises_vistos: set[str] = set()
    departamentos_vistos: set[tuple[str, str]] = set()
    ciudades_batch: list[dict] = []
    paises_batch: list[dict] = []
    departamentos_batch: list[dict] = []

    for r in data:
        nombre_pais = _clean(r[0])
        nombre_dept = _clean(r[1])
        nombre_ciudad = _clean(r[2])
        cod_pais_raw = _clean(r[3])
        cod_dept = _codigo(r[4])
        cod_ciudad = _codigo(r[5])

        if not nombre_pais or not cod_pais_raw:
            continue

        # Aplicar corrección Colombia: Co → Col
        cod_pais = _PATCH_PAIS.get(cod_pais_raw, cod_pais_raw)

        if cod_pais not in paises_vistos:
            paises_vistos.add(cod_pais)
            paises_batch.append({"codigo": cod_pais, "nombre": nombre_pais})

        if nombre_dept and cod_dept:
            key_dept = (cod_dept, cod_pais)
            if key_dept not in departamentos_vistos:
                departamentos_vistos.add(key_dept)
                departamentos_batch.append({
                    "codigo": cod_dept,
                    "nombre": nombre_dept,
                    "pais_codigo": cod_pais,
                })

        if nombre_ciudad and cod_ciudad:
            ciudades_batch.append({
                "codigo": cod_ciudad,
                "nombre": nombre_ciudad,
                "departamento_codigo": cod_dept if cod_dept else None,
                "pais_codigo": cod_pais,
            })

    close_after = db_session is None
    db = db_session or SessionLocal()

    try:
        # Paises
        for p in paises_batch:
            db.execute(
                text(
                    "INSERT INTO paises (codigo, nombre) VALUES (:codigo, :nombre) "
                    "ON CONFLICT (codigo) DO NOTHING"
                ),
                p,
            )
        rows_paises = len(paises_batch)

        # Departamentos
        for d in departamentos_batch:
            db.execute(
                text(
                    "INSERT INTO departamentos (codigo, nombre, pais_codigo) "
                    "VALUES (:codigo, :nombre, :pais_codigo) "
                    "ON CONFLICT ON CONSTRAINT uq_departamentos_codigo_pais DO NOTHING"
                ),
                d,
            )
        rows_depts = len(departamentos_batch)

        # Ciudades (en lotes de 500 para no saturar la transacción)
        BATCH = 500
        for i in range(0, len(ciudades_batch), BATCH):
            chunk = ciudades_batch[i : i + BATCH]
            for c in chunk:
                db.execute(
                    text(
                        "INSERT INTO ciudades (codigo, nombre, departamento_codigo, pais_codigo) "
                        "VALUES (:codigo, :nombre, :departamento_codigo, :pais_codigo) "
                        "ON CONFLICT ON CONSTRAINT uq_ciudades_codigo_pais DO NOTHING"
                    ),
                    c,
                )
        rows_ciudades = len(ciudades_batch)

        db.commit()
        print(f"Seed completado:")
        print(f"  Países:        {rows_paises}")
        print(f"  Departamentos: {rows_depts}")
        print(f"  Ciudades:      {rows_ciudades}")
    except Exception as e:
        db.rollback()
        print(f"Error en seed: {e}")
        raise
    finally:
        if close_after:
            db.close()

    return {
        "paises": rows_paises,
        "departamentos": rows_depts,
        "ciudades": rows_ciudades,
    }


if __name__ == "__main__":
    seed()
