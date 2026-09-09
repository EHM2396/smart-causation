"""Cupos de causación por usuario/empresa + siembra de planes grandes

Revision ID: 020
Revises: 019
Create Date: 2026-09-08

- Tabla `cupos_causacion`: tope de causaciones/mes que el admin asigna a un
  usuario (o empresa) dentro de la Cuenta (adicional al tope del plan).
- Siembra los planes Profesional / Firma / Enterprise con sus límites (el plan
  'base' = Básico ya existe). Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cupos_causacion (
            id          SERIAL PRIMARY KEY,
            cuenta_id   INTEGER NOT NULL REFERENCES cuentas_cliente(id),
            usuario_id  INTEGER REFERENCES usuarios(id),
            empresa_id  INTEGER REFERENCES empresas(id),
            max_mes     INTEGER NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cupos_causacion_cuenta ON cupos_causacion (cuenta_id)"))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cupos_causacion_usuario ON cupos_causacion (usuario_id)"))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cupos_causacion_empresa ON cupos_causacion (empresa_id)"))

    # Planes grandes (Básico = 'base' ya existe con 300/1/1).
    conn.execute(sa.text("""
        INSERT INTO planes (nombre, max_empresas, max_usuarios, max_causaciones_mes, activo, visible)
        VALUES
            ('Profesional', 10,   5,    1000, TRUE, TRUE),
            ('Firma',       50,   20,   5000, TRUE, TRUE),
            ('Enterprise',  NULL, NULL, NULL, TRUE, TRUE)
        ON CONFLICT (nombre) DO NOTHING
    """))


def downgrade() -> None:
    pass
