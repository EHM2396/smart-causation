"""Filtrar historial por módulo: agregar tipo_causacion a facturas_causadas

Revision ID: 019
Revises: 018
Create Date: 2026-09-17

Guarda el módulo de causación (compras | nc | ventas | nc_ventas | soporte |
nc_soporte, mismos valores que DocTipo en el frontend) para poder filtrar el
historial por tipo. Registros anteriores quedan en NULL — se pueden completar
con scripts/backfill_tipo_causacion.py a partir de datos_json donde exista.
Idempotente.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columnas = {c["name"] for c in inspector.get_columns("facturas_causadas")}

    if "tipo_causacion" not in columnas:
        op.add_column(
            "facturas_causadas",
            sa.Column("tipo_causacion", sa.String(length=20), nullable=True),
        )
        op.create_index(
            "ix_facturas_causadas_tipo_causacion",
            "facturas_causadas",
            ["tipo_causacion"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columnas = {c["name"] for c in inspector.get_columns("facturas_causadas")}

    if "tipo_causacion" in columnas:
        op.drop_index("ix_facturas_causadas_tipo_causacion", table_name="facturas_causadas")
        op.drop_column("facturas_causadas", "tipo_causacion")
