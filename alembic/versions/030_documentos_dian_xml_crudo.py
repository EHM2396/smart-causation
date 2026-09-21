"""Guardar el XML original de cada documento traído de la DIAN

Revision ID: 030
Revises: 029
Create Date: 2026-09-20

El motor del Formulario 300 exige que cada valor del reporte pueda contestar
"¿de dónde salió?" hasta el documento que lo originó:

    valor consolidado → categoría → proveedor → concepto → documento → ítem → XML

Hoy eso es imposible: se guardaba el resultado del parseo y el XML se
descartaba. Sin el original no hay trazabilidad, y tampoco se puede reprocesar
cuando el parser aprenda a leer un campo nuevo (AIU, tipo de operación,
exportación) — habría que volver a descargarlo TODO de la DIAN, con un enlace
que dura una hora.

Se guarda comprimido con gzip: un XML de factura ronda las decenas de KB y
comprime cerca de 10 a 1, así que el costo en disco es menor y viaja dentro del
respaldo normal de la base. Se guarda el archivo tal como lo entrega la DIAN
(XML suelto o ZIP), sin reescribirlo: si algún día hay que auditar una firma
digital, tiene que ser el original byte por byte.

Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE documentos_dian ADD COLUMN IF NOT EXISTS xml_crudo BYTEA"
    )


def downgrade() -> None:
    pass
