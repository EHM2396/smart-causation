"""Máximo de empresas por usuario causador (lo asigna el admin de la cuenta)

Revision ID: 023
Revises: 022
Create Date: 2026-09-08

Cada causador crea sus propias empresas hasta el máximo que le asigna el admin.
NULL = sin tope propio (solo el del plan). Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS max_empresas INTEGER"))


def downgrade() -> None:
    pass
