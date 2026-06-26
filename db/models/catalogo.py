"""
Modelos de catálogo contable:
  - CuentaContable    →  Plan Único de Cuentas (PUC)
  - CodigoImpuesto    →  Tabla de impuestos SIIGO
  - TipoComprobante   →  Tipos de comprobante contable

Cada catálogo es por empresa: (codigo, empresa_id) es único.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Plan Único de Cuentas
# ─────────────────────────────────────────────────────────────────────────────

class CuentaContable(Base):
    __tablename__ = "cuentas_contables"
    __table_args__ = (
        UniqueConstraint("codigo", "empresa_id", name="uq_cuentas_codigo_empresa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    clase: Mapped[int | None] = mapped_column(SmallInteger)
    nivel: Mapped[int | None] = mapped_column(SmallInteger)
    fiscal: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    empresa_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CuentaContable {self.codigo} – {self.nombre[:40]}>"


# ─────────────────────────────────────────────────────────────────────────────
# Códigos de impuesto
# ─────────────────────────────────────────────────────────────────────────────

class CodigoImpuesto(Base):
    __tablename__ = "codigos_impuestos"
    __table_args__ = (
        UniqueConstraint("codigo", "empresa_id", name="uq_impuestos_codigo_empresa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    nombre: Mapped[str | None] = mapped_column(String(255))
    tipo_impuesto: Mapped[str | None] = mapped_column(String(50))
    tarifa: Mapped[float | None] = mapped_column(Numeric(8, 4))
    cta_ventas: Mapped[str | None] = mapped_column(String(20))
    cta_compras: Mapped[str | None] = mapped_column(String(20))
    cta_dev_ventas: Mapped[str | None] = mapped_column(String(20))
    cta_dev_compras: Mapped[str | None] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    empresa_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def es_retencion(self) -> bool:
        if not self.tipo_impuesto:
            return False
        return any(r in self.tipo_impuesto.lower() for r in ("retefuente", "reteica", "reteiva"))

    @property
    def cuenta_debito(self) -> str:
        return self.cta_compras or "" if not self.es_retencion else ""

    @property
    def cuenta_credito(self) -> str:
        return self.cta_compras or "" if self.es_retencion else ""

    def __repr__(self) -> str:
        return f"<CodigoImpuesto {self.codigo} {self.tipo_impuesto} {self.tarifa}%>"


# ─────────────────────────────────────────────────────────────────────────────
# Tipos de comprobante contable
# ─────────────────────────────────────────────────────────────────────────────

class TipoComprobante(Base):
    __tablename__ = "tipos_comprobante"
    __table_args__ = (
        UniqueConstraint("codigo", "empresa_id", name="uq_tipos_codigo_empresa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    empresa_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("empresas.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<TipoComprobante {self.codigo} – {self.titulo}>"
