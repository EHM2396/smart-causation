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

import logging
from datetime import date
from io import BytesIO
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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

from dataclasses import dataclass as _dataclass

@_dataclass
class ResultadoSugerencia:
    cuenta: str | None
    origen: str | None
    explicacion: str | None = None
    confianza: float | None = None
    cuenta_pago: str | None = None
    cuenta_pago_origen: str | None = None  # 'aprendizaje' | 'ia_alta' | 'ia_media' | 'ia_baja'


def _obtener_cuentas_pago_batch(
    db: Session,
    nits: list[str],
    empresa_id: int | None,
) -> dict[str, str]:
    """Lookup en lote de cuenta_pago para múltiples NITs desde el historial. Una sola query."""
    if not nits:
        return {}
    import json as _json
    from sqlalchemy import select as _select
    stmt = (
        _select(FacturaCausada.nit_proveedor, FacturaCausada.datos_json)
        .where(
            FacturaCausada.nit_proveedor.in_(nits),
            FacturaCausada.datos_json.is_not(None),
        )
        .order_by(FacturaCausada.id.desc())
    )
    if empresa_id is not None:
        stmt = stmt.where(FacturaCausada.empresa_id == empresa_id)
    rows = db.execute(stmt).all()
    resultado: dict[str, str] = {}
    for nit_prov, datos_str in rows:
        if nit_prov in resultado:
            continue  # ya tenemos el más reciente para este NIT
        try:
            data = _json.loads(datos_str)
            for m in data.get("mapeos", []):
                cp = m.get("cuenta_pago")
                if cp:
                    resultado[nit_prov] = cp
                    break
        except Exception:
            pass
    return resultado


def _obtener_cuenta_pago_anterior(
    db: Session,
    nit: str | None,
    empresa_id: int | None,
) -> str | None:
    """Busca la cuenta_pago más reciente usada para este NIT en causaciones previas."""
    if not nit:
        return None
    import json as _json
    from sqlalchemy import select as _select
    stmt = (
        _select(FacturaCausada.datos_json)
        .where(
            FacturaCausada.nit_proveedor == nit,
            FacturaCausada.datos_json.is_not(None),
        )
        .order_by(FacturaCausada.id.desc())
        .limit(1)
    )
    if empresa_id is not None:
        stmt = stmt.where(FacturaCausada.empresa_id == empresa_id)
    datos_str = db.scalar(stmt)
    if not datos_str:
        return None
    try:
        data = _json.loads(datos_str)
        for m in data.get("mapeos", []):
            cp = m.get("cuenta_pago")
            if cp:
                return cp
    except Exception:
        pass
    return None


