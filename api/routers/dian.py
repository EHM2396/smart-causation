"""
Router: /dian – integración con el portal de Facturación Electrónica de la DIAN.

Permite al usuario (ya autenticado en la plataforma) traer sus facturas
RECIBIDAS directamente de la DIAN usando una URL AuthToken que obtiene tras
loguearse él mismo en el portal, en vez de subir XML/ZIP/PDF manualmente.

Flujo:
  POST /dian/consultar  → lista de facturas del rango (rápido, sin descargas)
  POST /dian/importar   → trae los XML seleccionados EN MEMORIA, los parsea y
                          devuelve las facturas listas para causar (mismo shape
                          que /causacion/parsear).
"""

from __future__ import annotations

import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies import get_empresa_activa
from core.parser import usar_cliente_como_tercero
from db.models.auth import Empresa
from services import causacion_service, dian_service
from services.dian_service import DianError

router = APIRouter(prefix="/dian", tags=["DIAN"])

EmpresaActiva = Annotated[Empresa, Depends(get_empresa_activa)]


# ── Esquemas ──────────────────────────────────────────────────────────────────

class ConsultarRequest(BaseModel):
    auth_url: str = Field(..., description="URL completa de AuthToken de la DIAN")
    fecha_desde: str = Field(..., description="DD/MM/YYYY")
    fecha_hasta: str = Field(..., description="DD/MM/YYYY")
    modo: str = Field("compras", description="'compras' (recibidos) | 'ventas' (emitidos)")


class DocumentoDian(BaseModel):
    id: str | None
    numero: str
    fecha: str
    proveedor: str
    tipo: str


class ConsultarResponse(BaseModel):
    success: bool
    total: int
    documents: list[DocumentoDian]


class ImportarRequest(BaseModel):
    auth_url: str
    ids: list[str] = Field(..., description="DT_RowId de las facturas a importar")
    modo: str = Field("compras", description="'compras' (recibidos) | 'ventas' (emitidos)")


class ConsultarTodoRequest(BaseModel):
    """Consulta unificada: recibidos (compras) + emitidos (ventas) con un solo token."""
    auth_url: str = Field(..., description="URL completa de AuthToken de la DIAN")
    fecha_desde: str = Field(..., description="DD/MM/YYYY")
    fecha_hasta: str = Field(..., description="DD/MM/YYYY")


class ImportarTodoRequest(BaseModel):
    """Importación unificada: los ids se separan por origen (recibidos/emitidos)."""
    auth_url: str
    ids_compras: list[str] = Field(default_factory=list, description="DT_RowId de recibidos")
    ids_ventas: list[str] = Field(default_factory=list, description="DT_RowId de emitidos")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mapear_error(e: DianError) -> HTTPException:
    """Traduce un DianError a HTTP con mensaje claro para el frontend.

    IMPORTANTE: nunca usar 401 aquí. El frontend interpreta un 401 como que la
    sesión del USUARIO (su JWT) expiró y lo desloguea. Los errores de token/
    sesión de la DIAN son errores de negocio → 400, para no cerrar la sesión.
    """
    if e.code == "CONNECTION_ERROR":
        status = 504
    elif e.code in ("TOKEN_EXPIRED", "TOKEN_INVALID", "SESSION_EXPIRED"):
        status = 400
    else:
        status = 502
    return HTTPException(status_code=status, detail=e.message)


def _filtrar_por_modo(facturas: list[dict], empresa: Empresa, modo: str = "compras") -> list[dict]:
    """Malla de seguridad para el import de la DIAN.

    Los documentos YA vienen del endpoint correcto (``/Document/Received`` para
    compras, ``/Document/Sent`` para ventas), así que la fuente ya garantiza el
    tipo. Por eso este filtro NUNCA debe descartar todo por un NIT que no calza
    exacto (dígito de verificación/formato distinto entre el XML y el guardado):

      - ``ventas``: vienen de *emitidos* → son ventas de la empresa. Se conservan
        TODAS (antes se caían cuando el NIT del emisor no coincidía exacto).
      - ``compras``: vienen de *recibidos*. Se quitan, solo por seguridad, las que
        resulten ser ventas propias (emisor == NIT de la empresa); en la práctica
        el endpoint de recibidos no las trae.
    """
    es_venta = (modo or "compras").lower() == "ventas"
    if es_venta:
        return facturas
    if not empresa.nit:
        return facturas
    nit_empresa = re.sub(r"[^\d]", "", empresa.nit)
    if not nit_empresa:
        return facturas
    compras, ventas = [], []
    for fac in facturas:
        nit_emisor = re.sub(r"[^\d]", "", fac.get("nit", "") or "")
        (ventas if (nit_emisor and nit_emisor == nit_empresa) else compras).append(fac)
    if ventas and compras:
        compras[0].setdefault("advertencias", []).append(
            f"{len(ventas)} factura(s) de venta omitida(s) (son ventas de tu empresa, no compras)."
        )
    return compras


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/consultar", response_model=ConsultarResponse)
def consultar(body: ConsultarRequest, empresa: EmpresaActiva):
    """Lista las facturas recibidas de la DIAN en el rango de fechas (sin descargar XML)."""
    try:
        return dian_service.consultar_documentos(
            body.auth_url, body.fecha_desde, body.fecha_hasta, modo=body.modo
        )
    except DianError as e:
        raise _mapear_error(e)


