"""
Modelos para aprendizaje automático y trazabilidad de decisiones:
  - MapeoPUC            →  asociación NIT+keyword → cuenta PUC aprendida
  - HistorialDecision   →  log de cada mapeo aplicado (correcto/corregido)
  - ReglaClasificacion  →  reglas de clasificación versionadas (prepara ML)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# ─────────────────────────────────────────────────────────────────────────────
# Mapeos PUC aprendidos
# ─────────────────────────────────────────────────────────────────────────────

class MapeoPUC(Base):
    """
    Aprende la asociación entre (NIT del proveedor + keyword de descripción) y
    una cuenta del PUC. Se refuerza con cada uso confirmado.
    Aislado por (usuario_id + empresa_id): dos usuarios en la misma empresa
    mantienen aprendizajes independientes.
    """
    __tablename__ = "mapeos_puc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    nit: Mapped[str | None] = mapped_column(String(20), index=True)
    keyword: Mapped[str | None] = mapped_column(String(255), index=True)
    cuenta_puc: Mapped[str] = mapped_column(String(10), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    usos: Mapped[int] = mapped_column(Integer, default=1)
    confianza: Mapped[float] = mapped_column(Numeric(5, 4), default=0.5)  # [0, 1]
    ultima_vez: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<MapeoPUC nit={self.nit} kw={self.keyword!r} → {self.cuenta_puc}>"


# ─────────────────────────────────────────────────────────────────────────────
# Historial de decisiones (trazabilidad para IA)
# ─────────────────────────────────────────────────────────────────────────────

class HistorialDecision(Base):
    """
    Registra cada decisión de mapeo aplicada durante una causación.
    Aislado por (usuario_id + empresa_id).
    fue_corregida: True si el usuario cambió la cuenta sugerida.
    origen: 'manual' | 'aprendizaje' | 'ia'
    """
    __tablename__ = "historial_decisiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    numero_dian: Mapped[str | None] = mapped_column(String(80), index=True)
    nit_proveedor: Mapped[str | None] = mapped_column(String(20), index=True)
    descripcion_item: Mapped[str | None] = mapped_column(Text)
    cuenta_sugerida: Mapped[str | None] = mapped_column(String(10))
    cuenta_aplicada: Mapped[str | None] = mapped_column(String(10))
    cod_impuesto: Mapped[str | None] = mapped_column(String(10))
    fue_corregida: Mapped[bool] = mapped_column(Boolean, default=False)
    origen: Mapped[str | None] = mapped_column(String(20))           # 'manual'|'aprendizaje'|'ia'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<HistorialDecision {self.numero_dian} "
            f"→ {self.cuenta_aplicada} (corregida={self.fue_corregida})>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Reglas de clasificación versionadas
# ─────────────────────────────────────────────────────────────────────────────

class ReglaClasificacion(Base):
    """
    Reglas de clasificación automática para mapear descripciones a cuentas PUC.

    tipo:
      'keyword'  →  coincidencia de texto simple
      'regex'    →  patrón de expresión regular
      'ml'       →  delegado a modelo ML externo (futura integración)

    version: permite versionado de conjuntos de reglas para auditoría.
    prioridad: mayor número = se evalúa primero.
    """
    __tablename__ = "reglas_clasificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    patron: Mapped[str] = mapped_column(String(500), nullable=False)  # texto o regex
    cuenta_puc: Mapped[str] = mapped_column(String(10), nullable=False)
    prioridad: Mapped[int] = mapped_column(Integer, default=0)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    tipo: Mapped[str] = mapped_column(String(20), default="keyword")  # keyword|regex|ml
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ReglaClasificacion v{self.version} {self.patron!r} → {self.cuenta_puc}>"
