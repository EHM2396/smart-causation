"""
Traer de la DIAN los documentos de una empresa y guardarlos.

Por qué guardar y no consultar en vivo: el listado que devuelve la DIAN NO trae
montos —solo id, número, fecha, contraparte y tipo—, así que para conocer un
valor hay que descargar y parsear el XML de cada documento. Para un rango de un
año eso son minutos. Se trae una vez y queda disponible al instante, tanto para
la analítica como para el reporte de impuestos.

Clasificación por tipo: el ORIGEN de la consulta manda (recibidos = compra,
emitidos = venta, y el documento soporte se consulta aparte), y el tipo de
documento del XML separa factura de nota crédito o débito. A diferencia de la
causación, acá las notas DÉBITO sí se guardan: no tienen módulo donde causarse,
pero existen en la DIAN y suman al valor, así que omitirlas falsearía el informe.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.contabilidad import DocumentoDian
from services import dian_service
from services.causacion_service import base_gravable_de

# Cada consulta a la DIAN y el tipo que produce para un documento normal.
ORIGENES = ("compras", "ventas", "soporte", "soporte_ajuste")


def clasificar(factura: dict, origen: str) -> str:
    """Tipo con el que se guarda un documento ya parseado."""
    if origen == "soporte":
        return "soporte"
    if origen == "soporte_ajuste":
        return "nc_soporte"
    td = (factura.get("tipo_documento") or "factura").lower()
    # Malla de seguridad: un documento soporte que se cuele en otra bandeja
    # igual se guarda como lo que es.
    if td == "documento_soporte":
        return "soporte"
    if td == "nota_ajuste_soporte":
        return "nc_soporte"
    es_venta = origen == "ventas"
    if td == "nota_credito":
        return "nc_ventas" if es_venta else "nc"
    if td == "nota_debito":
        return "nd_ventas" if es_venta else "nd"
    return "ventas" if es_venta else "compras"


def _fecha(valor: str | None) -> date | None:
    """La fecha del parser viene como DD/MM/YYYY."""
    if not valor:
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except (ValueError, AttributeError):
            continue
    return None


def guardar_documento(db: Session, *, empresa_id: int, factura: dict, origen: str) -> DocumentoDian:
    """Guarda (o actualiza) un documento traído de la DIAN.

    Se actualiza en vez de duplicar: volver a traer el mismo rango es una
    operación normal —para incorporar documentos que el proveedor emitió
    después— y no debe multiplicar las cifras.
    """
    tipo = clasificar(factura, origen)
    numero = factura.get("numero_dian") or factura.get("numero_factura") or ""

    existente = db.scalar(
        select(DocumentoDian).where(
            DocumentoDian.empresa_id == empresa_id,
            DocumentoDian.tipo == tipo,
            DocumentoDian.numero == numero,
        )
    )
    doc = existente or DocumentoDian(empresa_id=empresa_id, tipo=tipo, numero=numero)

    doc.cufe = factura.get("cufe")
    doc.fecha_emision = _fecha(factura.get("fecha"))
    doc.nit_contraparte = factura.get("nit")
    doc.razon_social = factura.get("razon_social")
    doc.total = factura.get("total") or 0.0
    doc.base_gravable = base_gravable_de(factura)
    doc.items_json = json.dumps(factura.get("items") or [], ensure_ascii=False, default=str)
    doc.traido_at = datetime.now()

    if existente is None:
        db.add(doc)
    db.flush()
    return doc


def ultima_actualizacion(db: Session, empresa_id: int) -> datetime | None:
    """Cuándo se trajo por última vez algo de la DIAN para esta empresa."""
    from sqlalchemy import func
    return db.scalar(
        select(func.max(DocumentoDian.traido_at)).where(DocumentoDian.empresa_id == empresa_id)
    )


def listar_ids(auth_url: str, desde: str, hasta: str) -> dict[str, list[str]]:
    """IDs de todos los documentos del rango, por origen. Solo el listado: barato
    y sin descargar XML, sirve para saber cuánto falta antes de empezar."""
    ids: dict[str, list[str]] = {}
    for origen in ORIGENES:
        resultado = dian_service.consultar_documentos(auth_url, desde, hasta, modo=origen)
        ids[origen] = [d["id"] for d in resultado.get("documents", []) if d.get("id")]
    return ids
