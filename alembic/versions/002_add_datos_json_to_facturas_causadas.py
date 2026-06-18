"""add datos_json to facturas_causadas

Revision ID: 002
Revises: 001
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "facturas_causadas",
        sa.Column("datos_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("facturas_causadas", "datos_json")
