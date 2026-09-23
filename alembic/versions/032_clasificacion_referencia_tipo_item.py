"""Referencia de producto y tipo de ítem (bien/servicio) en clasificacion_empresa

Revision ID: 032
Revises: 031
Create Date: 2026-09-23

Fase 1 del módulo de IVA (versión simplificada acordada con Andrés):

`referencia` — el código/referencia del producto tal como lo trae el XML
    (cac:SellersItemIdentification/cbc:ID). La memoria de clasificación ahora
    es proveedor + referencia + descripción, no solo proveedor + descripción:
    un mismo proveedor puede vender bienes y servicios con tratamientos
    distintos, y la referencia es lo que los distingue quando el texto de la
    descripción se repite. NULL cuando el XML no la trae — sigue funcionando
    con el fallback anterior (proveedor + descripción).

`tipo_item` — bien | servicio, sugerido automáticamente por descripción y
    confirmable por el contador en un clic (nunca obligatorio: si no hay
    seguridad suficiente queda NULL y se muestra "pendiente" sin bloquear
    nada).

Solo agrega columnas (quedan en NULL); no altera clasificaciones existentes.
Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE clasificacion_empresa "
        "ADD COLUMN IF NOT EXISTS referencia VARCHAR(120)"
    )
    op.execute(
        "ALTER TABLE clasificacion_empresa "
        "ADD COLUMN IF NOT EXISTS tipo_item VARCHAR(20)"
    )
    # La memoria por referencia se busca siempre junto con proveedor y
    # concepto — el mismo índice de búsqueda que ya existe (empresa_id,
    # concepto_norm, nit_tercero) alcanza para filtrar después por
    # referencia en memoria; no hace falta un índice aparte para esta
    # cantidad de filas.


def downgrade() -> None:
    pass
