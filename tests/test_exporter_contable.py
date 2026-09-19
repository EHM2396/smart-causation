"""
Reglas contables del exporter — la parte más crítica del sistema.

Si algo de acá se rompe, se generan comprobantes MAL para SIIGO: partidas que no
cuadran, IVA en el lado equivocado o tributos que no deberían ser descontables.
"""
from __future__ import annotations

import pytest

from core.exporter import construir_movimientos
from tests.conftest import sumar

pytestmark = pytest.mark.contable


def _mov(factura, mapeos, **kw):
    return construir_movimientos(factura=factura, consecutivo=1, mapeos_confirmados=mapeos, **kw)


# ─── Partida doble: SIEMPRE debe cuadrar ──────────────────────────────────────

@pytest.mark.parametrize(
    "es_venta,es_nota_credito",
    [(False, False), (False, True), (True, False), (True, True)],
    ids=["compra", "nc_compra", "venta", "nc_venta"],
)
def test_partida_doble_cuadra_en_los_cuatro_casos(factura_simple, mapeo_simple, es_venta, es_nota_credito):
    movs = _mov(factura_simple, [mapeo_simple], es_venta=es_venta, es_nota_credito=es_nota_credito)
    deb, cre = sumar(movs)
    assert deb == cre, f"el comprobante no cuadra: débitos {deb} vs créditos {cre}"
    assert deb > 0, "se esperaba al menos un movimiento"


def test_compra_deja_gasto_e_iva_al_debito(factura_simple, mapeo_simple):
    movs = _mov(factura_simple, [mapeo_simple], es_venta=False, es_nota_credito=False)
    gasto = next(m for m in movs if m["Código cuenta contable"] == "519530")
    iva = next(m for m in movs if m["Código cuenta contable"] == "240820")
    assert float(gasto["Débito"]) == 100000.0
    assert float(iva["Débito"]) == 19000.0
    assert iva["Descripción"] == "Iva descontable"
    # La contrapartida (proveedor) va al crédito por el total de la factura.
    pago = next(m for m in movs if m["Código cuenta contable"] == "220505")
    assert float(pago["Crédito"]) == 119000.0


def test_venta_invierte_la_partida(factura_simple, mapeo_simple):
    """Una venta es la imagen espejo: ingreso e IVA al crédito, cliente al débito."""
    movs = _mov(factura_simple, [mapeo_simple], es_venta=True, es_nota_credito=False)
    ingreso = next(m for m in movs if m["Código cuenta contable"] == "519530")
    iva = next(m for m in movs if m["Código cuenta contable"] == "240820")
    cliente = next(m for m in movs if m["Código cuenta contable"] == "130505")
    assert float(ingreso["Crédito"]) == 100000.0
    assert float(iva["Crédito"]) == 19000.0
    assert iva["Descripción"] == "Iva generado"
    assert float(cliente["Débito"]) == 119000.0


def test_nota_credito_de_compra_reversa_la_compra(factura_simple, mapeo_simple):
    movs = _mov(factura_simple, [mapeo_simple], es_venta=False, es_nota_credito=True)
    gasto = next(m for m in movs if m["Código cuenta contable"] == "519530")
    iva = next(m for m in movs if m["Código cuenta contable"] == "240820")
    assert float(gasto["Crédito"]) == 100000.0, "en una NC el gasto se reversa al crédito"
    assert iva["Descripción"] == "Iva devolucion en compras"


# ─── Base gravable vs base exenta ─────────────────────────────────────────────

def test_item_con_iva_reporta_base_gravable(factura_simple, mapeo_simple):
    movs = _mov(factura_simple, [mapeo_simple])
    gasto = next(m for m in movs if m["Código cuenta contable"] == "519530")
    assert gasto["Base gravable libro compras/ventas  "] == 100000.0
    assert gasto["Base exenta libro compras/ventas"] == ""


