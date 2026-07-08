"""
Modelos operacionales de contabilidad:
  - Proveedor         →  terceros registrados
  - FacturaCausada    →  historial de facturas procesadas
  - Consecutivo       →  contador por prefijo de comprobante
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# ─────────────────────────────────────────────────────────────────────────────
# Proveedores
# ─────────────────────────────────────────────────────────────────────────────

class Proveedor(Base):
    """
    Terceros (proveedores) que emiten facturas electrónicas a la empresa.

    tipo_persona: 'juridica' | 'natural'
    cuenta_pagar: código PUC de la cuenta por pagar (ej. '22050501')
                  → FK lógica a cuentas_contables.codigo
    """
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nit: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    razon_social: Mapped[str | None] = mapped_column(String(255))
    tipo_persona: Mapped[str | None] = mapped_column(String(20))     # 'juridica' | 'natural'
    regimen: Mapped[str | None] = mapped_column(String(50))
    cuenta_pagar: Mapped[str | None] = mapped_column(String(10))     # PUC cuentas por pagar
    ciudad: Mapped[str | None] = mapped_column(String(100))
    direccion: Mapped[str | None] = mapped_column(String(255))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    ia_habilitada: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = heredar global (True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Proveedor {self.nit} – {self.razon_social}>"


# ─────────────────────────────────────────────────────────────────────────────
# Facturas causadas (historial de procesamiento)
# ─────────────────────────────────────────────────────────────────────────────

class FacturaCausada(Base):
    """
    Registro de cada factura procesada por el sistema.
    Sirve para evitar re-causaciones y para auditoría.
    """
    __tablename__ = "facturas_causadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    numero_dian: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    nit_proveedor: Mapped[str | None] = mapped_column(String(20), index=True)
    razon_social: Mapped[str | None] = mapped_column(String(255))
    fecha_factura: Mapped[date | None] = mapped_column(Date)
    total: Mapped[float | None] = mapped_column(Numeric(18, 4))
    consecutivo: Mapped[str | None] = mapped_column(String(20))
    tipo_comprobante: Mapped[str | None] = mapped_column(String(10))
    fecha_causacion: Mapped[date | None] = mapped_column(Date)
    archivo_origen: Mapped[str | None] = mapped_column(String(500))
    datos_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero_dian", name="uq_facturas_causadas_empresa_numero"),
    )

    def __repr__(self) -> str:
        return f"<FacturaCausada {self.numero_dian} ({self.consecutivo})>"


# ─────────────────────────────────────────────────────────────────────────────
# Consecutivos por prefijo de comprobante
# ─────────────────────────────────────────────────────────────────────────────

class Consecutivo(Base):
    """
    Lleva el último número consecutivo utilizado por cada prefijo/tipo de comprobante.
    Reemplaza la tabla SQLite del mismo nombre.
    """
    __tablename__ = "consecutivos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    prefijo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ultimo_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("prefijo", "empresa_id", name="uq_consecutivos_prefijo_empresa"),
    )

    def __repr__(self) -> str:
        return f"<Consecutivo {self.prefijo}={self.ultimo_num}>"
