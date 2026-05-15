"""
Router: /causacion – flujo principal de causación contable.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session

from api.schemas import (
    CausacionRequest,
    CausacionResponse,
    SugerenciaRequest,
    SugerenciaResponse,
)
from db.session import get_db
from services import causacion_service

router = APIRouter(prefix="/causacion", tags=["Causación"])

DB = Annotated[Session, Depends(get_db)]


@router.post("/parsear", response_model=list[dict])
async def parsear_facturas(
    archivo: UploadFile = File(..., description="Archivo XLSX de facturas DIAN"),
):
    """
    Paso 1: Recibe el archivo XLSX de facturas electrónicas DIAN y retorna
    la lista de facturas parseadas en formato dict.
    """
    contenido = await archivo.read()
    try:
        facturas = causacion_service.parsear_archivo(contenido, archivo.filename or "")
    except Exception as exc:
        raise HTTPException(400, f"Error al parsear el archivo: {exc}") from exc
    return facturas


@router.post("/sugerir-cuenta", response_model=SugerenciaResponse)
def sugerir_cuenta(body: SugerenciaRequest, db: DB):
    """
    Dado un NIT y una descripción de ítem, sugiere la cuenta de gasto PUC.
    Consulta reglas de clasificación y mapeos aprendidos.
    """
    cuenta = causacion_service.sugerir_cuenta_gasto(
        db, nit=body.nit, descripcion=body.descripcion
    )
    origen = None
    if cuenta:
        from services.aprendizaje_service import aplicar_reglas
        origen = "regla" if aplicar_reglas(db, body.descripcion) else "aprendizaje"

    return SugerenciaResponse(cuenta_sugerida=cuenta, origen=origen)


@router.post("/generar", response_model=CausacionResponse)
def generar_causacion(body: CausacionRequest, db: DB):
    """
    Paso final: genera el archivo SIIGO y registra la causación.
    Retorna metadatos; el archivo se descarga por /causacion/descargar/{numero_dian}.
    """
    numero_dian = body.factura.get("numero_dian", "")

    if causacion_service.esta_causada(db, numero_dian):
        raise HTTPException(409, f"La factura {numero_dian!r} ya fue causada")

    mapeos = [m.model_dump() for m in body.mapeos_confirmados]

    try:
        _bytes, consecutivo = causacion_service.generar_siigo(
            db,
            factura=body.factura,
            mapeos_confirmados=mapeos,
            tipo_comprobante=body.tipo_comprobante,
            centro_costo=body.centro_costo,
            prefijo=body.prefijo,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    # Confirmar mapeos aprendidos
    for m in mapeos:
        causacion_service.confirmar_mapeo(
            db,
            numero_dian=numero_dian,
            nit=body.factura.get("nit"),
            descripcion=m.get("descripcion", ""),
            cuenta_sugerida=None,
            cuenta_aplicada=m["cuenta_gasto"],
            cod_impuesto=m.get("cod_impuesto"),
        )

    causacion_service.registrar_factura_causada(
        db,
        factura=body.factura,
        consecutivo=consecutivo,
        tipo_comprobante=body.tipo_comprobante,
    )

    db.commit()

    nombre_archivo = f"importacion_SIIGO_{numero_dian}.xlsx"
    return CausacionResponse(
        consecutivo=consecutivo,
        numero_dian=numero_dian,
        archivo_nombre=nombre_archivo,
    )


@router.post("/generar-descarga")
def generar_y_descargar(body: CausacionRequest, db: DB):
    """
    Igual que /generar pero retorna el xlsx como descarga directa.
    Útil para integración rápida con la UI Streamlit mientras migra.
    """
    numero_dian = body.factura.get("numero_dian", "")

    if causacion_service.esta_causada(db, numero_dian):
        raise HTTPException(409, f"La factura {numero_dian!r} ya fue causada")

    mapeos = [m.model_dump() for m in body.mapeos_confirmados]

    try:
        xlsx_bytes, consecutivo = causacion_service.generar_siigo(
            db,
            factura=body.factura,
            mapeos_confirmados=mapeos,
            tipo_comprobante=body.tipo_comprobante,
            centro_costo=body.centro_costo,
            prefijo=body.prefijo,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    for m in mapeos:
        causacion_service.confirmar_mapeo(
            db,
            numero_dian=numero_dian,
            nit=body.factura.get("nit"),
            descripcion=m.get("descripcion", ""),
            cuenta_sugerida=None,
            cuenta_aplicada=m["cuenta_gasto"],
            cod_impuesto=m.get("cod_impuesto"),
        )

    causacion_service.registrar_factura_causada(
        db,
        factura=body.factura,
        consecutivo=consecutivo,
        tipo_comprobante=body.tipo_comprobante,
    )

    db.commit()

    nombre_archivo = f"importacion_SIIGO_{numero_dian}.xlsx"
    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
