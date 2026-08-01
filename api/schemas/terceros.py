"""
Schemas Pydantic para el módulo de Terceros.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TipoIdentificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: int
    descripcion: str


class PaisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: str
    nombre: str


class DepartamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: str
    nombre: str
    pais_codigo: str | None = None


class CiudadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: str
    nombre: str
    departamento_codigo: str | None = None
    pais_codigo: str | None = None


class SiigoTipoPersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: str
    descripcion: str
    valor_interno: str | None = None


class SiigoRegimenIvaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: str
    etiqueta: str


class SiigoResponsabilidadFiscalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: str
    descripcion: str


class TerceroCatalogos(BaseModel):
    tipos_identificacion: list[TipoIdentificacionOut]
    paises: list[PaisOut]
    tipos_persona: list[SiigoTipoPersonaOut] = []
    regimenes_iva: list[SiigoRegimenIvaOut] = []
    responsabilidades_fiscales: list[SiigoResponsabilidadFiscalOut] = []


class TerceroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nit: str
    digito_verificacion: int | None = None
    codigo_sucursal: str | None = None
    tipo_identificacion: int | None = None
    tipo_persona: str | None = None
    razon_social: str | None = None
    nombres_tercero: str | None = None
    apellidos_tercero: str | None = None
    nombre_comercial: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    departamento: str | None = None
    codigo_pais: str | None = None
    codigo_departamento: str | None = None
    codigo_ciudad_siigo: str | None = None
    codigo_postal: str | None = None
    indicativo_tel: int | None = None
    telefono: str | None = None
    extension_tel: str | None = None
    email: str | None = None
    regimen: str | None = None
    tipo_regimen_iva: str | None = None
    codigo_responsabilidad: str | None = None
    cuenta_pagar: str | None = None
    nombres_contacto: str | None = None
    apellidos_contacto: str | None = None
    indicativo_tel_contacto: int | None = None
    telefono_contacto: str | None = None
    extension_tel_contacto: str | None = None
    email_contacto: str | None = None
    es_cliente: bool = False
    activo: bool = True
    ia_habilitada: bool | None = None
    fuente: str | None = None
    empresa_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ExportarTercerosBody(BaseModel):
    ids: list[int] = []  # vacío = exportar todos


class TerceroUpdate(BaseModel):
    """Campos editables desde la UI. Todos opcionales."""
    tipo_identificacion: int | None = None
    codigo_sucursal: str | None = None
    razon_social: str | None = None
    nombres_tercero: str | None = None
    apellidos_tercero: str | None = None
    nombre_comercial: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    departamento: str | None = None
    codigo_pais: str | None = None
    codigo_departamento: str | None = None
    codigo_ciudad_siigo: str | None = None
    codigo_postal: str | None = None
    indicativo_tel: int | None = None
    telefono: str | None = None
    extension_tel: str | None = None
    email: str | None = None
    tipo_regimen_iva: str | None = None
    codigo_responsabilidad: str | None = None
    cuenta_pagar: str | None = None
    nombres_contacto: str | None = None
    apellidos_contacto: str | None = None
    indicativo_tel_contacto: int | None = None
    telefono_contacto: str | None = None
    extension_tel_contacto: str | None = None
    email_contacto: str | None = None
    es_cliente: bool | None = None
    activo: bool | None = None
    ia_habilitada: bool | None = None
