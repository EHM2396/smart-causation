"""Tabla consentimientos: prueba de aceptación de términos y política de privacidad

La Ley 1581 de 2012 exige autorización previa, expresa e informada del titular,
y obliga al responsable a conservar prueba de ella. Esta tabla es esa prueba:
una fila por documento aceptado, con versión, fecha, IP y user-agent.

Es append-only por diseño; no se actualiza ni se borra.

Revision ID: 015
Revises: 014
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consentimientos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("documento", sa.String(length=20), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("origen", sa.String(length=30), nullable=False, server_default="registro"),
        sa.Column(
            "aceptado_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_consentimientos_usuario_id", "consentimientos", ["usuario_id"])
    # Consulta típica: "¿este usuario aceptó la versión vigente de este documento?"
    op.create_index(
        "ix_consentimientos_usuario_doc",
        "consentimientos",
        ["usuario_id", "documento", "version"],
    )


def downgrade() -> None:
    op.drop_index("ix_consentimientos_usuario_doc", table_name="consentimientos")
    op.drop_index("ix_consentimientos_usuario_id", table_name="consentimientos")
    op.drop_table("consentimientos")
