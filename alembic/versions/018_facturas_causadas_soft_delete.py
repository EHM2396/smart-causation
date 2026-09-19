"""Borrado individual del historial: soft-delete en facturas_causadas

Revision ID: 018
Revises: 017
Create Date: 2026-09-14

Se agregan `eliminado` (bool) y `eliminado_at` para poder quitar un registro
puntual del historial sin ejecutar un DELETE contra la base de datos: el
registro se marca como eliminado y se filtra de los listados. Idempotente.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columnas = {c["name"] for c in inspector.get_columns("facturas_causadas")}

    if "eliminado" not in columnas:
        op.add_column(
            "facturas_causadas",
            sa.Column("eliminado", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "eliminado_at" not in columnas:
        op.add_column(
            "facturas_causadas",
            sa.Column("eliminado_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columnas = {c["name"] for c in inspector.get_columns("facturas_causadas")}

    if "eliminado_at" in columnas:
        op.drop_column("facturas_causadas", "eliminado_at")
    if "eliminado" in columnas:
        op.drop_column("facturas_causadas", "eliminado")
