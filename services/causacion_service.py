"""
CausacionService – orquesta el flujo completo de causación contable.

Este servicio es el corazón del sistema. Coordina:
  1. Parsing del archivo DIAN (core.parser)
  2. Sugerencia de cuentas PUC (aprendizaje + reglas)
  3. Registro del historial de decisiones
  4. Generación del archivo SIIGO (core.exporter)
  5. Persistencia del consecutivo y la factura causada

No tiene dependencias de Streamlit. Puede ser llamado desde:
  - FastAPI endpoints
  - Scripts de migración
  - Tests automatizados
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

from sqlalchemy.orm import Session

from core import exporter, parser
from core.validator import validar_movimientos
from db.models.contabilidad import FacturaCausada
from services import (
    aprendizaje_service,
    consecutivos_service,
    cuentas_service,
    impuestos_service,
)


# ── Parseo ────────────────────────────────────────────────────────────────────

def parsear_archivo(contenido: bytes, nombre_archivo: str = "") -> list[dict]:
    """
    Parsea un archivo DIAN (xlsx bytes) y retorna lista de facturas.
    Delega directamente a core.parser.
    """
    return parser.parsear_archivo(BytesIO(contenido), nombre_archivo)


# ── Sugerencia de cuentas ─────────────────────────────────────────────────────

def sugerir_cuenta_gasto(
    db: Session,
    *,
    nit: str | None,
    descripcion: str,
) -> str | None:
    """
    Intenta encontrar la mejor cuenta de gasto para un ítem de factura.
    Orden de prioridad:
      1. Reglas de clasificación activas (mayor prioridad + tipo)
      2. Mapeos aprendidos previos (NIT + keyword)
      3. None → el usuario debe seleccionarla manualmente
    """
    # 1. Reglas de clasificación
    cuenta = aprendizaje_service.aplicar_reglas(db, descripcion)
    if cuenta:
        return cuenta

    # 2. Mapeo aprendido
    cuenta = aprendizaje_service.obtener_mapeo(db, nit, descripcion)
    return cuenta


# ── Confirmación y aprendizaje ────────────────────────────────────────────────

def confirmar_mapeo(
    db: Session,
    *,
    numero_dian: str,
    nit: str | None,
    descripcion: str,
    cuenta_sugerida: str | None,
    cuenta_aplicada: str,
    cod_impuesto: str | None = None,
    origen: str = "manual",
) -> None:
    """
    Registra el mapeo confirmado por el usuario y actualiza el historial.
    Llama a registrar_mapeo para reforzar el aprendizaje.
    """
    fue_corregida = cuenta_sugerida != cuenta_aplicada and cuenta_sugerida is not None

    aprendizaje_service.registrar_decision(
        db,
        numero_dian=numero_dian,
        nit_proveedor=nit,
        descripcion_item=descripcion,
        cuenta_sugerida=cuenta_sugerida,
        cuenta_aplicada=cuenta_aplicada,
        cod_impuesto=cod_impuesto,
        fue_corregida=fue_corregida,
        origen=origen,
    )

    aprendizaje_service.registrar_mapeo(
        db,
        nit=nit,
        descripcion=descripcion,
        cuenta_puc=cuenta_aplicada,
    )


# ── Generación del archivo SIIGO ──────────────────────────────────────────────

def generar_siigo(
    db: Session,
    *,
    factura: dict,
    mapeos_confirmados: list[dict],
    tipo_comprobante: str = "12",
    centro_costo: str = "",
    prefijo: str = "FC",
) -> tuple[bytes, int]:
    """
    Genera el xlsx de importación SIIGO para una factura.

    Retorna:
        (bytes_del_archivo, consecutivo_asignado)
    """
    consecutivo = consecutivos_service.siguiente(db, prefijo)

    movimientos = exporter.construir_movimientos(
        factura=factura,
        consecutivo=consecutivo,
        mapeos_confirmados=mapeos_confirmados,
        tipo_comprobante=tipo_comprobante,
        centro_costo=centro_costo,
    )

    validar_movimientos(movimientos)

    buf = exporter.exportar_xlsx(movimientos)
    return buf, consecutivo


# ── Registro de factura causada ───────────────────────────────────────────────

def registrar_factura_causada(
    db: Session,
    *,
    factura: dict,
    consecutivo: int,
    tipo_comprobante: str,
    archivo_origen: str = "",
    datos_json: str | None = None,
) -> FacturaCausada:
    numero = factura.get("numero_dian") or factura.get("numero_factura", "")
    hoy = date.today()

    fc = FacturaCausada(
        numero_dian=numero,
        nit_proveedor=factura.get("nit"),
        razon_social=factura.get("razon_social"),
        fecha_factura=_parse_date(factura.get("fecha", "")),
        total=factura.get("total", 0.0),
        consecutivo=str(consecutivo),
        tipo_comprobante=tipo_comprobante,
        fecha_causacion=hoy,
        archivo_origen=archivo_origen,
        datos_json=datos_json,
    )
    db.add(fc)
    db.flush()
    return fc


def esta_causada(db: Session, numero_dian: str) -> bool:
    from sqlalchemy import select
    return db.scalar(
        select(FacturaCausada.id).where(FacturaCausada.numero_dian == numero_dian)
    ) is not None


# ── Helpers privados ──────────────────────────────────────────────────────────

def _parse_date(valor: Any) -> date | None:
    from datetime import datetime
    if not valor:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(valor), fmt).date()
        except ValueError:
            pass
    return None
