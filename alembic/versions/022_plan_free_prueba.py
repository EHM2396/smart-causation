"""Plan Free de prueba (100 causaciones / 14 días / 1 empresa) + campos de prueba

Revision ID: 022
Revises: 021
Create Date: 2026-09-08

- planes: + max_causaciones_total (cupo total, no mensual) + dias_prueba.
- cuentas_cliente: + es_prueba + prueba_expira.
- Siembra el plan 'Free' (100 causaciones totales, 14 días, 1 usuario, 1 empresa).
Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE planes ADD COLUMN IF NOT EXISTS max_causaciones_total INTEGER"))
    conn.execute(sa.text("ALTER TABLE planes ADD COLUMN IF NOT EXISTS dias_prueba INTEGER"))
    conn.execute(sa.text("ALTER TABLE cuentas_cliente ADD COLUMN IF NOT EXISTS es_prueba BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(sa.text("ALTER TABLE cuentas_cliente ADD COLUMN IF NOT EXISTS prueba_expira DATE"))

    # Plan Free de prueba (no visible como plan comprable; se asigna al registrarse).
    conn.execute(sa.text("""
        INSERT INTO planes (nombre, max_empresas, max_usuarios, max_causaciones_mes,
                            max_causaciones_total, dias_prueba, activo, visible)
        VALUES ('Free', 1, 1, NULL, 100, 14, TRUE, FALSE)
        ON CONFLICT (nombre) DO NOTHING
    """))


def downgrade() -> None:
    pass
