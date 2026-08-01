"""Corregir unique constraint de consecutivos a (prefijo, empresa_id)

El índice anterior era único solo sobre `prefijo`, lo que impedía que dos
empresas distintas tuvieran su propio consecutivo para el mismo tipo de
comprobante. Se reemplaza por un unique compuesto (prefijo, empresa_id).

Revision ID: 010
Revises: 009
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Eliminar el índice único global sobre prefijo solamente
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_consecutivos_prefijo"))

    # Eliminar constraint compuesto si ya existía de una migración anterior fallida
    conn.execute(sa.text(
        "ALTER TABLE consecutivos DROP CONSTRAINT IF EXISTS uq_consecutivos_prefijo_empresa"
    ))

    # Crear el nuevo unique compuesto (prefijo, empresa_id)
    # Permite que cada empresa tenga sus propios consecutivos independientes
    op.create_unique_constraint(
        "uq_consecutivos_prefijo_empresa",
        "consecutivos",
        ["prefijo", "empresa_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_consecutivos_prefijo_empresa", "consecutivos", type_="unique")
    op.create_index("ix_consecutivos_prefijo", "consecutivos", ["prefijo"], unique=True)
