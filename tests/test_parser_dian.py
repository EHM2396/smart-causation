"""
Extracción de datos del XML de la DIAN.

Cubre lo que alimenta toda la causación: bases, IVA por ítem, otros tributos,
descuentos y el tipo de documento (que decide a qué módulo va cada factura).
"""
from __future__ import annotations

import pytest

from core.parser import _parsear_xml_dian, clasificar_tributo_dian
from tests.conftest import factura_xml, linea_xml

pytestmark = pytest.mark.parser


def test_extrae_datos_basicos_de_la_factura():
    xml = factura_xml([linea_xml("Producto A", 100000, iva_pct=19, iva_valor=19000)],
                      numero="FE123", total=119000)
    f = _parsear_xml_dian(xml, "prueba.xml")

    assert f["numero_dian"] == "FE123"
    assert f["nit"] == "900123456"
    assert f["razon_social"] == "Proveedor de Prueba SAS"
    assert f["fecha"] == "15/09/2026"
    assert f["total"] == 119000.0
    assert f["tipo_documento"] == "factura"
    assert len(f["items"]) == 1


def test_iva_se_extrae_por_item_no_por_factura():
    """Una factura puede mezclar tarifas; cada ítem conserva la suya."""
    xml = factura_xml([
        linea_xml("Gravado 19", 100000, iva_pct=19, iva_valor=19000),
        linea_xml("Gravado 5", 200000, iva_pct=5, iva_valor=10000),
        linea_xml("Sin IVA", 50000, iva_pct=0, iva_valor=0),
    ], total=379000)
    f = _parsear_xml_dian(xml, "prueba.xml")

    tarifas = [i["porcentaje"] for i in f["items"]]
    ivas = [i["valor_impuesto"] for i in f["items"]]
    assert tarifas == [19.0, 5.0, 0.0]
    assert ivas == [19000.0, 10000.0, 0.0]


def test_codigo_siigo_se_infiere_de_la_tarifa():
    xml = factura_xml([
        linea_xml("19%", 100000, iva_pct=19, iva_valor=19000),
        linea_xml("5%", 100000, iva_pct=5, iva_valor=5000),
    ], total=224000)
    f = _parsear_xml_dian(xml, "prueba.xml")
    assert [i["cod_impuesto"] for i in f["items"]] == ["1", "2"]


# ─── Tipo de documento: define a qué módulo va ────────────────────────────────

def test_detecta_nota_credito():
    xml = factura_xml([linea_xml("Devolución", 100000, iva_pct=19, iva_valor=19000, tag="CreditNoteLine")],
                      total=119000, nota_credito=True)
    f = _parsear_xml_dian(xml, "nc.xml")
    assert f["tipo_documento"] == "nota_credito"


def test_detecta_documento_soporte():
    """CustomizationID 05 ⇒ documento soporte, NO una factura de compra."""
    xml = factura_xml([linea_xml("Servicio", 100000, iva_pct=0, iva_valor=0)],
                      total=100000, customization="05")
    f = _parsear_xml_dian(xml, "ds.xml")
    assert f["tipo_documento"] == "documento_soporte"


def test_detecta_nota_de_ajuste_al_soporte():
    xml = factura_xml([linea_xml("Ajuste", 50000, iva_pct=0, iva_valor=0, tag="CreditNoteLine")],
                      total=50000, nota_credito=True, customization="05")
    f = _parsear_xml_dian(xml, "ajuste.xml")
    assert f["tipo_documento"] == "nota_ajuste_soporte"


# ─── Otros tributos ───────────────────────────────────────────────────────────

def test_extrae_inc_e_ibua_como_otros_tributos():
    xml = factura_xml([
        linea_xml("Gaseosa", 100000, iva_pct=19, iva_valor=19000,
                  otros=[("04", 8000, 8), ("34", 5000, 0)]),
    ], total=132000)
    f = _parsear_xml_dian(xml, "prueba.xml")
    tributos = f["items"][0]["otros_tributos"]

    assert {t["cod_dian"] for t in tributos} == {"04", "34"}
    inc = next(t for t in tributos if t["cod_dian"] == "04")
    ibua = next(t for t in tributos if t["cod_dian"] == "34")
    assert inc["grupo"] == "independiente"   # en ventas se desglosa aparte
    assert ibua["grupo"] == "costo"          # se suma al costo/ingreso
    assert inc["valor"] == 8000.0
    # El IVA NO debe contaminarse con los otros tributos.
    assert f["items"][0]["valor_impuesto"] == 19000.0


