"""
Router: /causacion – flujo principal de causación contable.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import (
    CausacionRequest,
    CausacionResponse,
    SugerenciaRequest,
    SugerenciaResponse,
)
from db.models.contabilidad import FacturaCausada
from db.session import get_db
from services import causacion_service, consecutivos_service
from core import exporter, validator

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


# ─────────────────────────────────────────────────────────────────────────────
# Batch: N facturas → 1 xlsx + validación de partida doble
# ─────────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel


class BatchItem(BaseModel):
    factura: dict
    mapeos_confirmados: list[dict]


class BatchRequest(BaseModel):
    items: list[BatchItem]
    tipo_comprobante: str = "12"
    centro_costo: str = ""
    confirmar: bool = False  # True = persistir aprendizaje + consecutivos


class ValidacionComprobante(BaseModel):
    consecutivo: int
    numero_dian: str
    total_debito: float
    total_credito: float
    diferencia: float
    cuadra: bool


class BatchValidacionResponse(BaseModel):
    comprobantes: list[ValidacionComprobante]
    global_cuadra: bool
    gran_total_debitos: float
    gran_total_creditos: float


@router.post("/batch/validar", response_model=BatchValidacionResponse)
def batch_validar(body: BatchRequest, db: DB):
    """
    Construye los movimientos para N facturas y valida la partida doble.
    NO persiste nada. Usar antes de confirmar.
    """
    ultimo = consecutivos_service.get_ultimo(db, body.tipo_comprobante)
    todos_movs: list[dict] = []

    for idx, item in enumerate(body.items):
        consecutivo = ultimo + 1 + idx
        movs = exporter.construir_movimientos(
            factura=item.factura,
            consecutivo=consecutivo,
            mapeos_confirmados=item.mapeos_confirmados,
            tipo_comprobante=body.tipo_comprobante,
            centro_costo=body.centro_costo,
        )
        todos_movs.extend(movs)

    reporte = validator.validar_movimientos(todos_movs)

    comps = [
        ValidacionComprobante(
            consecutivo=c.consecutivo,
            numero_dian=next(
                (body.items[i].factura.get("numero_dian", "")
                 for i, item in enumerate(body.items)
                 if ultimo + 1 + i == c.consecutivo),
                "",
            ),
            total_debito=c.total_debito,
            total_credito=c.total_credito,
            diferencia=c.diferencia,
            cuadra=c.cuadra,
        )
        for c in reporte.comprobantes
    ]

    return BatchValidacionResponse(
        comprobantes=comps,
        global_cuadra=reporte.global_cuadra,
        gran_total_debitos=reporte.gran_total_debitos,
        gran_total_creditos=reporte.gran_total_creditos,
    )


@router.post("/batch/generar")
def batch_generar(body: BatchRequest, db: DB):
    """
    Genera el xlsx consolidado para N facturas y opcionalmente confirma.
    Retorna el archivo como descarga directa.
    """
    ultimo = consecutivos_service.get_ultimo(db, body.tipo_comprobante)
    todos_movs: list[dict] = []

    for idx, item in enumerate(body.items):
        numero_dian = item.factura.get("numero_dian", "")
        if causacion_service.esta_causada(db, numero_dian):
            raise HTTPException(409, f"La factura {numero_dian!r} ya fue causada")
        consecutivo = ultimo + 1 + idx
        movs = exporter.construir_movimientos(
            factura=item.factura,
            consecutivo=consecutivo,
            mapeos_confirmados=item.mapeos_confirmados,
            tipo_comprobante=body.tipo_comprobante,
            centro_costo=body.centro_costo,
        )
        todos_movs.extend(movs)

    xlsx_buf = exporter.generar_xlsx(todos_movs)

    if body.confirmar:
        for idx, item in enumerate(body.items):
            consecutivo = ultimo + 1 + idx
            for m in item.mapeos_confirmados:
                if m.get("cuenta_gasto") and item.factura.get("nit"):
                    causacion_service.confirmar_mapeo(
                        db,
                        numero_dian=item.factura.get("numero_dian", ""),
                        nit=item.factura.get("nit"),
                        descripcion=m.get("descripcion", ""),
                        cuenta_sugerida=m.get("cuenta_sugerida"),
                        cuenta_aplicada=m["cuenta_gasto"],
                        cod_impuesto=m.get("cod_impuesto"),
                        origen=m.get("fuente", "manual"),
                    )
            causacion_service.registrar_factura_causada(
                db,
                factura=item.factura,
                consecutivo=consecutivo,
                tipo_comprobante=body.tipo_comprobante,
                archivo_origen=item.factura.get("_archivo", ""),
            )
        consecutivos_service.set_ultimo(db, body.tipo_comprobante, ultimo + len(body.items))
        db.commit()

    nombre = exporter.nombre_archivo_salida()
    return StreamingResponse(
        xlsx_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/historial", response_model=list[dict])
def get_historial_causadas(db: DB, limit: int = 100):
    """Listado de facturas ya causadas, orden descendente por fecha."""
    rows = db.scalars(
        select(FacturaCausada)
        .order_by(FacturaCausada.fecha_causacion.desc(), FacturaCausada.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "consecutivo": r.consecutivo,
            "numero_dian": r.numero_dian,
            "razon_social": r.razon_social,
            "fecha_factura": str(r.fecha_factura) if r.fecha_factura else None,
            "fecha_causacion": str(r.fecha_causacion) if r.fecha_causacion else None,
            "total": float(r.total or 0),
        }
        for r in rows
    ]

