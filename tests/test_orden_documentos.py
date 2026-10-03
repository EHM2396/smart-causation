"""
Orden cronológico de los documentos y consecutivo original.

Regla: manda la FECHA DE EMISIÓN del XML. El orden en que el usuario descarga,
importa o causa los documentos NO decide su posición: si se trae primero
septiembre y después agosto, agosto queda antes. El número del documento
(prefijo + consecutivo) se conserva EXACTO como viene en el XML.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from core.exporter import construir_movimientos
from core.parser import _parsear_xml_dian
from services.causacion_service import (
    _parse_date,
    clave_cronologica,
    ordenar_por_emision,
    partes_numero,
)
from tests.conftest import factura_xml, linea_xml

pytestmark = pytest.mark.orden


def _doc(numero: str, fecha: str, *, nota: bool = False) -> dict:
    tag = "CreditNoteLine" if nota else "InvoiceLine"
    xml = factura_xml([linea_xml("Producto", 100000, iva_pct=19, iva_valor=19000, tag=tag)],
                      numero=numero, fecha=fecha, total=119000, nota_credito=nota)
    return _parsear_xml_dian(xml, f"{numero}.xml")


def _ordenar_facturas(facturas: list[dict]) -> list[str]:
    ordenadas = ordenar_por_emision(
        facturas,
        fecha=lambda f: _parse_date(f["fecha"]),
        numero=lambda f: f["numero_dian"],
        tipo=lambda f: f["tipo_documento"],
    )
    return [f["numero_dian"] for f in ordenadas]


# ─── Prueba 3: extracción desordenada ─────────────────────────────────────────

def test_periodo_anterior_importado_despues_queda_en_su_lugar():
    """Se importa primero septiembre y después agosto: agosto va antes."""
    incorporadas = [
        _doc("FE20", "2026-09-10"),
        _doc("FE21", "2026-09-12"),
        _doc("FE7", "2026-08-03"),   # llegó después, pero es de agosto
        _doc("FE8", "2026-08-25"),
    ]
    assert _ordenar_facturas(incorporadas) == ["FE7", "FE8", "FE20", "FE21"]


def test_mismo_dia_se_ordena_por_tipo_prefijo_y_consecutivo():
    incorporadas = [
        _doc("NC3", "2026-08-20", nota=True),
        _doc("FE10", "2026-08-20"),
        _doc("FE9", "2026-08-20"),    # en texto "FE10" < "FE9"; numéricamente 9 < 10
        _doc("FC2", "2026-08-20"),
    ]
    # Factura antes que su nota; luego prefijo (FC < FE) y consecutivo numérico.
    assert _ordenar_facturas(incorporadas) == ["FC2", "FE9", "FE10", "NC3"]


def test_historial_mas_reciente_primero_y_sin_fecha_al_final():
    filas = [
        SimpleNamespace(fecha_factura=date(2026, 9, 1), numero_dian="FE1", tipo_causacion="compras"),
        SimpleNamespace(fecha_factura=None, numero_dian="FE0", tipo_causacion="compras"),
        SimpleNamespace(fecha_factura=date(2026, 8, 1), numero_dian="FE2", tipo_causacion="compras"),
        SimpleNamespace(fecha_factura=date(2026, 9, 1), numero_dian="FE10", tipo_causacion="compras"),
    ]
    ordenadas = ordenar_por_emision(filas, descendente=True)
    assert [f.numero_dian for f in ordenadas] == ["FE10", "FE1", "FE2", "FE0"]


def test_la_fecha_de_causacion_no_interviene():
    """Dos documentos causados en orden inverso a su emisión: manda la emisión."""
    filas = [
        SimpleNamespace(fecha_factura=date(2026, 9, 5), fecha_causacion=date(2026, 9, 6),
                        numero_dian="FE50", tipo_causacion="ventas"),
        SimpleNamespace(fecha_factura=date(2026, 8, 5), fecha_causacion=date(2026, 10, 1),
                        numero_dian="FE40", tipo_causacion="ventas"),
    ]
    assert [f.numero_dian for f in ordenar_por_emision(filas)] == ["FE40", "FE50"]


def test_consecutivos_largos_se_comparan_sin_perder_precision():
    a = clave_cronologica(date(2026, 1, 1), "SETP990000000000000009")
    b = clave_cronologica(date(2026, 1, 1), "SETP990000000000000010")
    assert a < b


# ─── Prueba 4: el consecutivo original se conserva ────────────────────────────

@pytest.mark.parametrize("numero", ["FEV-000123", "SETP990000001", "FE0012", "fe77"])
def test_parser_conserva_el_numero_exacto_del_xml(numero):
    f = _doc(numero, "2026-09-15")
    assert f["numero_dian"] == numero


def test_partes_numero_solo_lee_no_modifica():
    assert partes_numero("FE0012") == ("FE", "0012")   # ceros a la izquierda intactos
    assert partes_numero("FEV-000123") == ("FEV-", "000123")
    assert partes_numero("SINNUMERO") == ("SINNUMERO", "")


def test_el_comprobante_siigo_lleva_el_numero_original():
    f = _doc("FE0012", "2026-09-15")
    mapeo = {"descripcion": "Producto", "base": 100000.0, "valor_impuesto": 19000.0, "porcentaje": 19.0,
             "cod_impuesto": "1", "es_retencion": False, "cuenta_gasto": "51953001",
             "cuenta_impuesto_deb": "24081001", "cuenta_impuesto_cre": "", "cuenta_pago": "",
             "cuenta_pago_nombre": ""}
    movs = construir_movimientos(f, 7, [mapeo])
    assert all(m["Observaciones"].startswith("FE0012-") for m in movs)


def test_fecha_de_emision_sale_del_xml():
    f = _doc("FE1", "2026-08-03")
    assert f["fecha"] == "03/08/2026"