def test_las_retenciones_no_se_toman_del_xml():
    """Las retenciones las aplica el contador en la interfaz, no se leen de la factura."""
    xml = factura_xml([
        linea_xml("Servicio", 100000, iva_pct=19, iva_valor=19000, otros=[("06", 2500, 2.5)]),
    ], total=119000)
    f = _parsear_xml_dian(xml, "prueba.xml")
    codigos = {t["cod_dian"] for t in f["items"][0]["otros_tributos"]}
    assert "06" not in codigos, "retefuente (06) no debe entrar como tributo del ítem"


def test_tributo_desconocido_genera_advertencia():
    """Un tributo sin tratamiento definido se contabiliza pero avisa al contador."""
    xml = factura_xml([
        linea_xml("Producto", 100000, iva_pct=19, iva_valor=19000, otros=[("23", 1000, 1)]),
    ], total=120000)
    f = _parsear_xml_dian(xml, "prueba.xml")
    assert any("23" in a for a in f["advertencias"]), "se esperaba alerta del tributo 23"


# ─── Descuentos y recargos ────────────────────────────────────────────────────

def test_descuento_y_recargo_globales():
    xml = factura_xml([linea_xml("Producto", 100000, iva_pct=19, iva_valor=19000)],
                      total=112000, descuento_global=10000, recargo_global=3000)
    f = _parsear_xml_dian(xml, "prueba.xml")
    assert f["descuento_global"] == 10000.0
    assert f["recargo_global"] == 3000.0


def test_descuento_por_item_se_reporta_pero_la_base_ya_viene_neta():
    xml = factura_xml([linea_xml("Producto", 100000, iva_pct=19, iva_valor=19000, descuento=5000)],
                      total=119000)
    f = _parsear_xml_dian(xml, "prueba.xml")
    item = f["items"][0]
    assert item["descuento_item"] == 5000.0
    assert item["base"] == 100000.0, "LineExtensionAmount ya viene neto del descuento"


# ─── Clasificación de tributos DIAN ───────────────────────────────────────────

@pytest.mark.clasificacion
@pytest.mark.parametrize("codigo,grupo_esperado,conocido", [
    ("01", "iva", True),
    ("04", "independiente", True),   # INC
    ("22", "independiente", True),   # bolsas
    ("34", "costo", True),           # IBUA
    ("35", "costo", True),           # ICUI
    ("33", "costo", True),           # INPP
    ("06", "retencion", True),       # retefuente
    ("23", "costo", False),          # carbono: sin tratamiento explícito → alerta
    ("XX", "costo", False),          # desconocido → nunca revienta, avisa
])
def test_clasificacion_de_tributos(codigo, grupo_esperado, conocido):
    nombre, grupo, es_conocido = clasificar_tributo_dian(codigo)
    assert grupo == grupo_esperado
    assert es_conocido is conocido
    assert nombre, "todo tributo debe tener un nombre legible para el contador"


# ─── Referencia/código del producto (Fase 1 del módulo de IVA) ───────────────
#
# La memoria de clasificación ahora afina por proveedor + referencia +
# descripción, no solo proveedor + descripción — hace falta que el parser
# guarde ese código aparte, sin tocar cómo se arma la descripción.

def test_extrae_la_referencia_del_producto():
    xml = factura_xml([linea_xml("Servicio de mantenimiento", 100000, iva_pct=0, iva_valor=0,
                                  referencia="MANT-001")])
    f = _parsear_xml_dian(xml, "prueba.xml")
    assert f["items"][0]["referencia"] == "MANT-001"


def test_sin_referencia_en_el_xml_queda_en_none():
    """No todos los proveedores mandan SellersItemIdentification: no debe
    reventar ni inventarse un valor."""
    xml = factura_xml([linea_xml("Servicio sin código", 100000, iva_pct=0, iva_valor=0)])
    f = _parsear_xml_dian(xml, "prueba.xml")
    assert f["items"][0]["referencia"] is None


def test_referencia_no_reemplaza_la_descripcion_cuando_ambas_existen():
    """La referencia es un dato aparte, no un respaldo de la descripción — eso
    solo pasa cuando el XML no trae Description en absoluto."""
    xml = factura_xml([linea_xml("Descripción real del ítem", 100000, iva_pct=0, iva_valor=0,
                                  referencia="REF-9")])
    f = _parsear_xml_dian(xml, "prueba.xml")
    item = f["items"][0]
    assert item["descripcion"] == "Descripción real del ítem"
    assert item["referencia"] == "REF-9"
