"""
Modelo de borrador de causación.

Guarda un "temporal" del flujo de causación en curso para que el usuario pueda
desconectarse y retomar donde quedó. Hay un único borrador por (empresa, usuario):
guardar hace upsert sobre la misma fila.

El snapshot completo del wizard (facturas parseadas + configuración de paso 2)
vive en ``datos_json``. Los campos ``total_*`` y ``tipo_comp`` son metadatos
ligeros para mostrar la tarjeta "Continuar" sin tener que deserializar el JSON.

No se borra nunca la fila: "descartar" es un soft-delete que marca
``estado='descartado'``; volver a guardar la reactiva.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class BorradorCausacion(Base):
    __tablename__ = "borradores_causacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Multi-tenancy + privacidad: el borrador pertenece a una empresa y a un usuario.
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Snapshot completo del wizard (JSON serializado). Puede pesar varios cientos
    # de KB con muchas facturas, por eso va en Text.
    datos_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadatos ligeros para la tarjeta "Continuar" sin deserializar datos_json.
    total_facturas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_verificadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tipo_comp: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # 'activo' | 'descartado'. Soft-delete: nunca se borra la fila.
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "empresa_id", "usuario_id", name="uq_borrador_empresa_usuario"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BorradorCausacion empresa={self.empresa_id} "
            f"usuario={self.usuario_id} {self.estado}>"
        )