def test_item_sin_tarifa_reporta_base_exenta(factura_simple, mapeo_simple):
    """Tarifa 0 ⇒ la base va a 'base exenta', no a 'base gravable'."""
    item = {**mapeo_simple, "porcentaje": 0.0, "valor_impuesto": 0.0, "cod_impuesto": "22"}
    factura = {**factura_simple, "total": 100000.0}
    movs = _mov(factura, [item])
    gasto = next(m for m in movs if m["Código cuenta contable"] == "519530")
    assert gasto["Base exenta libro compras/ventas"] == 100000.0
    assert gasto["Base gravable libro compras/ventas  "] == ""


# ─── Retenciones ──────────────────────────────────────────────────────────────

def test_retencion_va_al_credito_en_compras(factura_simple, mapeo_simple):
    retencion = {
        "descripcion": "Retefuente 2.5%", "base": 100000.0, "valor_impuesto": 2500.0,
        "porcentaje": 2.5, "cod_impuesto": "RF", "es_retencion": True,
        "cuenta_gasto": "", "cuenta_impuesto_deb": "", "cuenta_impuesto_cre": "236540",
        "cuenta_pago": "", "cuenta_pago_nombre": "",
    }
    movs = _mov(factura_simple, [mapeo_simple, retencion])
    ret = next(m for m in movs if m["Código cuenta contable"] == "236540")
    assert float(ret["Crédito"]) == 2500.0
    deb, cre = sumar(movs)
    assert deb == cre
    # La retención reduce lo que se le paga al proveedor.
    pago = next(m for m in movs if m["Código cuenta contable"] == "220505")
    assert float(pago["Crédito"]) == 116500.0


# ─── Otros tributos (INC, bolsas, IBUA…) ──────────────────────────────────────

def _con_tributos(mapeo, tributos):
    return {**mapeo, "otros_tributos": tributos}


def test_inc_en_compra_es_mayor_valor_del_gasto(factura_simple, mapeo_simple):
    """INC no es descontable en compras: engorda el gasto, no va a cuenta de impuesto."""
    inc = {"cod_dian": "04", "nombre": "INC", "grupo": "independiente", "valor": 8000.0, "cuenta": "", "cod_impuesto": ""}
    factura = {**factura_simple, "total": 127000.0}
    movs = _mov(factura, [_con_tributos(mapeo_simple, [inc])], es_venta=False)

    lineas_gasto = [m for m in movs if m["Código cuenta contable"] == "519530"]
    assert len(lineas_gasto) == 2, "el INC debe ir en su propia línea sobre la cuenta de gasto"
    assert sum(float(m["Débito"]) for m in lineas_gasto) == 108000.0  # 100.000 + 8.000
    deb, cre = sumar(movs)
    assert deb == cre


def test_inc_en_venta_se_desglosa_en_cuenta_propia(factura_simple, mapeo_simple):
    """En ventas el INC sí es independiente: va a su cuenta del catálogo, al crédito."""
    inc = {"cod_dian": "04", "nombre": "INC", "grupo": "independiente", "valor": 8000.0,
           "cuenta": "243601", "cod_impuesto": "INC8"}
    factura = {**factura_simple, "total": 127000.0}
    movs = _mov(factura, [_con_tributos(mapeo_simple, [inc])], es_venta=True)

    linea_inc = next(m for m in movs if m["Código cuenta contable"] == "243601")
    assert float(linea_inc["Crédito"]) == 8000.0, "el INC en ventas queda por pagar (crédito)"
    deb, cre = sumar(movs)
    assert deb == cre


def test_tributo_de_grupo_costo_no_usa_cuenta_propia(factura_simple, mapeo_simple):
    """IBUA/ICUI/INPP se suman al costo (compra) o al ingreso (venta), no van aparte."""
    ibua = {"cod_dian": "34", "nombre": "IBUA", "grupo": "costo", "valor": 5000.0, "cuenta": "", "cod_impuesto": ""}
    factura = {**factura_simple, "total": 124000.0}
    movs = _mov(factura, [_con_tributos(mapeo_simple, [ibua])], es_venta=True)

    lineas_ingreso = [m for m in movs if m["Código cuenta contable"] == "519530"]
    assert sum(float(m["Crédito"]) for m in lineas_ingreso) == 105000.0  # 100.000 + 5.000 IBUA
    deb, cre = sumar(movs)
    assert deb == cre


