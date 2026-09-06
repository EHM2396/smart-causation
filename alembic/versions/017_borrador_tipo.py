"""Agregar columna `tipo` a borradores_causacion (compras | nc)

Revision ID: 017
Revises: 016
Create Date: 2026-09-05

Cada usuario tiene un borrador por tipo de causación: uno para compras y otro
para notas crédito. Se agrega la columna `tipo` y se reemplaza el unique
(empresa_id, usuario_id) por (empresa_id, usuario_id, tipo).
Idempotente: seguro de re-ejecutar.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE borradores_causacion "
        "ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) NOT NULL DEFAULT 'compras'"
    ))
    # Reemplazar el unique viejo por uno que incluya el tipo
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_borrador_empresa_usuario'
                  AND conrelid = 'borradores_causacion'::regclass
            ) THEN
                ALTER TABLE borradores_causacion DROP CONSTRAINT uq_borrador_empresa_usuario;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_borrador_empresa_usuario_tipo'
                  AND conrelid = 'borradores_causacion'::regclass
            ) THEN
                ALTER TABLE borradores_causacion
                ADD CONSTRAINT uq_borrador_empresa_usuario_tipo
                UNIQUE (empresa_id, usuario_id, tipo);
            END IF;
        END $$
    """))


def downgrade() -> None:
    pass
