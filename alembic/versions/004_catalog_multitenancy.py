"""Agregar empresa_id a tablas de catálogo

Revision ID: 004
Revises: 003
Create Date: 2026-06-25

Vincula cuentas_contables, codigos_impuestos y tipos_comprobante a empresas.
Migra los datos existentes a la primera empresa (id mínimo).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

_CATALOG_TABLES = [
    ("cuentas_contables",  "ix_cuentas_contables_empresa_id",  "cuentas_contables_codigo_key",  "uq_cuentas_codigo_empresa"),
    ("codigos_impuestos",  "ix_codigos_impuestos_empresa_id",  "codigos_impuestos_codigo_key",  "uq_impuestos_codigo_empresa"),
    ("tipos_comprobante",  "ix_tipos_comprobante_empresa_id",   "tipos_comprobante_codigo_key",  "uq_tipos_codigo_empresa"),
]


def upgrade() -> None:
    conn = op.get_bind()

    for tabla, idx_name, old_uq, new_uq in _CATALOG_TABLES:
        # 1. Añadir columna empresa_id (nullable)
        conn.execute(sa.text(
            f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id)"
        ))
        conn.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tabla}(empresa_id)"
        ))

        # 2. Quitar la constraint única simple sobre codigo
        conn.execute(sa.text(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{old_uq}'
                      AND conrelid = '{tabla}'::regclass
                ) THEN
                    ALTER TABLE {tabla} DROP CONSTRAINT {old_uq};
                END IF;
            END $$
        """))

        # 3. Añadir unique compuesto (codigo, empresa_id)
        conn.execute(sa.text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{new_uq}'
                      AND conrelid = '{tabla}'::regclass
                ) THEN
                    ALTER TABLE {tabla} ADD CONSTRAINT {new_uq} UNIQUE (codigo, empresa_id);
                END IF;
            END $$
        """))

    # 4. Asignar datos existentes a la primera empresa
    for tabla, _, _, _ in _CATALOG_TABLES:
        conn.execute(sa.text(
            f"UPDATE {tabla} SET empresa_id = (SELECT MIN(id) FROM empresas) WHERE empresa_id IS NULL"
        ))


def downgrade() -> None:
    pass
