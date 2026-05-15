"""
Schemas Pydantic para la API de catálogo (cuentas, impuestos, tipos comprobante).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Cuentas Contables ─────────────────────────────────────────────────────────

class CuentaBase(BaseModel):
    codigo: str = Field(..., max_length=10, examples=["51050505"])
    nombre: str = Field(..., max_length=255)
    fiscal: bool = False


class CuentaCreate(CuentaBase):
    pass


class CuentaUpdate(BaseModel):
    nombre: str | None = None
    fiscal: bool | None = None
    activo: bool | None = None


class CuentaOut(CuentaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    clase: int | None
    nivel: int | None
    activo: bool
    created_at: datetime


class CuentaOpcion(BaseModel):
    """Shape compacto para selectboxes en la UI."""
    codigo: str
    nombre: str
    label: str


# ── Códigos de Impuesto ───────────────────────────────────────────────────────

class ImpuestoBase(BaseModel):
    codigo: str = Field(..., max_length=10, examples=["1"])
    nombre: str | None = None
    tipo_impuesto: str | None = None
    tarifa: float | None = None
    cta_ventas: str | None = None
    cta_compras: str | None = None
    cta_dev_ventas: str | None = None
    cta_dev_compras: str | None = None


class ImpuestoCreate(ImpuestoBase):
    pass


class ImpuestoUpdate(BaseModel):
    nombre: str | None = None
    tarifa: float | None = None
    cta_ventas: str | None = None
    cta_compras: str | None = None
    activo: bool | None = None


class ImpuestoOut(ImpuestoBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    activo: bool
    created_at: datetime


# ── Tipos de Comprobante ──────────────────────────────────────────────────────

class TipoComprobanteBase(BaseModel):
    codigo: str = Field(..., max_length=10, examples=["12"])
    titulo: str = Field(..., max_length=255)


class TipoComprobanteCreate(TipoComprobanteBase):
    pass


class TipoComprobanteOut(TipoComprobanteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    activo: bool
    created_at: datetime
