"""Eliminación (permanente en la UI, soft en la BD) de usuarios sin causaciones

Revision ID: 029
Revises: 028
Create Date: 2026-09-20

El admin puede "eliminar" a un causador que nunca causó nada, para dejar de
verlo en su lista. Nunca se borra la fila de `usuarios` (regla del proyecto:
nunca DELETE): se marca `eliminado` y desaparece de todo, igual que
`facturas_causadas.eliminado` y `empresas.activa` ya hacen con sus propias
filas. Las empresas que ese usuario haya creado se desactivan junto con él
(`empresas.activa = false`), reutilizando ese mismo campo — no hace falta
columna nueva ahí.

Eliminar debe DEJAR LIBRE el correo: la persona detrás de esa cuenta puede
registrarse de nuevo con el mismo correo, como una cuenta totalmente
independiente (su propio plan, su propia Cuenta) — eliminar a alguien de un
grupo no es dejarlo marcado para siempre. Como `email` es UNIQUE, se reescribe
el de la fila eliminada a un valor inerte (`email_original` guarda el real,
para consulta/auditoría) y así el correo real queda disponible para una
inscripción nueva.

Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS eliminado "
        "BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS eliminado_at "
        "TIMESTAMPTZ"
    )
    # El correo real de la fila eliminada, para consulta/auditoría, una vez
    # que `email` se reescribió a un valor inerte para liberarlo.
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_original "
        "VARCHAR(255)"
    )


def downgrade() -> None:
    pass
