"""Rol org_admin: marca a los dueños de cada Cuenta como administradores

Revision ID: 019
Revises: 018
Create Date: 2026-09-08

B3: introduce el rol `org_admin` (administrador de la Cuenta). Marca como
org_admin a los usuarios que son dueños de una empresa dentro de una Cuenta.
El resto de usuarios sigue como `user` (causador). El superadmin (`admin`) no
se toca. Idempotente; downgrade no-op.
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
    conn.execute(sa.text("""
        UPDATE usuarios SET rol = 'org_admin'
        WHERE rol = 'user'
          AND cuenta_id IS NOT NULL
          AND id IN (
              SELECT DISTINCT owner_id FROM empresas
              WHERE owner_id IS NOT NULL AND cuenta_id IS NOT NULL
          )
    """))


def downgrade() -> None:
    pass