# ─── Descuentos y recargos globales ───────────────────────────────────────────

def test_descuento_global_reduce_el_gasto_y_lo_que_se_paga(factura_simple, mapeo_simple):
    factura = {**factura_simple, "descuento_global": 10000.0, "total": 109000.0}
    movs = _mov(factura, [mapeo_simple], es_venta=False)

    desc = next(m for m in movs if m["Descripción"] == "Descuento global")
    assert float(desc["Crédito"]) == 10000.0, "el descuento acredita la cuenta de gasto (menor valor)"
    pago = next(m for m in movs if m["Código cuenta contable"] == "220505")
    assert float(pago["Crédito"]) == 109000.0, "se le paga al proveedor el total ya con descuento"
    deb, cre = sumar(movs)
    assert deb == cre


def test_recargo_global_aumenta_el_valor(factura_simple, mapeo_simple):
    factura = {**factura_simple, "recargo_global": 3000.0, "total": 122000.0}
    movs = _mov(factura, [mapeo_simple], es_venta=False)

    rec = next(m for m in movs if m["Descripción"] == "Recargo global")
    assert float(rec["Débito"]) == 3000.0
    deb, cre = sumar(movs)
    assert deb == cre


def test_descuento_global_en_venta_reduce_el_ingreso(factura_simple, mapeo_simple):
    """Al invertir la venta, el descuento debita el ingreso (menor venta)."""
    factura = {**factura_simple, "descuento_global": 10000.0, "total": 109000.0}
    movs = _mov(factura, [mapeo_simple], es_venta=True)

    desc = next(m for m in movs if m["Descripción"] == "Descuento global")
    assert float(desc["Débito"]) == 10000.0
    cliente = next(m for m in movs if m["Código cuenta contable"] == "130505")
    assert float(cliente["Débito"]) == 109000.0
    deb, cre = sumar(movs)
    assert deb == cre


# ─── Varios ítems y redondeo ──────────────────────────────────────────────────

def test_items_identicos_no_se_colapsan(factura_simple, mapeo_simple):
    """Dos ítems iguales son dos líneas contables: colapsarlos descuadraba el total."""
    factura = {**factura_simple, "total": 238000.0}
    movs = _mov(factura, [mapeo_simple, dict(mapeo_simple)])
    lineas_gasto = [m for m in movs if m["Código cuenta contable"] == "519530"]
    assert len(lineas_gasto) == 2
    deb, cre = sumar(movs)
    assert deb == cre


def test_ajuste_de_redondeo_pequeno_cuadra_contra_el_total(factura_simple, mapeo_simple):
    """Si el IVA por renglón difiere en pocos pesos del total DIAN, se absorbe."""
    factura = {**factura_simple, "total": 118999.0}   # 1 peso menos por redondeo
    movs = _mov(factura, [mapeo_simple])
    pago = next(m for m in movs if m["Código cuenta contable"] == "220505")
    assert float(pago["Crédito"]) == 118999.0, "debe cuadrar exacto contra el total de la factura"
    deb, cre = sumar(movs)
    assert deb == cre


def test_diferencia_grande_no_se_oculta(factura_simple, mapeo_simple):
    """Una diferencia grande NO es redondeo: no debe absorberse en silencio."""
    factura = {**factura_simple, "total": 90000.0}
    movs = _mov(factura, [mapeo_simple])
    iva = next(m for m in movs if m["Código cuenta contable"] == "240820")
    assert float(iva["Débito"]) == 19000.0, "el IVA no debe alterarse para tapar un descuadre real"
