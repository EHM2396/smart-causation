"""
Schemas Pydantic para el flujo de causación y aprendizaje.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Causación ─────────────────────────────────────────────────────────────────

class MapeoItem(BaseModel):
    """Mapeo confirmado por el usuario para un ítem de factura."""
    descripcion: str
    cuenta_gasto: str = Field(..., max_length=10)
    cod_impuesto: str = Field(..., max_length=10)
    porcentaje: float = 0.0
    cuenta_impuesto_deb: str = ""
    cuenta_impuesto_cre: str = ""
    base: float = 0.0
    valor_impuesto: float = 0.0
    cuenta_pago: str | None = None


class CausacionRequest(BaseModel):
    """Body para el endpoint POST /causacion/generar."""
    factura: dict                            # dict parseado por parsear_archivo
    mapeos_confirmados: list[MapeoItem]
    tipo_comprobante: str = "12"
    centro_costo: str = ""
    prefijo: str = "FC"


class CausacionResponse(BaseModel):
    consecutivo: int
    numero_dian: str
    archivo_nombre: str


# ── Sugerencia de cuenta ──────────────────────────────────────────────────────

class SugerenciaRequest(BaseModel):
    nit: str | None = None
    descripcion: str
    tipo_proveedor: str = "juridica"


class SugerenciaResponse(BaseModel):
    cuenta_sugerida: str | None
    origen: str | None = None        # 'regla' | 'aprendizaje' | 'ia_alta' | 'ia_media' | 'ia_baja' | None
    explicacion_ia: str | None = None
    confianza_ia: float | None = None
    cuenta_pago_sugerida: str | None = None
    cuenta_pago_origen: str | None = None  # 'aprendizaje' | 'ia_alta' | 'ia_media' | 'ia_baja' | None


class SugerenciaBatchItem(BaseModel):
    key: str                         # e.g. "0_0", "2_3"
    nit: str | None = None
    descripcion: str
    tipo_proveedor: str | None = None
    nombre_proveedor: str | None = None
    forma_pago: str | None = None    # "CRÉDITO" | "CONTADO" | …
    medio_pago: str | None = None    # "EFECTIVO" | "TRANSFERENCIA DÉBITO BANCARIA" | …


class SugerenciaBatchRequest(BaseModel):
    items: list[SugerenciaBatchItem]


class SugerenciaBatchResponse(BaseModel):
    resultados: dict[str, SugerenciaResponse]


class FacturaCausadaInfo(BaseModel):
    numero_dian: str
    nit_proveedor: str | None = None
    razon_social: str | None = None
    fecha_factura: str | None = None
    total: float | None = None
    consecutivo: str | None = None
    tipo_comprobante: str | None = None
    fecha_causacion: str | None = None
    datos_json: str | None = None  # JSON: {factura, mapeos, tipo_comprobante, centro_costo}


class VerificarCausadasRequest(BaseModel):
    numeros_dian: list[str]


class VerificarCausadasResponse(BaseModel):
    ya_causadas: list[FacturaCausadaInfo]


# ── Historial de decisiones ───────────────────────────────────────────────────

class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero_dian: str | None
    nit_proveedor: str | None
    descripcion_item: str | None
    cuenta_sugerida: str | None
    cuenta_aplicada: str | None
    cod_impuesto: str | None
    fue_corregida: bool
    origen: str | None
    created_at: datetime


# ── Reglas de clasificación ───────────────────────────────────────────────────

class ReglaCreate(BaseModel):
    patron: str
    cuenta_puc: str = Field(..., max_length=10)
    tipo: str = Field("keyword", pattern="^(keyword|regex)$")
    prioridad: int = 0
    version: int = 1


class ReglaOut(ReglaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    activa: bool
    created_at: datetime


# ── Borrador de causación (guardado temporal) ─────────────────────────────────

class BorradorGuardarRequest(BaseModel):
    """Body para PUT /causacion/borrador. `datos` es el snapshot completo del
    wizard (facturas + configuración de paso 2); los demás son metadatos ligeros
    para la tarjeta 'Continuar'."""
    datos: dict
    total_facturas: int = 0
    total_verificadas: int = 0
    tipo_comp: str | None = None


class BorradorResumen(BaseModel):
    """Metadatos del borrador, sin el snapshot pesado. Para saber si hay algo que
    retomar y mostrarlo en una tarjeta."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    total_facturas: int
    total_verificadas: int
    tipo_comp: str | None = None
    actualizado_at: datetime


class BorradorCompleto(BorradorResumen):
    """Borrador con el snapshot completo, para rehidratar el wizard al reanudar."""
    datos: dict
