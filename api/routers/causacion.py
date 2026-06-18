"""
Router: /causacion – flujo principal de causación contable.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy import delete, select
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
                datos_json=json.dumps(
                    {
                        "factura": item.factura,
                        "mapeos": item.mapeos_confirmados,
                        "tipo_comprobante": body.tipo_comprobante,
                        "centro_costo": body.centro_costo,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        consecutivos_service.set_ultimo(db, body.tipo_comprobante, ultimo + len(body.items))
        db.commit()

    nombre = exporter.nombre_archivo_salida()
    return StreamingResponse(
        xlsx_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/historial/exportar-lote")
def exportar_lote_historial(
    db: DB,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    tipo_comprobante: str | None = None,
):
    """Genera un único XLSX SIIGO con todas las facturas del período que tienen datos almacenados."""
    stmt = (
        select(FacturaCausada)
        .where(FacturaCausada.datos_json.is_not(None))
        .order_by(FacturaCausada.id)
    )
    if fecha_desde:
        try:
            stmt = stmt.where(FacturaCausada.fecha_causacion >= date.fromisoformat(fecha_desde))
        except ValueError:
            pass
    if fecha_hasta:
        try:
            stmt = stmt.where(FacturaCausada.fecha_causacion <= date.fromisoformat(fecha_hasta))
        except ValueError:
            pass
    if tipo_comprobante:
        stmt = stmt.where(FacturaCausada.tipo_comprobante == tipo_comprobante)

    rows = db.scalars(stmt).all()
    if not rows:
        raise HTTPException(
            404,
            "No hay registros con datos exportables en el período seleccionado. "
            "Solo facturas causadas desde la versión actual pueden descargarse.",
        )

    todos_movs: list[dict] = []
    for fc in rows:
        data = json.loads(fc.datos_json)  # type: ignore[arg-type]
        movs = exporter.construir_movimientos(
            factura=data["factura"],
            consecutivo=int(fc.consecutivo or 0),
            mapeos_confirmados=data["mapeos"],
            tipo_comprobante=fc.tipo_comprobante or data.get("tipo_comprobante", "12"),
            centro_costo=data.get("centro_costo", ""),
        )
        todos_movs.extend(movs)

    xlsx_buf = exporter.generar_xlsx(todos_movs)
    desde = fecha_desde or "inicio"
    hasta = fecha_hasta or "hoy"
    nombre = f"SIIGO_lote_{desde}_{hasta}.xlsx"
    return StreamingResponse(
        xlsx_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/historial", response_model=list[dict])
def get_historial_causadas(
    db: DB,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    buscar: str | None = None,
    tipo_comprobante: str | None = None,
    limit: int = 500,
):
    """Listado filtrable de facturas causadas, orden descendente por fecha."""
    stmt = (
        select(FacturaCausada)
        .order_by(FacturaCausada.fecha_causacion.desc(), FacturaCausada.id.desc())
        .limit(limit)
    )
    if fecha_desde:
        try:
            stmt = stmt.where(FacturaCausada.fecha_causacion >= date.fromisoformat(fecha_desde))
        except ValueError:
            pass
    if fecha_hasta:
        try:
            stmt = stmt.where(FacturaCausada.fecha_causacion <= date.fromisoformat(fecha_hasta))
        except ValueError:
            pass
    if tipo_comprobante:
        stmt = stmt.where(FacturaCausada.tipo_comprobante == tipo_comprobante)
    if buscar:
        q = f"%{buscar.lower()}%"
        from sqlalchemy import or_, func as sqlfunc
        stmt = stmt.where(
            or_(
                sqlfunc.lower(FacturaCausada.numero_dian).like(q),
                sqlfunc.lower(FacturaCausada.nit_proveedor).like(q),
                sqlfunc.lower(FacturaCausada.razon_social).like(q),
            )
        )
    rows = db.scalars(stmt).all()
    return [
        {
            "id": r.id,
            "consecutivo": r.consecutivo,
            "numero_dian": r.numero_dian,
            "nit_proveedor": r.nit_proveedor,
            "razon_social": r.razon_social,
            "fecha_factura": str(r.fecha_factura) if r.fecha_factura else None,
            "fecha_causacion": str(r.fecha_causacion) if r.fecha_causacion else None,
            "total": float(r.total or 0),
            "tipo_comprobante": r.tipo_comprobante,
            "archivo_origen": r.archivo_origen,
            "tiene_datos": r.datos_json is not None,
        }
        for r in rows
    ]


@router.post("/historial/{registro_id}/regenerar")
def regenerar_historial(registro_id: int, db: DB):
    """Re-genera el xlsx de una factura causada previamente a partir de datos almacenados."""
    fc = db.get(FacturaCausada, registro_id)
    if not fc:
        raise HTTPException(404, "Registro no encontrado")
    if not fc.datos_json:
        raise HTTPException(
            422,
            "Este registro fue causado antes de que se almacenaran los datos de regeneración. "
            "Solo facturas confirmadas desde esta versión pueden regenerarse.",
        )
    data = json.loads(fc.datos_json)
    consecutivo = int(fc.consecutivo or 0)
    movimientos = exporter.construir_movimientos(
        factura=data["factura"],
        consecutivo=consecutivo,
        mapeos_confirmados=data["mapeos"],
        tipo_comprobante=fc.tipo_comprobante or data.get("tipo_comprobante", "12"),
        centro_costo=data.get("centro_costo", ""),
    )
    xlsx_buf = exporter.generar_xlsx(movimientos)
    nombre = f"regenerado_SIIGO_{fc.numero_dian}.xlsx"
    return StreamingResponse(
        xlsx_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.delete("/historial", response_model=dict)
def limpiar_historial(
    db: DB,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
):
    """Elimina registros del historial, opcionalmente filtrados por rango de fechas."""
    stmt = delete(FacturaCausada)
    if fecha_desde:
        try:
            stmt = stmt.where(FacturaCausada.fecha_causacion >= date.fromisoformat(fecha_desde))
        except ValueError:
            pass
    if fecha_hasta:
        try:
            stmt = stmt.where(FacturaCausada.fecha_causacion <= date.fromisoformat(fecha_hasta))
        except ValueError:
            pass
    result = db.execute(stmt)
    db.commit()
    return {"eliminados": result.rowcount}
