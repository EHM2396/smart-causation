"""Registro de cada traída de la DIAN (qué periodo se consultó y cuándo)

Revision ID: 028
Revises: 027
Create Date: 2026-09-19

Saber "cuándo se actualizó" no alcanza: el usuario necesita saber QUÉ PERIODO se
trajo, porque de eso depende si tiene que volver a pegar el token. Si la última
traída cubrió enero–junio y ahora está mirando agosto, los números van a estar
vacíos y sin este dato no hay forma de entender por qué.

`documentos_dian.traido_at` solo da la fecha del último guardado; el rango
consultado se perdía. Esta tabla lo conserva.

Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS sincronizaciones_dian (
            id           SERIAL PRIMARY KEY,
            empresa_id   INTEGER NOT NULL REFERENCES empresas(id),
            usuario_id   INTEGER REFERENCES usuarios(id),
            fecha_desde  DATE NOT NULL,
            fecha_hasta  DATE NOT NULL,
            documentos   INTEGER NOT NULL DEFAULT 0,
            errores      INTEGER NOT NULL DEFAULT 0,
            ejecutado_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sincronizaciones_dian_empresa
            ON sincronizaciones_dian (empresa_id, ejecutado_at DESC)
    """)


def downgrade() -> None:
    pass
