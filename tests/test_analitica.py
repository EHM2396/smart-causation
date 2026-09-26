"""
Analítica de costos, gastos e ingresos.

Lo que se protege acá es que las cifras signifiquen algo: que las notas crédito
RESTEN y que cada documento electrónico caiga en su naturaleza. Si esto se
rompe, el dashboard muestra números que parecen correctos pero no lo son — que
es peor que no mostrarlos.
"""
from __future__ import annotations

import pytest

from db.models.contabilidad import FacturaCausada
from services.analitica_service import ETIQUETA, NATURALEZA, ORDEN, SIGNO
from services.causacion_service import base_gravable_de, columna_fecha
from services.documentos_dian_service import clasificar, nombre_contraparte

pytestmark = pytest.mark.analitica


# ─── Naturaleza de cada documento electrónico DIAN ───────────────────────────

@pytest.mark.parametrize("tipo,naturaleza", [
    ("ventas", "ingresos"),
    ("nc_ventas", "ingresos"),
    ("nd_ventas", "ingresos"),
    ("compras", "costos_gastos"),
    ("nc", "costos_gastos"),
    ("nd", "costos_gastos"),
    # El documento soporte legaliza un costo con personas naturales no obligadas
    # a facturar: es costo/gasto, no un ingreso, aunque lo emita el comprador.
    ("soporte", "costos_gastos"),
    ("nc_soporte", "costos_gastos"),
])
def test_naturaleza_por_tipo_de_documento(tipo, naturaleza):
    assert NATURALEZA[tipo] == naturaleza


# ─── Las notas crédito restan y las débito suman ─────────────────────────────

@pytest.mark.parametrize("tipo", ["nc", "nc_ventas", "nc_soporte"])
def test_las_notas_credito_restan(tipo):
    assert SIGNO[tipo] == -1


@pytest.mark.parametrize("tipo", ["compras", "ventas", "soporte"])
def test_las_facturas_suman(tipo):
    assert SIGNO[tipo] == 1


@pytest.mark.parametrize("tipo", ["nd", "nd_ventas"])
def test_las_notas_debito_suman(tipo):
    """Una nota débito aumenta el valor del documento que ajusta. No tiene módulo
    de causación, pero existe en la DIAN: omitirla falsearía el informe."""
    assert SIGNO[tipo] == 1


# ─── Clasificación de lo que trae el token ───────────────────────────────────

@pytest.mark.parametrize("tipo_documento,origen,esperado", [
    ("factura", "compras", "compras"),
    ("factura", "ventas", "ventas"),
    ("nota_credito", "compras", "nc"),
    ("nota_credito", "ventas", "nc_ventas"),
    ("nota_debito", "compras", "nd"),
    ("nota_debito", "ventas", "nd_ventas"),
    # El origen manda para el documento soporte: se consulta por su propio
    # endpoint, así que es más confiable que leer el CustomizationID.
    ("factura", "soporte", "soporte"),
    ("nota_credito", "soporte_ajuste", "nc_soporte"),
    # Malla de seguridad: un DS que se cuele en otra bandeja igual va a su tipo.
    ("documento_soporte", "compras", "soporte"),
    ("nota_ajuste_soporte", "compras", "nc_soporte"),
])
def test_clasificar_documento_del_token(tipo_documento, origen, esperado):
    assert clasificar({"tipo_documento": tipo_documento}, origen) == esperado


def test_clasificar_sin_tipo_documento_asume_factura():
    assert clasificar({}, "compras") == "compras"
    assert clasificar({}, "ventas") == "ventas"


@pytest.mark.parametrize("origen", ["compras", "ventas"])
def test_la_nota_debito_cuenta_en_analitica_pero_no_se_puede_causar(origen):
    """Los dos caminos difieren A PROPÓSITO y conviene que siga así.

    La analítica refleja lo que la DIAN reporta, así que una nota débito suma.
    La causación, en cambio, no tiene módulo donde registrarla: el importador la
    omite. Si alguien "unifica" ambos criterios, esta prueba avisa.
    """
    from api.routers.dian import _bucket_de

    factura = {"tipo_documento": "nota_debito"}
    assert clasificar(factura, origen) in ("nd", "nd_ventas")   # sí entra al informe
    assert _bucket_de(factura, origen) is None                  # no se puede causar


def test_una_venta_real_guarda_el_cliente_no_la_propia_empresa():
    """Bug real de producción: BELTRAN aparecía como 'proveedor' de sí misma en
    el Formulario 300, porque sus propias facturas de venta se estaban
    guardando sin reemplazar el tercero.

    El emisor de una factura de venta ES la empresa: el parser llena nit/
    razon_social con esos datos por defecto. Para que el tercero sea el
    CLIENTE hay que llamar usar_cliente_como_tercero — lo que causacion.py y
    dian.py ya hacían, y a la sincronización de Analítica/Formulario 300 le
    faltaba."""
    from core.parser import usar_cliente_como_tercero

    factura_como_la_da_el_parser = {
        "nit": "901694417", "razon_social": "BELTRAN INGENIERIA S.A.S.",  # el emisor
        "comprador_nit": "800555111", "comprador_razon_social": "CLIENTE REAL S.A.S.",
        "tipo_documento": "factura",
    }
    corregida = usar_cliente_como_tercero(dict(factura_como_la_da_el_parser))
    assert corregida["nit"] == "800555111", "debe quedar el NIT del cliente, no el de BELTRAN"
    assert corregida["razon_social"] == "CLIENTE REAL S.A.S."


