"""
Clasificación de documentos: a qué módulo pertenece cada factura y cuáles
reversan la partida.

Un error acá manda una factura al módulo equivocado (p. ej. un documento soporte
contado como compra) o deja una nota de ajuste sin reversar.
"""
from __future__ import annotations

import pytest

from api.routers.causacion import _columna_fecha, _es_nota_reversa
from db.models.contabilidad import FacturaCausada
from services.causacion_service import derivar_tipo_causacion

pytestmark = pytest.mark.clasificacion


# ─── Módulo al que pertenece cada documento ───────────────────────────────────

@pytest.mark.parametrize("tipo_documento,es_venta,esperado", [
    ("factura",              False, "compras"),
    ("nota_credito",         False, "nc"),
    ("factura",              True,  "ventas"),
    ("nota_credito",         True,  "nc_ventas"),
    ("documento_soporte",    False, "soporte"),
    ("nota_ajuste_soporte",  False, "nc_soporte"),
    # El documento soporte manda sobre el flag de venta: nunca es una venta.
    ("documento_soporte",    True,  "soporte"),
    ("nota_ajuste_soporte",  True,  "nc_soporte"),
])
def test_derivar_tipo_causacion(tipo_documento, es_venta, esperado):
    assert derivar_tipo_causacion({"tipo_documento": tipo_documento}, es_venta) == esperado


def test_sin_tipo_documento_se_asume_factura():
    assert derivar_tipo_causacion({}, False) == "compras"
    assert derivar_tipo_causacion({}, True) == "ventas"


# ─── Qué documentos reversan la partida ───────────────────────────────────────

@pytest.mark.parametrize("tipo_documento,reversa", [
    ("nota_credito", True),
    ("nota_ajuste_soporte", True),   # el ajuste al soporte se comporta como NC
    ("factura", False),
    ("documento_soporte", False),
    ("nota_debito", False),
])
def test_es_nota_reversa(tipo_documento, reversa):
    assert _es_nota_reversa({"tipo_documento": tipo_documento}) is reversa


def test_es_nota_reversa_tolera_factura_vacia():
    assert _es_nota_reversa(None) is False
    assert _es_nota_reversa({}) is False


# ─── Filtro de fechas del historial ───────────────────────────────────────────

def test_columna_fecha_del_historial():
    """'emision' filtra por la fecha de la factura; por defecto, por la de causación."""
    assert _columna_fecha("emision") is FacturaCausada.fecha_factura
    assert _columna_fecha("causacion") is FacturaCausada.fecha_causacion
    assert _columna_fecha(None) is FacturaCausada.fecha_causacion
    assert _columna_fecha("cualquier_cosa") is FacturaCausada.fecha_causacion