def sugerir_cuenta_gasto(
    db: Session,
    *,
    nit: str | None,
    descripcion: str,
    empresa_id: int | None = None,
    usuario_id: int | None = None,
    tipo_proveedor: str = "juridica",
    cuentas_pago: list[dict] | None = None,
) -> ResultadoSugerencia:
    """
    Intenta encontrar la mejor cuenta de gasto para un ítem de factura.
    Orden de prioridad:
      1. Reglas de clasificación activas (mayor prioridad + tipo)
      2. Mapeos aprendidos previos (NIT + keyword)
      3. IA (OpenAI) — fallback cuando no hay regla ni mapeo aprendido

    También sugiere cuenta_pago: primero desde historial de causaciones del NIT,
    luego desde IA cuando cuentas_pago está disponible.
    """
    # Lookup cuenta_pago desde historial (aprendizaje a nivel de proveedor)
    cp_anterior = _obtener_cuenta_pago_anterior(db, nit, empresa_id)

    # 1. Reglas de clasificación
    cuenta = aprendizaje_service.aplicar_reglas(db, descripcion)
    if cuenta:
        return ResultadoSugerencia(
            cuenta=cuenta, origen="regla",
            cuenta_pago=cp_anterior,
            cuenta_pago_origen="aprendizaje" if cp_anterior else None,
        )

    # 2. Mapeo aprendido
    cuenta = aprendizaje_service.obtener_mapeo(db, nit, descripcion, empresa_id=empresa_id, usuario_id=usuario_id)
    if cuenta:
        return ResultadoSugerencia(
            cuenta=cuenta, origen="aprendizaje",
            cuenta_pago=cp_anterior,
            cuenta_pago_origen="aprendizaje" if cp_anterior else None,
        )

    # 3. IA — fallback cuando no hay datos aprendidos
    try:
        from services import ai_service
        ia_ok = ai_service.esta_disponible()
        logger.warning("[IA-DEBUG] esta_disponible=%s desc=%r empresa=%s", ia_ok, descripcion[:40], empresa_id)
        if not ia_ok:
            return ResultadoSugerencia(
                cuenta=None, origen="ia_no_disponible",
                cuenta_pago=cp_anterior,
                cuenta_pago_origen="aprendizaje" if cp_anterior else None,
            )

        cuentas_gasto_list = cuentas_service.listar_cuentas_gasto(db, empresa_id=empresa_id)
        logger.warning("[IA-DEBUG] cuentas_gasto=%d para empresa_id=%s", len(cuentas_gasto_list), empresa_id)
        if not cuentas_gasto_list:
            return ResultadoSugerencia(
                cuenta=None, origen="sin_catalogo",
                cuenta_pago=cp_anterior,
                cuenta_pago_origen="aprendizaje" if cp_anterior else None,
            )

        codigos_imp = impuestos_service.listar_como_dict(db, empresa_id=empresa_id)
        sug = ai_service.sugerir(
            descripcion=descripcion,
            cuentas_gasto=[{"codigo": c["codigo"], "nombre": c["nombre"]} for c in cuentas_gasto_list],
            codigos_impuesto=codigos_imp,
            tipo_proveedor=tipo_proveedor,
            cuentas_pago=cuentas_pago,
        )
        logger.warning("[IA-DEBUG] sug=%s", sug)
        if sug and sug.cuenta_gasto:
            if sug.confianza >= 0.80:
                origen_ia = "ia_alta"
            elif sug.confianza >= 0.50:
                origen_ia = "ia_media"
            else:
                origen_ia = "ia_baja"
            # cuenta_pago: historial tiene prioridad sobre IA
            cp_final = cp_anterior or sug.cuenta_pago
            cp_origen = ("aprendizaje" if cp_anterior else (origen_ia if sug.cuenta_pago else None))
            return ResultadoSugerencia(
                cuenta=sug.cuenta_gasto,
                origen=origen_ia,
                explicacion=sug.explicacion,
                confianza=sug.confianza,
                cuenta_pago=cp_final,
                cuenta_pago_origen=cp_origen,
            )
    except Exception as exc:
        logger.warning("[IA-DEBUG] excepción: %s", exc, exc_info=True)

    return ResultadoSugerencia(
        cuenta=None, origen=None,
        cuenta_pago=cp_anterior,
        cuenta_pago_origen="aprendizaje" if cp_anterior else None,
    )


