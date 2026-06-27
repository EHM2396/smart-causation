"""Corregir constraints únicos en catálogos para soportar multiempresa

Revision ID: 007
Revises: 006
Create Date: 2026-06-27

La migración 004 intentó borrar los índices únicos simples sobre 'codigo'
buscando el nombre 'xxx_codigo_key', pero el nombre real en la BD es
'ix_{tabla}_codigo' (creado por SQLAlchemy con index=True, unique=True).
Esa constraint nunca se eliminó, impidiendo que dos empresas distintas
tengan los mismos códigos PUC/impuesto/comprobante.

Esta migración elimina los índices únicos simples y garantiza que
la constraint compuesta (codigo, empresa_id) exista correctamente.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

_TABLES = [
    {
        "tabla":   "cuentas_contables",
        "old_idx": "ix_cuentas_contables_codigo",
        "new_uq":  "uq_cuentas_codigo_empresa",
    },
    {
        "tabla":   "codigos_impuestos",
        "old_idx": "ix_codigos_impuestos_codigo",
        "new_uq":  "uq_impuestos_codigo_empresa",
    },
    {
        "tabla":   "tipos_comprobante",
        "old_idx": "ix_tipos_comprobante_codigo",
        "new_uq":  "uq_tipos_codigo_empresa",
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    for t in _TABLES:
        tabla   = t["tabla"]
        old_idx = t["old_idx"]
        new_uq  = t["new_uq"]

        # 1. Eliminar el índice único simple sobre 'codigo' si existe.
        #    Usamos SQL directo (no DO $$) porque DROP INDEX no acepta
        #    CONCURRENTLY dentro de bloques PL/pgSQL.
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {old_idx};"))

        # 2. Asegurarse de que la constraint compuesta (codigo, empresa_id) existe.
        conn.execute(sa.text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname  = '{new_uq}'
                      AND conrelid = '{tabla}'::regclass
                ) THEN
                    ALTER TABLE {tabla} ADD CONSTRAINT {new_uq} UNIQUE (codigo, empresa_id);
                END IF;
            END $$;
        """))


def downgrade() -> None:
    pass