@router.post("/importar")
def importar(body: ImportarRequest, empresa: EmpresaActiva):
    """
    Trae los XML seleccionados EN MEMORIA, los parsea y los devuelve listos para
    causar. Responde en streaming NDJSON para informar el PROGRESO REAL de
    descarga (una línea por factura), y una línea final con las facturas.

    Formato de las líneas (una por línea, JSON):
      {"type":"start","total":N}
      {"type":"progress","done":i,"total":N}
      {"type":"done","facturas":[...],"errores":k}
      {"type":"error","code":"...","message":"..."}
    """
    if not body.ids:
        raise HTTPException(400, "No se seleccionaron facturas para importar.")

    def gen():
        facturas: list[dict] = []
        errores = 0
        emitido_start = False
        try:
            for done, total, id_, xml in dian_service.descargar_xmls_stream(body.auth_url, body.ids, modo=body.modo):
                if not emitido_start:
                    yield json.dumps({"type": "start", "total": total}) + "\n"
                    emitido_start = True
                nombre = dian_service.nombre_para_parser(xml, id_)
                try:
                    facturas.extend(causacion_service.parsear_archivo(xml, nombre))
                except Exception:  # noqa: BLE001 — un XML malo no debe tumbar el lote
                    errores += 1
                yield json.dumps({"type": "progress", "done": done, "total": total}) + "\n"

            facturas = _filtrar_por_modo(facturas, empresa, modo=body.modo)
            if (body.modo or "compras").lower() == "ventas":
                # En ventas el tercero es el cliente (receptor), no la empresa emisora.
                facturas = [usar_cliente_como_tercero(f) for f in facturas]
            if errores and facturas:
                facturas[0].setdefault("advertencias", []).append(
                    f"{errores} factura(s) no se pudieron parsear y se omitieron."
                )
            yield json.dumps({"type": "done", "facturas": facturas, "errores": errores}) + "\n"
        except DianError as e:
            yield json.dumps({"type": "error", "code": e.code, "message": e.message}) + "\n"

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ── Importación UNIFICADA (un solo token → compras, NC compras, ventas, NC ventas) ──

@router.post("/consultar-todo")
def consultar_todo(body: ConsultarTodoRequest, empresa: EmpresaActiva):
    """Con un solo token, lista TODO en el rango: recibidos (compras) y emitidos
    (ventas). La sesión DIAN se reutiliza (cacheada por token), así que las dos
    consultas usan la misma autenticación."""
    try:
        compras = dian_service.consultar_documentos(
            body.auth_url, body.fecha_desde, body.fecha_hasta, modo="compras"
        )
        ventas = dian_service.consultar_documentos(
            body.auth_url, body.fecha_desde, body.fecha_hasta, modo="ventas"
        )
    except DianError as e:
        raise _mapear_error(e)
    return {"compras": compras, "ventas": ventas}


def _bucket_de(factura: dict, origen: str) -> str | None:
    """Clasifica una factura ya parseada en su módulo destino.

    El ORIGEN manda (recibidos=compra, emitidos=venta); el tipo de documento
    separa factura de nota crédito. Las notas débito se omiten (no hay módulo).
    """
    td = (factura.get("tipo_documento") or "factura").lower()
    if td == "nota_debito":
        return None
    if origen == "ventas":
        return "nc_ventas" if td == "nota_credito" else "ventas"
    return "nc" if td == "nota_credito" else "compras"


@router.post("/importar-todo")
def importar_todo(body: ImportarTodoRequest, empresa: EmpresaActiva):
    """Descarga y parsea recibidos + emitidos con un solo token, y devuelve las
    facturas ya clasificadas en 4 grupos: compras, nc, ventas, nc_ventas.
    Responde en streaming NDJSON con progreso real; la línea final trae los grupos.

    Líneas: {"type":"start","total":N} · {"type":"progress","done":i,"total":N}
            {"type":"done","buckets":{...},"errores":k} · {"type":"error",...}
    """
    if not body.ids_compras and not body.ids_ventas:
        raise HTTPException(400, "No se seleccionaron facturas para importar.")

    total = len(body.ids_compras) + len(body.ids_ventas)

    def gen():
        buckets: dict[str, list[dict]] = {"compras": [], "nc": [], "ventas": [], "nc_ventas": []}
        errores = 0
        done = 0
        yield json.dumps({"type": "start", "total": total}) + "\n"
        try:
            for origen, ids in (("compras", body.ids_compras), ("ventas", body.ids_ventas)):
                if not ids:
                    continue
                for _d, _t, id_, xml in dian_service.descargar_xmls_stream(body.auth_url, ids, modo=origen):
                    done += 1
                    try:
                        nombre = dian_service.nombre_para_parser(xml, id_)
                        for fac in causacion_service.parsear_archivo(xml, nombre):
                            destino = _bucket_de(fac, origen)
                            if destino is None:
                                continue
                            if origen == "ventas":
                                fac = usar_cliente_como_tercero(fac)
                            buckets[destino].append(fac)
                    except Exception:  # noqa: BLE001 — un XML malo no debe tumbar el lote
                        errores += 1
                    yield json.dumps({"type": "progress", "done": done, "total": total}) + "\n"

            yield json.dumps({"type": "done", "buckets": buckets, "errores": errores}) + "\n"
        except DianError as e:
            yield json.dumps({"type": "error", "code": e.code, "message": e.message}) + "\n"

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
