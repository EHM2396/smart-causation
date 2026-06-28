"""Agregar campo tutorial_pendiente a usuarios

Revision ID: 008
Revises: 007
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column("tutorial_pendiente", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("usuarios", "tutorial_pendiente")