def sugerir_cuentas_batch(
    db: Session,
    *,
    items: list[dict],
    empresa_id: int | None = None,
    usuario_id: int | None = None,
    cuentas_pago: list[dict] | None = None,
) -> dict[str, ResultadoSugerencia]:
    """
    Sugiere cuentas para múltiples ítems en una sola operación.
    Orden de prioridad por ítem: reglas → aprendizaje → IA.
    Minimiza queries DB: reglas se cargan 1 vez, aprendizaje en 1 query, IA se deduplica por descripción.
    """
    if not items:
        return {}

    resultados: dict[str, ResultadoSugerencia] = {}

    # 1. Cargar reglas una sola vez (1 query para todos los ítems)
    reglas = aprendizaje_service.cargar_reglas(db)

    # 2. Aplicar reglas (puro Python, sin DB)
    sin_regla: list[dict] = []
    for item in items:
        cuenta = aprendizaje_service.aplicar_reglas_cargadas(reglas, item["descripcion"])
        if cuenta:
            resultados[item["key"]] = ResultadoSugerencia(cuenta=cuenta, origen="regla")
        else:
            sin_regla.append(item)

    # 3. Aprendizaje en lote para los que no tienen regla (1 query)
    sin_aprendizaje: list[dict] = []
    if sin_regla:
        mapeos = aprendizaje_service.obtener_mapeos_batch(
            db, sin_regla, empresa_id=empresa_id, usuario_id=usuario_id
        )
        for item in sin_regla:
            cuenta = mapeos.get(item["key"])
            if cuenta:
                resultados[item["key"]] = ResultadoSugerencia(cuenta=cuenta, origen="aprendizaje")
            else:
                sin_aprendizaje.append(item)

    # 4. Cuenta de pago en lote para todos los NITs únicos (1 query)
    nits_unicos = list({item["nit"] for item in items if item.get("nit")})
    cp_por_nit = _obtener_cuentas_pago_batch(db, nits_unicos, empresa_id)

    # Inyectar cuenta_pago a los ya resueltos por regla/aprendizaje
    for key, res in resultados.items():
        item = next((i for i in items if i["key"] == key), None)
        if item:
            nit = item.get("nit")
            cp = cp_por_nit.get(nit) if nit else None
            if cp:
                res.cuenta_pago = cp
                res.cuenta_pago_origen = "aprendizaje"

    # 5. IA para los ítems sin regla ni aprendizaje
    if sin_aprendizaje:
        ia_ok = False
        cuentas_gasto_opts: list[dict] = []
        codigos_imp: dict = {}
        try:
            from services import ai_service
            ia_ok = ai_service.esta_disponible()
            if ia_ok:
                cuentas_gasto_list = cuentas_service.listar_cuentas_gasto(db, empresa_id=empresa_id)
                if cuentas_gasto_list:
                    codigos_imp = impuestos_service.listar_como_dict(db, empresa_id=empresa_id)
                    cuentas_gasto_opts = [{"codigo": c["codigo"], "nombre": c["nombre"]} for c in cuentas_gasto_list]
                else:
                    ia_ok = False
        except Exception as exc:
            logger.warning("[batch-sugerir] setup IA falló: %s", exc)
            ia_ok = False

        if ia_ok and cuentas_gasto_opts:
            # 1 sola llamada a la IA con todos los ítems únicos
            items_para_batch = [
                {
                    "key": item["key"],
                    "descripcion": item["descripcion"],
                    "tipo_proveedor": item.get("tipo_proveedor"),
                }
                for item in sin_aprendizaje
            ]
            ai_results_by_key = ai_service.sugerir_batch(
                items=items_para_batch,
                cuentas_gasto=cuentas_gasto_opts,
                codigos_impuesto=codigos_imp,
                cuentas_pago=cuentas_pago,
            )

            for item in sin_aprendizaje:
                sug = ai_results_by_key.get(item["key"])
                nit = item.get("nit")
                cp = cp_por_nit.get(nit) if nit else None
                if sug and sug.cuenta_gasto:
                    confianza = sug.confianza or 0.0
                    if confianza >= 0.80:
                        origen_ia = "ia_alta"
                    elif confianza >= 0.50:
                        origen_ia = "ia_media"
                    else:
                        origen_ia = "ia_baja"
                    cp_final = cp or sug.cuenta_pago
                    cp_origen = "aprendizaje" if cp else (origen_ia if sug.cuenta_pago else None)
                    resultados[item["key"]] = ResultadoSugerencia(
                        cuenta=sug.cuenta_gasto,
                        origen=origen_ia,
                        explicacion=sug.explicacion,
                        confianza=sug.confianza,
                        cuenta_pago=cp_final,
                        cuenta_pago_origen=cp_origen,
                    )
                else:
                    resultados[item["key"]] = ResultadoSugerencia(
                        cuenta=None, origen=None,
                        cuenta_pago=cp, cuenta_pago_origen="aprendizaje" if cp else None,
                    )
        else:
            # IA no disponible o sin catálogo de cuentas
            origen_fallback = "sin_catalogo" if ia_ok else "ia_no_disponible"
            for item in sin_aprendizaje:
                nit = item.get("nit")
                cp = cp_por_nit.get(nit) if nit else None
                resultados[item["key"]] = ResultadoSugerencia(
                    cuenta=None, origen=origen_fallback,
                    cuenta_pago=cp, cuenta_pago_origen="aprendizaje" if cp else None,
                )

    return resultados


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
    empresa_id: int | None = None,
    usuario_id: int | None = None,
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
        empresa_id=empresa_id,
        usuario_id=usuario_id,
    )

    aprendizaje_service.registrar_mapeo(
        db,
        nit=nit,
        descripcion=descripcion,
        cuenta_puc=cuenta_aplicada,
        empresa_id=empresa_id,
        usuario_id=usuario_id,
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
    empresa_id: int | None = None,
) -> tuple[bytes, int]:
    """
    Genera el xlsx de importación SIIGO para una factura.

    Retorna:
        (bytes_del_archivo, consecutivo_asignado)
    """
    consecutivo = consecutivos_service.siguiente(db, prefijo, empresa_id=empresa_id)

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
    empresa_id: int | None = None,
) -> FacturaCausada:
    from sqlalchemy import select
    numero = factura.get("numero_dian") or factura.get("numero_factura", "")
    hoy = date.today()

    # Si ya existe para esta empresa, devolver el registro existente sin error
    stmt = select(FacturaCausada).where(FacturaCausada.numero_dian == numero)
    if empresa_id is not None:
        stmt = stmt.where(FacturaCausada.empresa_id == empresa_id)
    existente = db.scalar(stmt)
    if existente is not None:
        return existente

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
        empresa_id=empresa_id,
    )
    db.add(fc)
    db.flush()
    return fc


def esta_causada(db: Session, numero_dian: str, empresa_id: int | None = None) -> bool:
    from sqlalchemy import select
    stmt = select(FacturaCausada.id).where(FacturaCausada.numero_dian == numero_dian)
    if empresa_id is not None:
        stmt = stmt.where(FacturaCausada.empresa_id == empresa_id)
    return db.scalar(stmt) is not None


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
