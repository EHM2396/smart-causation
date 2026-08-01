"""Corregir campos cruzados: tipo_regimen_iva y codigo_responsabilidad

El parser extraía R-99-PN (código de responsabilidad fiscal) y lo guardaba en
tipo_regimen_iva, y ZZ ("no aplica") en codigo_responsabilidad. Este script
corrige los registros existentes:
  - tipo_regimen_iva con R-XX-XX u O-XX → mover a codigo_responsabilidad
  - codigo_responsabilidad ZZ → tipo_regimen_iva = '0' (no responsable de IVA)

Revision ID: 014
Revises: 013
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Registros donde tipo_regimen_iva tiene un código de responsabilidad fiscal
    # (R-99-PN, O-13, O-15, O-23, O-47) y codigo_responsabilidad es ZZ o vacío.
    # → Mover tipo_regimen_iva → codigo_responsabilidad y poner '0' en tipo_regimen_iva.
    conn.execute(sa.text("""
        UPDATE proveedores
        SET
            codigo_responsabilidad = tipo_regimen_iva,
            tipo_regimen_iva       = '0'
        WHERE
            tipo_regimen_iva ~ '^(R-[0-9]+-[A-Z]+|O-[0-9]+)$'
            AND (codigo_responsabilidad IS NULL
                 OR codigo_responsabilidad = ''
                 OR codigo_responsabilidad = 'ZZ')
    """))

    # Registros donde tipo_regimen_iva ya tiene un código de responsabilidad
    # pero codigo_responsabilidad tiene un valor válido (no ZZ): solo normalizar régimen.
    conn.execute(sa.text("""
        UPDATE proveedores
        SET tipo_regimen_iva = '0'
        WHERE
            tipo_regimen_iva ~ '^(R-[0-9]+-[A-Z]+|O-[0-9]+)$'
    """))

    # Limpiar ZZ sobrantes en codigo_responsabilidad (dejar NULL o vacío)
    conn.execute(sa.text("""
        UPDATE proveedores
        SET codigo_responsabilidad = NULL
        WHERE codigo_responsabilidad = 'ZZ'
    """))


def downgrade() -> None:
    # No reversible: los valores originales eran incorrectos
    pass
