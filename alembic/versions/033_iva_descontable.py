"""IVA descontable en clasificacion_empresa

Revision ID: 033
Revises: 032
Create Date: 2026-09-26

Fase 2 del módulo de IVA (versión simplificada acordada con Andrés):
separar IVA_FACTURADO / IVA_DESCONTABLE / PENDIENTE_VALIDACIÓN.

`IVA_FACTURADO` no necesita columna propia: es el valor de IVA que ya trae
cada ítem en `documentos_dian.items_json` (`valor_impuesto`). Lo nuevo es la
DECISIÓN de si ese IVA facturado cuenta como descontable — eso sí hay que
guardarlo, y vive en la misma fila que el tratamiento y el tipo de ítem
(proveedor + referencia + concepto), porque se clasifica al mismo nivel.

`iva_descontable` — descontable | no_descontable. NULL = pendiente de
validación (el estado por defecto, igual que tipo_item): no bloquea nada, y
mientras no se confirme se muestra la sugerencia automática (derivada del
tratamiento de IVA, ver catalogo_tributario_service.sugerir_iva_descontable).

Solo agrega la columna (queda en NULL); no altera clasificaciones
existentes. Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE clasificacion_empresa "
        "ADD COLUMN IF NOT EXISTS iva_descontable VARCHAR(20)"
    )


def downgrade() -> None:
    pass
