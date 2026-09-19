"""Base gravable en facturas_causadas (analítica de costos/gastos/ingresos)

Revision ID: 026
Revises: 025
Create Date: 2026-09-19

El dashboard de analítica suma por naturaleza (ingresos vs costos y gastos). El
`total` de la factura incluye IVA, y el IVA descontable no es un costo: es un
saldo a favor. La cifra correcta es la suma de las bases de los ítems.

Ese dato ya vivía dentro de `datos_json` (texto), pero calcularlo exigía parsear
un JSON por fila en cada carga del dashboard. Se materializa en su propia
columna para que la analítica sea una agregación SQL.

Solo agrega la columna (queda en NULL). El poblado de los registros históricos
va aparte, en scripts/backfill_base_gravable.py, para poder revisarlo antes de
aplicarlo. Mientras tanto la analítica usa COALESCE(base_gravable, total), así
que funciona igual desde el primer día. Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE facturas_causadas "
        "ADD COLUMN IF NOT EXISTS base_gravable NUMERIC(18, 4)"
    )


def downgrade() -> None:
    pass
