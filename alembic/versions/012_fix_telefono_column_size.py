"""Ampliar columnas telefono de VARCHAR(30) a VARCHAR(50)

Los números de teléfono con indicativo y extensión pueden superar 30 chars.
También previene truncación cuando el parser PDF extrae texto largo.

Revision ID: 012
Revises: 011
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE proveedores ALTER COLUMN telefono TYPE VARCHAR(50)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE proveedores ALTER COLUMN telefono_contacto TYPE VARCHAR(50)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE proveedores ALTER COLUMN telefono TYPE VARCHAR(30)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE proveedores ALTER COLUMN telefono_contacto TYPE VARCHAR(30)"
    ))
