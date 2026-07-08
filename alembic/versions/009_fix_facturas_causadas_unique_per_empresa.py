"""Corregir unique constraint de facturas_causadas a (empresa_id, numero_dian)

El constraint anterior era único sobre numero_dian globalmente, lo que impedía
que dos empresas distintas registraran facturas con el mismo número DIAN.
Se reemplaza por un unique compuesto (empresa_id, numero_dian).

Revision ID: 009
Revises: 008
Create Date: 2026-07-08
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eliminar el índice único global sobre numero_dian
    op.drop_index("ix_facturas_causadas_numero_dian", table_name="facturas_causadas")

    # Crear el nuevo unique compuesto por empresa + numero
    op.create_unique_constraint(
        "uq_facturas_causadas_empresa_numero",
        "facturas_causadas",
        ["empresa_id", "numero_dian"],
    )

    # Mantener índice simple en numero_dian para búsquedas rápidas
    op.create_index(
        "ix_facturas_causadas_numero_dian",
        "facturas_causadas",
        ["numero_dian"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_constraint("uq_facturas_causadas_empresa_numero", "facturas_causadas", type_="unique")
    op.drop_index("ix_facturas_causadas_numero_dian", table_name="facturas_causadas")
    op.create_index(
        "ix_facturas_causadas_numero_dian",
        "facturas_causadas",
        ["numero_dian"],
        unique=True,
    )
