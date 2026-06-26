"""Agregar usuario_id a mapeos_puc e historial_decisiones

Revision ID: 005
Revises: 004
Create Date: 2026-06-25

El aprendizaje queda aislado por (usuario + empresa): dos usuarios que
operen la misma empresa (planes Profesional+) mantienen aprendizajes
independientes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    for tabla, idx_name in [
        ("mapeos_puc",           "ix_mapeos_puc_usuario_id"),
        ("historial_decisiones", "ix_historial_decisiones_usuario_id"),
    ]:
        conn.execute(sa.text(
            f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES usuarios(id)"
        ))
        conn.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tabla}(usuario_id)"
        ))

    # Asignar datos existentes al usuario causacion@smartcausacion.com
    conn.execute(sa.text("""
        UPDATE mapeos_puc
        SET usuario_id = (SELECT id FROM usuarios WHERE email = 'causacion@smartcausacion.com')
        WHERE usuario_id IS NULL
    """))
    conn.execute(sa.text("""
        UPDATE historial_decisiones
        SET usuario_id = (SELECT id FROM usuarios WHERE email = 'causacion@smartcausacion.com')
        WHERE usuario_id IS NULL
    """))


def downgrade() -> None:
    pass
