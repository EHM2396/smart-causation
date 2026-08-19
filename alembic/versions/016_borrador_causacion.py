"""Tabla borradores_causacion: guardado temporal del flujo de causación

Permite al usuario dejar un lote de facturas verificado/configurado a medias,
desconectarse, y retomar donde quedó. Un único borrador por (empresa, usuario),
garantizado por un unique constraint. La fila nunca se borra: "descartar" es un
soft-delete que marca estado='descartado'.

Revision ID: 016
Revises: 015
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "borradores_causacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.Integer(),
            sa.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("datos_json", sa.Text(), nullable=False),
        sa.Column("total_facturas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_verificadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tipo_comp", sa.String(length=10), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="activo"),
        sa.Column(
            "creado_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "actualizado_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "empresa_id", "usuario_id", name="uq_borrador_empresa_usuario"
        ),
    )
    op.create_index(
        "ix_borradores_causacion_empresa_id", "borradores_causacion", ["empresa_id"]
    )
    op.create_index(
        "ix_borradores_causacion_usuario_id", "borradores_causacion", ["usuario_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_borradores_causacion_usuario_id", table_name="borradores_causacion")
    op.drop_index("ix_borradores_causacion_empresa_id", table_name="borradores_causacion")
    op.drop_table("borradores_causacion")
