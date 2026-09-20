"""
El XML original de cada documento DIAN.

Es el último eslabón de la trazabilidad que exige el motor del Formulario 300:
cada cifra del reporte tiene que poder llegar hasta el documento que la originó.
También es lo que permite reprocesar cuando el parser aprenda a leer un campo
nuevo, sin volver a descargar todo de la DIAN con un enlace que dura una hora.
"""
from __future__ import annotations

import gzip

import pytest

from db.models.contabilidad import DocumentoDian
from services.documentos_dian_service import xml_original

pytestmark = pytest.mark.trazabilidad

XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b"<Invoice><cbc:ID>FE123</cbc:ID><cbc:IssueDate>2026-08-15</cbc:IssueDate></Invoice>"
)


def test_se_recupera_el_archivo_tal_como_llego():
    """Byte por byte: si alguna vez hay que auditar la firma digital, un XML
    reescrito no sirve."""
    doc = DocumentoDian(xml_crudo=gzip.compress(XML))
    assert xml_original(doc) == XML


def test_comprimir_vale_la_pena():
    """Un XML de factura es texto repetitivo: comprime muy bien, y por eso se
    puede guardar dentro de la base sin que el respaldo se dispare."""
    grande = XML * 200
    comprimido = gzip.compress(grande)
    assert len(comprimido) < len(grande) / 5


def test_sin_archivo_guardado_devuelve_nada():
    """Los documentos traídos antes de que se guardara el XML no tienen nada
    que devolver, y eso no debe reventar el reporte."""
    assert xml_original(DocumentoDian(xml_crudo=None)) is None


def test_un_dato_sin_comprimir_se_devuelve_igual():
    """Tolera lo guardado sin comprimir: tener el original crudo sigue siendo
    mejor que fallar."""
    doc = DocumentoDian(xml_crudo=XML)
    assert xml_original(doc) == XML


def test_tambien_sirve_para_un_zip():
    """La DIAN a veces entrega un ZIP en vez del XML suelto. Se guarda tal cual,
    sin desempacarlo: el original es el ZIP."""
    zip_falso = b"PK\x03\x04" + b"contenido comprimido"
    doc = DocumentoDian(xml_crudo=gzip.compress(zip_falso))
    recuperado = xml_original(doc)
    assert recuperado == zip_falso
    assert recuperado.startswith(b"PK"), "debe seguir siendo reconocible como ZIP"
