"""
Analítica de costos, gastos e ingresos.

Lo que se protege acá es que las cifras signifiquen algo: que las notas crédito
RESTEN y que cada documento electrónico caiga en su naturaleza. Si esto se
rompe, el dashboard muestra números que parecen correctos pero no lo son — que
es peor que no mostrarlos.
"""
from __future__ import annotations

import pytest

from services.analitica_service import ETIQUETA, NATURALEZA, ORDEN, SIGNO
from services.causacion_service import base_gravable_de

pytestmark = pytest.mark.analitica


# ─── Naturaleza de cada documento electrónico DIAN ───────────────────────────

@pytest.mark.parametrize("tipo,naturaleza", [
    ("ventas", "ingresos"),
    ("nc_ventas", "ingresos"),
    ("compras", "costos_gastos"),
    ("nc", "costos_gastos"),
    # El documento soporte legaliza un costo con personas naturales no obligadas
    # a facturar: es costo/gasto, no un ingreso, aunque lo emita el comprador.
    ("soporte", "costos_gastos"),
    ("nc_soporte", "costos_gastos"),
])
def test_naturaleza_por_tipo_de_documento(tipo, naturaleza):
    assert NATURALEZA[tipo] == naturaleza


# ─── Las notas crédito restan ────────────────────────────────────────────────

@pytest.mark.parametrize("tipo", ["nc", "nc_ventas", "nc_soporte"])
def test_las_notas_credito_restan(tipo):
    assert SIGNO[tipo] == -1


@pytest.mark.parametrize("tipo", ["compras", "ventas", "soporte"])
def test_las_facturas_suman(tipo):
    assert SIGNO[tipo] == 1


def test_una_venta_con_su_nota_credito_se_neutraliza():
    """Facturar 100 y anular 100 deja ingresos en 0, no en 200."""
    ingresos = 100 * SIGNO["ventas"] + 100 * SIGNO["nc_ventas"]
    assert ingresos == 0


def test_compra_con_devolucion_parcial():
    """Compra de 1.000 con devolución de 300 deja 700 de costo."""
    costo = 1000 * SIGNO["compras"] + 300 * SIGNO["nc"]
    assert costo == 700


def test_todos_los_tipos_tienen_signo_naturaleza_etiqueta_y_orden():
    """Un tipo sin signo o sin naturaleza rompería la suma en silencio."""
    for tipo in SIGNO:
        assert tipo in NATURALEZA, f"{tipo} no tiene naturaleza"
        assert tipo in ETIQUETA, f"{tipo} no tiene etiqueta"
        assert tipo in ORDEN, f"{tipo} no aparece en el orden de presentación"
    assert set(ORDEN) == set(SIGNO)


# ─── Base gravable (sin IVA) ─────────────────────────────────────────────────

def test_base_gravable_suma_las_bases_de_los_items():
    factura = {"items": [{"base": 1000.0}, {"base": 500.0}, {"base": 250.5}]}
    assert base_gravable_de(factura) == 1750.5


def test_base_gravable_ignora_el_iva():
    """La base excluye impuestos: 1.000 + IVA 190 debe dar 1.000, no 1.190."""
    factura = {"items": [{"base": 1000.0, "iva": 190.0, "total": 1190.0}]}
    assert base_gravable_de(factura) == 1000.0


@pytest.mark.parametrize("factura", [
    {},                      # sin ítems
    {"items": []},           # lista vacía
])
def test_base_gravable_sin_items_es_nula(factura):
    """Sin ítems no se inventa un 0: se devuelve None para que la analítica
    caiga al total en vez de contar la factura como si valiera nada."""
    assert base_gravable_de(factura) is None


def test_base_gravable_tolera_items_corruptos():
    assert base_gravable_de({"items": [{"base": "no-es-numero"}]}) is None


def test_base_gravable_trata_el_item_sin_base_como_cero():
    assert base_gravable_de({"items": [{"base": 100.0}, {"descripcion": "sin base"}]}) == 100.0
