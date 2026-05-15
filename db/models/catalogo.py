"""
Modelos de catálogo contable:
  - CuentaContable    →  Plan Único de Cuentas (PUC)
  - CodigoImpuesto    →  Tabla de impuestos SIIGO
  - TipoComprobante   →  Tipos de comprobante contable
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Plan Único de Cuentas
# ─────────────────────────────────────────────────────────────────────────────

class CuentaContable(Base):
    """
    Representa una cuenta del PUC colombiano.

    Niveles:
      1 → Clase      (1 dígito)
      2 → Grupo      (2 dígitos)
      3 → Cuenta     (4 dígitos)
      4 → Subcuenta  (6 dígitos)
      5 → Auxiliar   (8 dígitos)  ← únicamente estos se usan en asientos

    Filtros relevantes para causación:
      - clase 1/2  →  cuentas de activo/pasivo (método de pago)
      - clase 5/6/7 →  gastos y costos
      - fiscal=True  →  excluir de selectores de la UI
    """
    __tablename__ = "cuentas_contables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    clase: Mapped[int | None] = mapped_column(SmallInteger)          # primer dígito
    nivel: Mapped[int | None] = mapped_column(SmallInteger)          # longitud del código
    fiscal: Mapped[bool] = mapped_column(Boolean, default=False)     # True si contiene "fiscal"
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
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
    """
    Tabla equivalente a codigos_impuestos.xlsx.

    tipo_impuesto:
      'IVA'          →  cuenta débito = cta_compras  (IVA descontable)
      'Impoconsumo'  →  cuenta débito = cta_compras
      'Retefuente'   →  cuenta crédito = cta_compras (retención a pagar)
      'ReteICA'      →  cuenta crédito = cta_compras
      'ReteIVA'      →  cuenta crédito = cta_compras
    """
    __tablename__ = "codigos_impuestos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    nombre: Mapped[str | None] = mapped_column(String(255))
    tipo_impuesto: Mapped[str | None] = mapped_column(String(50))    # IVA, Retefuente, ...
    tarifa: Mapped[float | None] = mapped_column(Numeric(8, 4))      # porcentaje (19.0, 5.0...)
    cta_ventas: Mapped[str | None] = mapped_column(String(20))
    cta_compras: Mapped[str | None] = mapped_column(String(20))      # cuenta débito/crédito
    cta_dev_ventas: Mapped[str | None] = mapped_column(String(20))
    cta_dev_compras: Mapped[str | None] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
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
        """Cuenta débito para el asiento de compras (IVA descontable)."""
        return self.cta_compras or "" if not self.es_retencion else ""

    @property
    def cuenta_credito(self) -> str:
        """Cuenta crédito para el asiento de compras (retención a pagar)."""
        return self.cta_compras or "" if self.es_retencion else ""

    def __repr__(self) -> str:
        return f"<CodigoImpuesto {self.codigo} {self.tipo_impuesto} {self.tarifa}%>"


# ─────────────────────────────────────────────────────────────────────────────
# Tipos de comprobante contable
# ─────────────────────────────────────────────────────────────────────────────

class TipoComprobante(Base):
    """
    Equivalente a Tipos_comprobante_contable.xlsx.
    Código numérico que SIIGO usa para identificar el tipo de asiento.
    """
    __tablename__ = "tipos_comprobante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<TipoComprobante {self.codigo} – {self.titulo}>"
