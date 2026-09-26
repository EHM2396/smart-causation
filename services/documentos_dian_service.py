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

import gzip
import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.contabilidad import DocumentoDian, SincronizacionDian
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


def nombre_contraparte(factura: dict) -> str:
    """El nombre para mostrar de la contraparte, con el mismo respaldo para
    persona natural en los dos lados (compra y venta).

    Cuando la contraparte es una persona natural, el XML no trae razón social
    (`cac:PartyLegalEntity/RegistrationName`) sino nombre y apellido
    (`cac:Person`) — el parser los guarda aparte en `nombres_tercero` /
    `apellidos_tercero`. Es el caso típico del documento soporte (se emite a
    personas no obligadas a facturar) y también pasa en ventas a un cliente
    natural. Sin este respaldo, esas filas quedaban con la razón social vacía
    y quien las viera perdía de vista a qué proveedor o cliente correspondían.
    """
    nombres = (factura.get("nombres_tercero") or "").strip()
    apellidos = (factura.get("apellidos_tercero") or "").strip()
    return f"{nombres} {apellidos}".strip()


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


def xml_original(doc: DocumentoDian) -> bytes | None:
    """El archivo tal como lo entregó la DIAN (XML suelto o ZIP), descomprimido.

    Es el último eslabón de la trazabilidad: cada cifra del reporte tiene que
    poder llegar hasta el documento que la originó.
    """
    if not doc.xml_crudo:
        return None
    try:
        return gzip.decompress(doc.xml_crudo)
    except (OSError, EOFError, gzip.BadGzipFile):
        # Guardado antes de que se comprimiera, o dato corrupto: se devuelve
        # tal cual en vez de fallar — el original sigue siendo más útil que nada.
        return bytes(doc.xml_crudo)


def guardar_documento(
    db: Session, *, empresa_id: int, factura: dict, origen: str, xml_crudo: bytes | None = None,
) -> DocumentoDian:
    """Guarda (o actualiza) un documento traído de la DIAN.

    Se actualiza en vez de duplicar: volver a traer el mismo rango es una
    operación normal —para incorporar documentos que el proveedor emitió
    después— y no debe multiplicar las cifras.

    `xml_crudo` es el archivo original que entregó la DIAN. Se guarda comprimido
    y sin modificar: es el final de la cadena de trazabilidad y lo que permite
    reprocesar cuando el parser aprenda a leer un campo nuevo, sin tener que
    volver a descargarlo todo con un enlace que dura una hora.
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
    doc.razon_social = factura.get("razon_social") or nombre_contraparte(factura)
    doc.total = factura.get("total") or 0.0
    doc.base_gravable = base_gravable_de(factura)
    doc.items_json = json.dumps(factura.get("items") or [], ensure_ascii=False, default=str)
    # Solo se pisa si llega uno nuevo: si una traída falla al descargar el
    # archivo, no se borra el que ya estaba guardado.
    if xml_crudo:
        doc.xml_crudo = gzip.compress(xml_crudo)
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


def registrar_sincronizacion(
    db: Session, *, empresa_id: int, usuario_id: int | None,
    desde: date, hasta: date, documentos: int, errores: int,
) -> SincronizacionDian:
    """Deja constancia de qué periodo se trajo y cuándo."""
    s = SincronizacionDian(
        empresa_id=empresa_id, usuario_id=usuario_id,
        fecha_desde=desde, fecha_hasta=hasta,
        documentos=documentos, errores=errores,
    )
    db.add(s)
    db.commit()
    return s


def ultima_sincronizacion(db: Session, empresa_id: int) -> SincronizacionDian | None:
    """La última traída de esta empresa: sirve para decirle al usuario qué
    periodo tiene cargado y si necesita volver a pegar el token."""
    return db.scalar(
        select(SincronizacionDian)
        .where(SincronizacionDian.empresa_id == empresa_id)
        .order_by(SincronizacionDian.ejecutado_at.desc())
        .limit(1)
    )


def listar_ids(auth_url: str, desde: str, hasta: str) -> dict[str, list[str]]:
    """IDs de todos los documentos del rango, por origen. Solo el listado: barato
    y sin descargar XML, sirve para saber cuánto falta antes de empezar."""
    ids: dict[str, list[str]] = {}
    for origen in ORIGENES:
        resultado = dian_service.consultar_documentos(auth_url, desde, hasta, modo=origen)
        ids[origen] = [d["id"] for d in resultado.get("documents", []) if d.get("id")]
    return ids
