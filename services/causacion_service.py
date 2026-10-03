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
import re
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


# ── Naturaleza contable del documento ────────────────────────────────────────
# La cuenta principal de cada ítem depende de QUÉ es el documento, no de las
# palabras de su descripción: "cemento" es un gasto/costo cuando la empresa lo
# compra, un ingreso cuando lo vende y una devolución en ventas cuando el
# cliente lo devuelve. Reglas, aprendizaje e IA comparten el mismo vocabulario
# (palabras clave), así que sin este filtro lo aprendido en compras se colaba
# como sugerencia de ventas (y al revés).

NATURALEZA_COMPRA = "compra"                      # compras, NC compras, soporte
NATURALEZA_VENTA = "venta"                        # factura de venta → ingreso
NATURALEZA_DEVOLUCION_VENTA = "devolucion_venta"  # NC de venta → reversa el ingreso


def naturaleza_operacion(es_venta: bool, es_nota_credito: bool = False) -> str:
    """Naturaleza contable de la cuenta principal de los ítems del documento."""
    if not es_venta:
        return NATURALEZA_COMPRA
    return NATURALEZA_DEVOLUCION_VENTA if es_nota_credito else NATURALEZA_VENTA


def es_cuenta_devolucion_venta(codigo: str, nombre: str | None = "") -> bool:
    """Cuenta de devoluciones/rebajas en ventas: la 4175 del PUC (ingreso de
    naturaleza débito) o una cuenta de ingreso que así se llame en el catálogo."""
    codigo = str(codigo or "").strip()
    if codigo.startswith("4175"):
        return True
    return codigo.startswith("4") and "devoluc" in (nombre or "").lower()


def cuentas_para_naturaleza(cuentas_ingreso: list[dict], naturaleza: str) -> list[dict]:
    """De las cuentas de ingreso (clase 4), las que aplican a la naturaleza:
      - venta: los ingresos, SIN las devoluciones en ventas.
      - devolución en venta: solo las devoluciones en ventas. Si el catálogo no
        tiene ninguna, la nota crédito reversa directamente la cuenta de ingreso.
    """
    devoluciones = [
        c for c in cuentas_ingreso if es_cuenta_devolucion_venta(c["codigo"], c.get("nombre"))
    ]
    if naturaleza == NATURALEZA_DEVOLUCION_VENTA:
        return devoluciones or list(cuentas_ingreso)
    ingresos = [c for c in cuentas_ingreso if c not in devoluciones]
    return ingresos or list(cuentas_ingreso)


def cuenta_coherente(codigo: str | None, naturaleza: str, validas: set[str] | None = None) -> bool:
    """¿La cuenta sirve como cuenta principal de un ítem de esta naturaleza?
      - compra: cualquier cuenta menos un ingreso (clase 4).
      - venta / devolución: una de las cuentas `validas` para esa naturaleza
        (ver cuentas_para_naturaleza); sin catálogo, al menos de clase 4.
        Nunca una cuenta de costo o gasto.
    """
    codigo = str(codigo or "").strip()
    if not codigo:
        return False
    if naturaleza == NATURALEZA_COMPRA:
        return not codigo.startswith("4")
    if validas:
        return codigo in validas
    return codigo.startswith("4")


