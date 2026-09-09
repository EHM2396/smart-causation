"""El plan Tester es de usuarios CAUSADORES (tope ilimitado), no administradores

Revision ID: 023
Revises: 022
Create Date: 2026-09-09

La migración 019 marcó como org_admin a los dueños de empresa, incluyendo a los
usuarios internos de prueba (plan Tester). Pero un Tester es un causador con topes
ilimitados (como un Básico pero sin límites), NO un administrador. Se revierten a
'causador'. Idempotente; downgrade no-op.
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
    conn.execute(sa.text("""
        UPDATE usuarios SET rol = 'causador'
        WHERE rol = 'org_admin'
          AND cuenta_id IN (
              SELECT id FROM cuentas_cliente
              WHERE plan_id = (SELECT id FROM planes WHERE nombre = 'Tester')
          )
    """))


def downgrade() -> None:
    pass
