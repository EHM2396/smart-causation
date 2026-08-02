"""
Modelo de prueba de consentimiento.

El artículo 9 de la Ley 1581 de 2012 exige la autorización previa, expresa e
informada del titular, y el Decreto 1074 de 2015 obliga al responsable a
conservar prueba de esa autorización. Esta tabla es esa prueba.

Se escribe una fila por cada aceptación. Nunca se actualiza ni se borra: si el
usuario acepta una versión nueva de los documentos, se inserta otra fila. Así el
histórico completo queda reconstruible ante un requerimiento de la SIC.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Consentimiento(Base):
    __tablename__ = "consentimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Documento aceptado: 'terminos' | 'privacidad'.
    # Hoy se aceptan juntos en el registro, pero quedan como filas separadas para
    # poder versionarlos de forma independiente más adelante.
    documento: Mapped[str] = mapped_column(String(20), nullable=False)

    # Versión exacta que el usuario vio (VERSION_LEGAL del frontend).
    version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Contexto de la aceptación, para acreditar cuándo y desde dónde se otorgó.
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)  # cabe IPv6
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    origen: Mapped[str] = mapped_column(String(30), nullable=False, default="registro")

    aceptado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Consentimiento u={self.usuario_id} {self.documento} v{self.version}>"