def _cuenta_pago_por_forma_pago(
    forma_pago: str | None,
    medio_pago: str | None,
    cuentas_pago: list[dict] | None,
    es_venta: bool = False,
) -> tuple[str | None, str | None]:
    """
    Determina cuenta de contrapartida y su origen según la forma/medio de pago.
    Retorna (codigo_cuenta | None, origen | None).

    COMPRAS (lo que debes / cómo pagaste):
      CRÉDITO de cualquier medio            → 2205x (proveedores nacionales)
      CONTADO + efectivo                    → 1105x (caja general)
      CONTADO + transferencia/débito/tarjeta→ 1110x (bancos)

    VENTAS (lo que te deben / cómo cobraste):
      CRÉDITO de cualquier medio            → 1305x (clientes nacionales)
      CONTADO + efectivo                    → 1105x (caja general)
      CONTADO + transferencia/débito/tarjeta→ 1110x (bancos)
    """
    fp = (forma_pago or "").lower()
    mp = (medio_pago or "").lower()

    if "crédit" in fp or "credit" in fp:
        prefix = "1305" if es_venta else "2205"
    elif "efect" in mp:
        prefix = "1105"
    elif any(kw in mp for kw in ("transfer", "débit", "debit", "tarjeta")):
        prefix = "1110"
    else:
        return None, None

    # Buscar en el catálogo la cuenta hoja que empiece con el prefijo
    for cuenta in (cuentas_pago or []):
        codigo = str(cuenta.get("codigo", ""))
        if codigo.startswith(prefix):
            return codigo, "forma_pago"

    # Si no hay catálogo, retornar el prefijo base para que el frontend lo muestre
    if not cuentas_pago:
        return prefix, "forma_pago"
    return None, None


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

    # 2. Mapeo aprendido (propio del tercero o del mismo ítem en otro proveedor)
    mapeo = aprendizaje_service.obtener_mapeo(db, nit, descripcion, empresa_id=empresa_id, usuario_id=usuario_id)
    if mapeo:
        cuenta, es_otro = mapeo
        return ResultadoSugerencia(
            cuenta=cuenta, origen="aprendizaje_otro" if es_otro else "aprendizaje",
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


def _obtener_ejemplos_aprendizaje(
    db: Session,
    empresa_id: int | None,
    cuentas_gasto_opts: list[dict],
    limit: int = 200,
) -> list[dict]:
    """
    Carga decisiones recientes confirmadas de la empresa para usar como ejemplos
    en el prompt de la IA. Retorna lista de {descripcion, cuenta, nombre_cuenta}.
    Si el historial está vacío (usuario nuevo), retorna lista vacía sin error.
    """
    try:
        from sqlalchemy import select
        from db.models.aprendizaje import HistorialDecision

        stmt = (
            select(HistorialDecision.descripcion_item, HistorialDecision.cuenta_aplicada)
            .where(
                HistorialDecision.cuenta_aplicada.is_not(None),
                HistorialDecision.descripcion_item.is_not(None),
            )
            .order_by(HistorialDecision.created_at.desc())
            .limit(limit)
        )
        if empresa_id is not None:
            stmt = stmt.where(HistorialDecision.empresa_id == empresa_id)

        rows = db.execute(stmt).all()

        # Índice de nombres de cuenta para enriquecer los ejemplos
        nombres_por_codigo = {c["codigo"]: c["nombre"] for c in cuentas_gasto_opts}

        seen: set[tuple] = set()
        result: list[dict] = []
        for desc, cuenta in rows:
            if not desc or not cuenta:
                continue
            key = (desc[:60].lower().strip(), cuenta)
            if key in seen:
                continue
            seen.add(key)
            nombre = nombres_por_codigo.get(cuenta, "")
            result.append({
                "descripcion": desc[:120],
                "cuenta": cuenta,
                "nombre_cuenta": nombre,
            })
            if len(result) >= 60:  # máximo 60 ejemplos únicos al prompt
                break

        return result
    except Exception as exc:
        logger.warning("[batch-sugerir] no se pudo cargar historial para IA: %s", exc)
        return []


def sugerir_cuentas_batch(
    db: Session,
    *,
    items: list[dict],
    empresa_id: int | None = None,
    usuario_id: int | None = None,
    cuentas_pago: list[dict] | None = None,
    es_venta: bool = False,
    es_nota_credito: bool = False,
) -> dict[str, ResultadoSugerencia]:
    """
    Sugiere cuentas para múltiples ítems en una sola operación.
    Orden de prioridad por ítem: reglas → aprendizaje → IA.
    Minimiza queries DB: reglas se cargan 1 vez, aprendizaje en 1 query, IA se deduplica por descripción.

    La NATURALEZA del documento (compra, venta o devolución en venta) decide qué
    cuentas son admisibles en las tres fuentes: en ventas solo ingresos (clase
    4), nunca costos ni gastos; en una nota crédito de venta, la cuenta de
    devoluciones en ventas (ver naturaleza_operacion).
    """
    if not items:
        return {}

    resultados: dict[str, ResultadoSugerencia] = {}
    naturaleza = naturaleza_operacion(es_venta, es_nota_credito)

    # 0. Cuentas admisibles para la naturaleza del documento (1 query)
    try:
        if naturaleza == NATURALEZA_COMPRA:
            candidatas = cuentas_service.listar_cuentas_gasto(db, empresa_id=empresa_id)
        else:
            candidatas = cuentas_para_naturaleza(
                cuentas_service.listar_cuentas_ingreso(db, empresa_id=empresa_id), naturaleza
            )
    except Exception as exc:
        logger.warning("[batch-sugerir] no se pudo cargar el catálogo de cuentas: %s", exc)
        candidatas = []
    validas = {c["codigo"] for c in candidatas}

    def _coherente(codigo: str) -> bool:
        return cuenta_coherente(codigo, naturaleza, validas)

    # 1. Cargar reglas una sola vez (1 query para todos los ítems)
    reglas = aprendizaje_service.cargar_reglas(db)

    # 2. Aplicar reglas (puro Python, sin DB)
    sin_regla: list[dict] = []
    for item in items:
        cuenta = aprendizaje_service.aplicar_reglas_cargadas(
            reglas, item["descripcion"], cuenta_valida=_coherente
        )
        if cuenta:
            resultados[item["key"]] = ResultadoSugerencia(cuenta=cuenta, origen="regla")
        else:
            sin_regla.append(item)

    # 3. Aprendizaje en lote para los que no tienen regla (1 query)
    sin_aprendizaje: list[dict] = []
    if sin_regla:
        mapeos = aprendizaje_service.obtener_mapeos_batch(
            db, sin_regla, empresa_id=empresa_id, usuario_id=usuario_id,
            cuenta_valida=_coherente,
        )
        for item in sin_regla:
            mapeo = mapeos.get(item["key"])
            if mapeo:
                cuenta, es_otro = mapeo
                resultados[item["key"]] = ResultadoSugerencia(
                    cuenta=cuenta, origen="aprendizaje_otro" if es_otro else "aprendizaje",
                )
            else:
                sin_aprendizaje.append(item)

    # 3b. Nota crédito de venta con UNA sola cuenta de devoluciones en ventas en el
    # catálogo: la cuenta sale de la naturaleza del documento, sin adivinar.
    if naturaleza == NATURALEZA_DEVOLUCION_VENTA and sin_aprendizaje:
        devoluciones = [c for c in candidatas if es_cuenta_devolucion_venta(c["codigo"], c.get("nombre"))]
        if len(devoluciones) == 1:
            for item in sin_aprendizaje:
                resultados[item["key"]] = ResultadoSugerencia(
                    cuenta=devoluciones[0]["codigo"], origen="devolucion_venta",
                    explicacion="Nota crédito de venta: reversa el ingreso",
                )
            sin_aprendizaje = []

    # 4. Cuenta de pago por item (regla determinista > historial NIT)
    nits_unicos = list({item["nit"] for item in items if item.get("nit")})
    cp_por_nit = _obtener_cuentas_pago_batch(db, nits_unicos, empresa_id)

    # La contrapartida aprendida del tercero debe ser del módulo actual: el
    # historial es por NIT y no distingue compras de ventas, así que un tercero que
    # es proveedor y cliente heredaba en la venta su cuenta de proveedores (2205).
    codigos_pago = {str(c.get("codigo", "")) for c in (cuentas_pago or [])}

    def _contrapartida_coherente(cp: str) -> bool:
        if codigos_pago:
            return cp in codigos_pago
        return cuentas_service.es_contrapartida(cp, es_venta=es_venta)

    # cp_por_key: llave de item → (codigo_cuenta, origen)
    # Regla forma_pago tiene máxima prioridad; si no aplica, usa historial del NIT
    cp_por_key: dict[str, tuple[str | None, str | None]] = {}
    for item in items:
        k = item["key"]
        codigo, origen = _cuenta_pago_por_forma_pago(
            item.get("forma_pago"), item.get("medio_pago"), cuentas_pago, es_venta=es_venta
        )
        if codigo:
            cp_por_key[k] = (codigo, origen)
        else:
            nit = item.get("nit")
            cp_hist = cp_por_nit.get(nit) if nit else None
            if cp_hist and not _contrapartida_coherente(cp_hist):
                cp_hist = None
            cp_por_key[k] = (cp_hist, "aprendizaje" if cp_hist else None)

    # Inyectar cuenta_pago a los ya resueltos por regla/aprendizaje
    for key, res in resultados.items():
        cp, cp_orig = cp_por_key.get(key, (None, None))
        if cp:
            res.cuenta_pago = cp
            res.cuenta_pago_origen = cp_orig

    # 5. IA para los ítems sin regla ni aprendizaje
    if sin_aprendizaje:
        ia_ok = False
        cuentas_gasto_opts: list[dict] = []
        codigos_imp: dict = {}
        try:
            from services import ai_service
            ia_ok = ai_service.esta_disponible()
            if ia_ok:
                # La IA solo puede elegir entre las cuentas de la naturaleza del
                # documento: en ventas, ingresos; nunca la lista de gastos.
                if candidatas:
                    codigos_imp = impuestos_service.listar_como_dict(db, empresa_id=empresa_id)
                    cuentas_gasto_opts = [{"codigo": c["codigo"], "nombre": c["nombre"]} for c in candidatas]
                else:
                    ia_ok = False
        except Exception as exc:
            logger.warning("[batch-sugerir] setup IA falló: %s", exc)
            ia_ok = False

        if ia_ok and cuentas_gasto_opts:
            # Cargar historial de decisiones de la empresa como ejemplos para la IA.
            # Solo los de la misma naturaleza: un ejemplo de compra (gasto) le
            # enseñaría a la IA a causar una venta contra un gasto.
            ejemplos = [
                e for e in _obtener_ejemplos_aprendizaje(db, empresa_id, cuentas_gasto_opts)
                if _coherente(e["cuenta"])
            ]

            # 1 sola llamada a la IA con todos los ítems únicos
            items_para_batch = [
                {
                    "key": item["key"],
                    "descripcion": item["descripcion"],
                    "tipo_proveedor": item.get("tipo_proveedor"),
                    "nombre_proveedor": item.get("nombre_proveedor"),
                }
                for item in sin_aprendizaje
            ]
            ai_results_by_key = ai_service.sugerir_batch(
                items=items_para_batch,
                cuentas_gasto=cuentas_gasto_opts,
                codigos_impuesto=codigos_imp,
                # El prompt de la cuenta de pago está pensado para proveedores
                # (pago/acreedor). En ventas la contrapartida sale de la forma de
                # pago (crédito → Clientes 1305, contado → Caja/Bancos) o del
                # historial del cliente, no de la IA.
                cuentas_pago=cuentas_pago if naturaleza == NATURALEZA_COMPRA else None,
                ejemplos_aprendizaje=ejemplos,
                naturaleza=naturaleza,
            )

            for item in sin_aprendizaje:
                sug = ai_results_by_key.get(item["key"])
                cp, cp_orig = cp_por_key.get(item["key"], (None, None))
                if sug and sug.cuenta_gasto:
                    confianza = sug.confianza or 0.0
                    if confianza >= 0.80:
                        origen_ia = "ia_alta"
                    elif confianza >= 0.50:
                        origen_ia = "ia_media"
                    else:
                        origen_ia = "ia_baja"
                    # Regla determinista / historial tienen prioridad sobre IA
                    cp_final = cp or sug.cuenta_pago
                    cp_origen_final = cp_orig if cp else (origen_ia if sug.cuenta_pago else None)
                    resultados[item["key"]] = ResultadoSugerencia(
                        cuenta=sug.cuenta_gasto,
                        origen=origen_ia,
                        explicacion=sug.explicacion,
                        confianza=sug.confianza,
                        cuenta_pago=cp_final,
                        cuenta_pago_origen=cp_origen_final,
                    )
                else:
                    resultados[item["key"]] = ResultadoSugerencia(
                        cuenta=None, origen=None,
                        cuenta_pago=cp, cuenta_pago_origen=cp_orig,
                    )
        else:
            # IA no disponible o sin catálogo de cuentas
            origen_fallback = "sin_catalogo" if ia_ok else "ia_no_disponible"
            for item in sin_aprendizaje:
                cp, cp_orig = cp_por_key.get(item["key"], (None, None))
                resultados[item["key"]] = ResultadoSugerencia(
                    cuenta=None, origen=origen_fallback,
                    cuenta_pago=cp, cuenta_pago_origen=cp_orig,
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
        es_nota_credito=factura.get("tipo_documento") == "nota_credito",
    )

    validar_movimientos(movimientos)

    buf = exporter.exportar_xlsx(movimientos)
    return buf, consecutivo


# ── Orden cronológico de documentos ───────────────────────────────────────────
# Manda la FECHA DE EMISIÓN del XML (fecha_factura), nunca la de causación ni el
# orden en que se importó: un documento de agosto que se trajo después de los de
# septiembre va antes que ellos. Mismo día: factura antes que sus notas, luego
# prefijo y consecutivo (numérico). Espejo de frontend/src/lib/orden-documentos.ts.

_TIPOS_NOTA = {"nc", "nc_ventas", "nc_soporte", "nota_credito", "nota_debito", "nota_ajuste_soporte"}


def partes_numero(numero: str | None) -> tuple[str, str]:
    """(prefijo, consecutivo) del número DIAN: "FE0012" → ("FE", "0012"). El
    consecutivo se devuelve como TEXTO tal cual: solo se usa para comparar, el
    número del documento nunca se modifica."""
    n = str(numero or "").strip()
    m = re.match(r"^(.*?)(\d+)$", n)
    if not m:
        return n.upper(), ""
    return m.group(1).upper(), m.group(2)


def clave_cronologica(fecha: date | None, numero: str | None, tipo: str | None = None) -> tuple:
    """Clave de orden ascendente: fecha de emisión → factura antes que notas →
    prefijo → consecutivo numérico (sin convertirlo: no pierde precisión)."""
    prefijo, consecutivo = partes_numero(numero)
    significativo = consecutivo.lstrip("0")
    return (
        fecha or date.min,
        1 if (tipo or "").lower() in _TIPOS_NOTA else 0,
        prefijo,
        consecutivo == "",
        len(significativo),
        significativo,
    )


def ordenar_por_emision(
    filas: list,
    *,
    descendente: bool = False,
    fecha=lambda f: f.fecha_factura,
    numero=lambda f: f.numero_dian,
    tipo=lambda f: f.tipo_causacion,
) -> list:
    """Ordena documentos por fecha de emisión (ver clave_cronologica). Los que
    no tienen fecha de emisión válida van siempre al final."""
    con_fecha = [f for f in filas if fecha(f)]
    sin_fecha = [f for f in filas if not fecha(f)]
    con_fecha.sort(key=lambda f: clave_cronologica(fecha(f), numero(f), tipo(f)), reverse=descendente)
    return con_fecha + sin_fecha


def columna_fecha(campo_fecha: str | None):
    """Columna de FacturaCausada sobre la que aplica un rango de fechas:
    'emision' = fecha de la factura (la que puso quien la emitió); 'causacion'
    (por defecto) = fecha en que se causó en el sistema.

    Vive acá, y no en un router, porque la usan el historial y la analítica: si
    cada uno tuviera su copia, con el tiempo dejarían de filtrar igual y el mismo
    rango de fechas daría resultados distintos en cada pantalla.
    """
    return FacturaCausada.fecha_factura if campo_fecha == "emision" else FacturaCausada.fecha_causacion


# ── Registro de factura causada ───────────────────────────────────────────────

def derivar_tipo_causacion(factura: dict, es_venta: bool) -> str:
    """
    Módulo de causación al que pertenece una factura ya parseada, según su
    tipo_documento + si la operación es una venta. Mismos valores que DocTipo en
    el frontend: "compras" | "nc" | "ventas" | "nc_ventas" | "soporte" |
    "nc_soporte". Espejo de _bucket_de() en api/routers/dian.py (ahí también
    interviene el ORIGEN de la consulta DIAN; acá solo se tiene la factura ya
    causada, así que basta con tipo_documento).
    """
    td = (factura.get("tipo_documento") or "factura").lower()
    if td == "documento_soporte":
        return "soporte"
    if td == "nota_ajuste_soporte":
        return "nc_soporte"
    if es_venta:
        return "nc_ventas" if td == "nota_credito" else "ventas"
    return "nc" if td == "nota_credito" else "compras"


def base_gravable_de(factura: dict) -> float | None:
    """Suma de las bases de los ítems (sin IVA): la cifra que vale para
    costos/gastos/ingresos. None si la factura no trae ítems con base."""
    items = factura.get("items") or []
    if not items:
        return None
    try:
        return float(sum(float(it.get("base") or 0) for it in items))
    except (TypeError, ValueError):
        return None


def registrar_factura_causada(
    db: Session,
    *,
    factura: dict,
    consecutivo: int,
    tipo_comprobante: str,
    archivo_origen: str = "",
    datos_json: str | None = None,
    empresa_id: int | None = None,
    usuario_id: int | None = None,
    tipo_causacion: str | None = None,
) -> FacturaCausada:
    from sqlalchemy import select
    numero = factura.get("numero_dian") or factura.get("numero_factura", "")
    hoy = date.today()
    base = base_gravable_de(factura)

    # Si ya existe para esta empresa...
    stmt = select(FacturaCausada).where(FacturaCausada.numero_dian == numero)
    if empresa_id is not None:
        stmt = stmt.where(FacturaCausada.empresa_id == empresa_id)
    existente = db.scalar(stmt)
    if existente is not None:
        if not existente.eliminado:
            # ...y sigue activa: devolver el registro existente sin duplicar.
            return existente
        # ...pero el usuario la ELIMINÓ del historial: se reutiliza la misma fila
        # (nunca se borra de la BD) con los datos de esta nueva causación, en vez
        # de bloquearla como "ya causada". Así "eliminar del historial" permite
        # volver a causar la factura, como espera el usuario.
        existente.eliminado = False
        existente.eliminado_at = None
        existente.nit_proveedor = factura.get("nit")
        existente.razon_social = factura.get("razon_social")
        existente.fecha_factura = _parse_date(factura.get("fecha", ""))
        existente.total = factura.get("total", 0.0)
        existente.base_gravable = base
        existente.consecutivo = str(consecutivo)
        existente.tipo_comprobante = tipo_comprobante
        existente.fecha_causacion = hoy
        existente.archivo_origen = archivo_origen
        existente.datos_json = datos_json
        existente.tipo_causacion = tipo_causacion
        db.flush()
        return existente

    fc = FacturaCausada(
        numero_dian=numero,
        nit_proveedor=factura.get("nit"),
        razon_social=factura.get("razon_social"),
        fecha_factura=_parse_date(factura.get("fecha", "")),
        total=factura.get("total", 0.0),
        base_gravable=base,
        consecutivo=str(consecutivo),
        tipo_comprobante=tipo_comprobante,
        fecha_causacion=hoy,
        archivo_origen=archivo_origen,
        datos_json=datos_json,
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        tipo_causacion=tipo_causacion,
    )
    db.add(fc)
    db.flush()
    return fc


def esta_causada(db: Session, numero_dian: str, empresa_id: int | None = None) -> bool:
    from sqlalchemy import select
    # Una factura eliminada del historial NO cuenta como "ya causada": eliminarla
    # es precisamente cómo el usuario libera el número para volver a causarla.
    stmt = select(FacturaCausada.id).where(
        FacturaCausada.numero_dian == numero_dian,
        FacturaCausada.eliminado.is_(False),
    )
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
