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


def _filtrar_ventas(facturas: list[dict], empresa: Empresa) -> list[dict]:
    """Quita facturas de venta (emisor == NIT de la empresa). Mismo criterio que /causacion/parsear."""
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
            body.auth_url, body.fecha_desde, body.fecha_hasta
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
            for done, total, id_, xml in dian_service.descargar_xmls_stream(body.auth_url, body.ids):
                if not emitido_start:
                    yield json.dumps({"type": "start", "total": total}) + "\n"
                    emitido_start = True
                nombre = dian_service.nombre_para_parser(xml, id_)
                try:
                    facturas.extend(causacion_service.parsear_archivo(xml, nombre))
                except Exception:  # noqa: BLE001 — un XML malo no debe tumbar el lote
                    errores += 1
                yield json.dumps({"type": "progress", "done": done, "total": total}) + "\n"

            facturas = _filtrar_ventas(facturas, empresa)
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
