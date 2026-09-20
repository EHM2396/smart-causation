"""Documentos traídos de la DIAN (base de la analítica y del reporte de impuestos)

Revision ID: 027
Revises: 026
Create Date: 2026-09-19

La analítica venía saliendo de `facturas_causadas`, o sea de lo que alcanzamos a
causar. Eso no es lo que pasó: si un documento existe en la DIAN pero nadie lo
causó, no aparecía. Se detectó con tres notas crédito (NC257/258/259) que la DIAN
tenía en agosto y el informe no mostraba, dando ingresos inflados.

Esta tabla guarda lo que el token trae, sin importar si se causó o no. Es una
verdad distinta de `facturas_causadas`, no un duplicado:
  - `documentos_dian`   → lo que la DIAN dice que pasó
  - `facturas_causadas` → lo que se registró en el sistema
Comparar ambas es lo que permite ver qué falta por causar.

Se guarda `items_json` porque el reporte de impuestos necesita la base y la
tarifa de cada ítem, y volver a descargarlos de la DIAN cuesta minutos.

Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS documentos_dian (
            id              SERIAL PRIMARY KEY,
            empresa_id      INTEGER NOT NULL REFERENCES empresas(id),
            -- compras | nc | nd | ventas | nc_ventas | nd_ventas | soporte | nc_soporte
            tipo            VARCHAR(20) NOT NULL,
            numero          VARCHAR(80) NOT NULL,
            cufe            VARCHAR(120),
            fecha_emision   DATE,
            nit_contraparte VARCHAR(20),
            razon_social    VARCHAR(255),
            total           NUMERIC(18, 4),
            base_gravable   NUMERIC(18, 4),
            items_json      TEXT,
            traido_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    # Un mismo número puede repetirse entre tipos distintos (una compra y una
    # venta sin relación), así que el tipo entra en la clave.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_documentos_dian_empresa_tipo_numero
            ON documentos_dian (empresa_id, tipo, numero)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_documentos_dian_empresa_fecha
            ON documentos_dian (empresa_id, fecha_emision)
    """)


def downgrade() -> None:
    pass