def test_analitica_aplica_el_reemplazo_de_tercero_en_ventas():
    """Guarda de regresión: el código fuente del router tiene que seguir
    llamando a usar_cliente_como_tercero para origen == 'ventas', antes de
    guardar_documento. Si alguien reordena o borra esa línea sin darse cuenta,
    vuelve el mismo bug."""
    import inspect
    import api.routers.analitica as router

    fuente = inspect.getsource(router)
    assert "usar_cliente_como_tercero" in fuente, (
        "analitica.py dejó de llamar a usar_cliente_como_tercero: "
        "las ventas volverían a guardarse con el NIT de la propia empresa"
    )


def test_persona_natural_sin_razon_social_arma_el_nombre_con_person():
    """Bug real de producción: en 'Terceros con mayor peso' varias barras
    salían sin nombre ('—') a pesar de que la información descargada estaba
    completa.

    Cuando la contraparte es una persona natural, el XML no trae razón social
    (PartyLegalEntity) sino nombre y apellido (cac:Person) — típico del
    documento soporte, que se emite a personas no obligadas a facturar. El
    parser ya guardaba esos campos aparte (nombres_tercero/apellidos_tercero),
    pero nadie los usaba para completar el nombre a mostrar."""
    factura = {
        "nit": "1020304050", "razon_social": "",
        "nombres_tercero": "Jose Alberto", "apellidos_tercero": "Alvarez Cortes",
    }
    assert nombre_contraparte(factura) == "Jose Alberto Alvarez Cortes"


def test_con_razon_social_no_hace_falta_el_respaldo():
    """El respaldo es solo eso — un respaldo. No debe pisar una razón social
    que sí vino en el XML. Reproduce exactamente `guardar_documento`:
    `factura.get("razon_social") or nombre_contraparte(factura)`."""
    factura = {"razon_social": "PROVEEDOR S.A.S.", "nombres_tercero": "Otro", "apellidos_tercero": "Nombre"}
    razon_social_guardada = factura.get("razon_social") or nombre_contraparte(factura)
    assert razon_social_guardada == "PROVEEDOR S.A.S."


def test_sin_ningun_nombre_el_respaldo_queda_vacio_no_inventa():
    """Sin razón social ni persona, mejor un campo vacío (se ve como '—') que
    un nombre inventado."""
    assert nombre_contraparte({}) == ""
    assert nombre_contraparte({"nombres_tercero": "  ", "apellidos_tercero": ""}) == ""


def test_solo_nombre_o_solo_apellido_no_deja_espacio_suelto():
    assert nombre_contraparte({"nombres_tercero": "Ana", "apellidos_tercero": ""}) == "Ana"
    assert nombre_contraparte({"nombres_tercero": "", "apellidos_tercero": "Gómez"}) == "Gómez"


def test_el_respaldo_tambien_aplica_a_ventas_con_cliente_natural():
    """El mismo respaldo sirve para los dos lados: en una venta a un cliente
    persona natural, usar_cliente_como_tercero ya intercambia estos mismos
    campos (nombres_tercero/apellidos_tercero van entre los que se
    sustituyen), así que guardar_documento los completa igual."""
    from core.parser import usar_cliente_como_tercero

    factura = {
        "nit": "900123456", "razon_social": "MI EMPRESA S.A.S.",
        "comprador_nit": "1098765432", "comprador_razon_social": "",
        "comprador_nombres_tercero": "Laura", "comprador_apellidos_tercero": "Pérez",
        "tipo_documento": "factura",
    }
    corregida = usar_cliente_como_tercero(dict(factura))
    assert corregida["razon_social"] == ""
    assert nombre_contraparte(corregida) == "Laura Pérez"


def test_todo_lo_que_clasifica_tiene_signo_y_naturaleza():
    """Un tipo que el traído produzca pero la analítica no conozca se sumaría
    con signo por defecto, en silencio y mal."""
    for tipo_doc in ("factura", "nota_credito", "nota_debito"):
        for origen in ("compras", "ventas", "soporte", "soporte_ajuste"):
            tipo = clasificar({"tipo_documento": tipo_doc}, origen)
            assert tipo in SIGNO, f"{tipo} no tiene signo"
            assert tipo in NATURALEZA, f"{tipo} no tiene naturaleza"


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


# ─── Sobre qué fecha corre el rango ──────────────────────────────────────────
#
# No da lo mismo: una factura emitida en agosto y causada en septiembre aparece
# en un mes o en el otro según lo que se elija. El historial y la analítica deben
# resolverlo IGUAL, o el mismo rango daría resultados distintos en cada pantalla.

@pytest.mark.parametrize("campo,columna", [
    ("emision", FacturaCausada.fecha_factura),
    ("causacion", FacturaCausada.fecha_causacion),
    (None, FacturaCausada.fecha_causacion),          # por defecto: causación
    ("cualquier_cosa", FacturaCausada.fecha_causacion),
])
def test_columna_fecha(campo, columna):
    assert columna_fecha(campo) is columna


def test_historial_y_analitica_usan_la_misma_definicion_de_fecha():
    """El helper del router debe delegar en el del servicio, no tener copia propia."""
    from api.routers.causacion import _columna_fecha
    for campo in ("emision", "causacion", None):
        assert _columna_fecha(campo) is columna_fecha(campo)
