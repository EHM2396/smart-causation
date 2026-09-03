"""Agrega columna ia_habilitada a proveedores

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-10

La columna se agrega como nullable=True para no romper proveedores existentes.
NULL significa "heredar configuración global" que por defecto es habilitada.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS ia_habilitada BOOLEAN")


def downgrade() -> None:
    op.drop_column('proveedores', 'ia_habilitada')
