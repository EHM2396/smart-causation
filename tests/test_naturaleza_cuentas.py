"""
Cuenta sugerida según la NATURALEZA del documento.

Reglas, aprendizaje e IA comparten el vocabulario (palabras clave), así que sin
este filtro lo aprendido en compras se colaba en ventas: "cemento" aprendido
como gasto se sugería al VENDER cemento. Acá se verifica que:
  - Una factura de venta nunca reciba como sugerencia una cuenta de costo o
    gasto: solo ingresos (clase 4), sin las devoluciones.
  - Una nota crédito de venta vaya a devoluciones en ventas (4175): reversa el
    ingreso.
  - Compras siga igual (gasto/costo), sin colarse ingresos.
Las pruebas no tocan BD ni red: el catálogo, las reglas y la IA se simulan.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.exporter import construir_movimientos
from services import ai_service, aprendizaje_service, causacion_service, cuentas_service, impuestos_service
from services.causacion_service import (
    NATURALEZA_COMPRA,
    NATURALEZA_DEVOLUCION_VENTA,
    NATURALEZA_VENTA,
    cuenta_coherente,
    cuentas_para_naturaleza,
    es_cuenta_devolucion_venta,
    naturaleza_operacion,
)
from tests.conftest import sumar

pytestmark = pytest.mark.sugerencias

NIT_CLIENTE = "800999888"

INGRESOS = [
    {"codigo": "41353501", "nombre": "Venta de materiales de construcción"},
    {"codigo": "41552001", "nombre": "Arrendamientos de bienes inmuebles"},
    {"codigo": "41750501", "nombre": "Devoluciones en ventas"},
]
GASTOS = [
    {"codigo": "51953001", "nombre": "Útiles, papelería y fotocopias"},
    {"codigo": "61350501", "nombre": "Costo de materiales de construcción"},
]


# ─── Simulación de BD, catálogo, reglas e IA ──────────────────────────────────

class _Resultado:
    def __init__(self, filas):
        self._filas = filas

    def all(self):
        return list(self._filas)


class FakeDB:
    """Sesión falsa: la consulta de aprendizaje devuelve las filas dadas (ya en
    el orden "más usadas primero" que daría la BD)."""

    def __init__(self, mapeos=()):
        self.mapeos = list(mapeos)

    def scalars(self, _stmt):
        return _Resultado(self.mapeos)


def mapeo(cuenta: str, keyword: str = "cemento", nit: str = NIT_CLIENTE):
    return SimpleNamespace(nit=nit, keyword=keyword, cuenta_puc=cuenta)


def regla(patron: str, cuenta: str):
    return SimpleNamespace(tipo="keyword", patron=patron, cuenta_puc=cuenta)


def item(key: str = "0_0", descripcion: str = "Cemento gris 50kg"):
    return {"key": key, "nit": NIT_CLIENTE, "descripcion": descripcion,
            "tipo_proveedor": "juridica", "nombre_proveedor": "Cliente de Prueba SAS"}


@pytest.fixture
def entorno(monkeypatch):
    estado = SimpleNamespace(
        reglas=[], ingresos=list(INGRESOS), gastos=list(GASTOS),
        ia_disponible=False, ia_llamadas=[], ia_respuesta={}, ejemplos=[],
    )
    monkeypatch.setattr(aprendizaje_service, "cargar_reglas", lambda db: estado.reglas)
    monkeypatch.setattr(cuentas_service, "listar_cuentas_ingreso", lambda db, empresa_id=None: estado.ingresos)
    monkeypatch.setattr(cuentas_service, "listar_cuentas_gasto", lambda db, empresa_id=None: estado.gastos)
    monkeypatch.setattr(causacion_service, "_obtener_cuentas_pago_batch", lambda db, nits, empresa_id: {})
    monkeypatch.setattr(
        causacion_service, "_obtener_ejemplos_aprendizaje",
        lambda db, empresa_id, opts, limit=200: estado.ejemplos,
    )
    monkeypatch.setattr(impuestos_service, "listar_como_dict", lambda db, empresa_id=None: [])
    monkeypatch.setattr(ai_service, "esta_disponible", lambda: estado.ia_disponible)

    def _ia(**kw):
        estado.ia_llamadas.append(kw)
        return {it["key"]: estado.ia_respuesta.get(it["key"]) for it in kw["items"]}

    monkeypatch.setattr(ai_service, "sugerir_batch", _ia)
    return estado


PAGO_COMPRAS = [{"codigo": "11050501", "nombre": "Caja general"},
                {"codigo": "22050501", "nombre": "Proveedores nacionales"}]
PAGO_VENTAS = [{"codigo": "11050501", "nombre": "Caja general"},
               {"codigo": "11100501", "nombre": "Bancos nacionales"},
               {"codigo": "13050501", "nombre": "Clientes nacionales"}]


def sugerir(items, mapeos=(), cuentas_pago=None, **kw):
    return causacion_service.sugerir_cuentas_batch(
        FakeDB(mapeos), items=items, empresa_id=1, usuario_id=1,
        cuentas_pago=cuentas_pago or [{"codigo": "22050501", "nombre": "Proveedores nacionales"}], **kw,
    )


def es_costo_o_gasto(codigo: str | None) -> bool:
    return str(codigo or "")[:1] in {"5", "6", "7"}


# ─── Naturaleza y cuentas admisibles ──────────────────────────────────────────

def test_naturaleza_segun_el_modulo():
    assert naturaleza_operacion(es_venta=False) == NATURALEZA_COMPRA
    assert naturaleza_operacion(es_venta=False, es_nota_credito=True) == NATURALEZA_COMPRA
    assert naturaleza_operacion(es_venta=True) == NATURALEZA_VENTA
    assert naturaleza_operacion(es_venta=True, es_nota_credito=True) == NATURALEZA_DEVOLUCION_VENTA


def test_identifica_cuentas_de_devolucion_en_ventas():
    assert es_cuenta_devolucion_venta("41750501", "Devoluciones en ventas")
    assert es_cuenta_devolucion_venta("41750599", "")  # 4175 del PUC aunque no diga el nombre
    assert es_cuenta_devolucion_venta("42500101", "Devolución en ventas no operacionales")
    assert not es_cuenta_devolucion_venta("41353501", "Venta de materiales")
    # Una devolución en COMPRAS no es una devolución en ventas.
    assert not es_cuenta_devolucion_venta("61350599", "Devoluciones en compras")


def test_venta_usa_ingresos_sin_devoluciones():
    codigos = {c["codigo"] for c in cuentas_para_naturaleza(INGRESOS, NATURALEZA_VENTA)}
    assert codigos == {"41353501", "41552001"}


def test_devolucion_usa_solo_devoluciones_en_ventas():
    codigos = {c["codigo"] for c in cuentas_para_naturaleza(INGRESOS, NATURALEZA_DEVOLUCION_VENTA)}
    assert codigos == {"41750501"}


def test_devolucion_sin_cuenta_4175_reversa_el_ingreso():
    sin_dev = [c for c in INGRESOS if not c["codigo"].startswith("4175")]
    codigos = {c["codigo"] for c in cuentas_para_naturaleza(sin_dev, NATURALEZA_DEVOLUCION_VENTA)}
    assert codigos == {"41353501", "41552001"}


def test_venta_nunca_acepta_costo_ni_gasto():
    validas = {"41353501", "41552001"}
    assert cuenta_coherente("41353501", NATURALEZA_VENTA, validas)
    assert not cuenta_coherente("51953001", NATURALEZA_VENTA, validas)
    assert not cuenta_coherente("61350501", NATURALEZA_VENTA, validas)
    assert not cuenta_coherente("41750501", NATURALEZA_VENTA, validas), "una venta no es una devolución"
    # Sin catálogo de ingresos, al menos debe ser clase 4.
    assert cuenta_coherente("41353501", NATURALEZA_VENTA, set())
    assert not cuenta_coherente("51953001", NATURALEZA_VENTA, set())


def test_compra_nunca_acepta_ingreso():
    assert cuenta_coherente("51953001", NATURALEZA_COMPRA)
    assert cuenta_coherente("14350501", NATURALEZA_COMPRA)
    assert not cuenta_coherente("41353501", NATURALEZA_COMPRA)


# ─── Prueba 1: factura de venta → cuenta de ingreso ───────────────────────────

def test_venta_no_reutiliza_lo_aprendido_como_costo(entorno):
    """"cemento" se causó muchas veces como costo en COMPRAS y alguna vez como
    ingreso en VENTAS. En una venta debe ganar el ingreso aunque el costo tenga
    más usos."""
    res = sugerir([item()], mapeos=[mapeo("61350501"), mapeo("41353501")], es_venta=True)
    assert res["0_0"].cuenta == "41353501"
    assert res["0_0"].origen == "aprendizaje"


def test_venta_no_sugiere_gasto_aunque_solo_haya_aprendizaje_de_compras(entorno):
    res = sugerir([item()], mapeos=[mapeo("61350501"), mapeo("51953001")], es_venta=True)
    assert not es_costo_o_gasto(res["0_0"].cuenta)


def test_venta_salta_la_regla_de_gasto(entorno):
    entorno.reglas = [regla("cemento", "51953001"), regla("cemento", "41353501")]
    res = sugerir([item()], es_venta=True)
    assert res["0_0"].cuenta == "41353501"
    assert res["0_0"].origen == "regla"


def test_venta_la_ia_solo_ve_cuentas_de_ingreso(entorno):
    entorno.ia_disponible = True
    entorno.ia_respuesta = {"0_0": ai_service.SugerenciaIA(cuenta_gasto="41353501", confianza=0.9)}
    res = sugerir([item()], es_venta=True)

    llamada = entorno.ia_llamadas[0]
    assert {c["codigo"] for c in llamada["cuentas_gasto"]} == {"41353501", "41552001"}
    assert llamada["naturaleza"] == NATURALEZA_VENTA
    # La lista de pago es de proveedores: en una venta no se le ofrece a la IA.
    assert llamada["cuentas_pago"] is None
    assert res["0_0"].cuenta == "41353501"
    assert res["0_0"].origen == "ia_alta"


def test_venta_no_le_pasa_a_la_ia_ejemplos_de_compras(entorno):
    entorno.ia_disponible = True
    entorno.ejemplos = [
        {"descripcion": "cemento gris", "cuenta": "61350501", "nombre_cuenta": "Costo"},
        {"descripcion": "cemento blanco", "cuenta": "41353501", "nombre_cuenta": "Venta"},
    ]
    sugerir([item()], es_venta=True)
    assert [e["cuenta"] for e in entorno.ia_llamadas[0]["ejemplos_aprendizaje"]] == ["41353501"]


# ─── Prueba 2: nota crédito de venta → devolución en ventas ───────────────────

def test_nc_venta_va_a_devoluciones_en_ventas(entorno):
    """Con UNA cuenta de devoluciones en el catálogo, la sugerencia sale de la
    naturaleza del documento, aunque el ítem se haya aprendido como ingreso."""
    res = sugerir([item()], mapeos=[mapeo("41353501")], es_venta=True, es_nota_credito=True)
    assert res["0_0"].cuenta == "41750501"
    assert res["0_0"].origen == "devolucion_venta"


def test_nc_venta_con_varias_devoluciones_la_ia_elige_entre_ellas(entorno):
    entorno.ingresos = INGRESOS + [{"codigo": "41753501", "nombre": "Devoluciones en ventas - comercio"}]
    entorno.ia_disponible = True
    sugerir([item()], es_venta=True, es_nota_credito=True)

    llamada = entorno.ia_llamadas[0]
    assert {c["codigo"] for c in llamada["cuentas_gasto"]} == {"41750501", "41753501"}
    assert llamada["naturaleza"] == NATURALEZA_DEVOLUCION_VENTA


def test_nc_venta_respeta_la_devolucion_aprendida(entorno):
    entorno.ingresos = INGRESOS + [{"codigo": "41753501", "nombre": "Devoluciones en ventas - comercio"}]
    res = sugerir([item()], mapeos=[mapeo("61350501"), mapeo("41753501")], es_venta=True, es_nota_credito=True)
    assert res["0_0"].cuenta == "41753501"
    assert res["0_0"].origen == "aprendizaje"


def test_nc_venta_sin_cuenta_de_devolucion_reversa_el_ingreso(entorno):
    entorno.ingresos = [c for c in INGRESOS if not c["codigo"].startswith("4175")]
    res = sugerir([item()], mapeos=[mapeo("61350501"), mapeo("41353501")], es_venta=True, es_nota_credito=True)
    assert res["0_0"].cuenta == "41353501"


# ─── Compras: sin cambios, y sin ingresos colados ─────────────────────────────

def test_compra_no_reutiliza_lo_aprendido_como_ingreso(entorno):
    res = sugerir([item()], mapeos=[mapeo("41353501"), mapeo("61350501")])
    assert res["0_0"].cuenta == "61350501"


def test_compra_la_ia_sigue_viendo_gastos_y_cuentas_de_pago(entorno):
    entorno.ia_disponible = True
    sugerir([item()])
    llamada = entorno.ia_llamadas[0]
    assert {c["codigo"] for c in llamada["cuentas_gasto"]} == {"51953001", "61350501"}
    assert llamada["naturaleza"] == NATURALEZA_COMPRA
    assert llamada["cuentas_pago"] == [{"codigo": "22050501", "nombre": "Proveedores nacionales"}]


# ─── Contrapartida: en ventas es Clientes / Caja / Bancos ─────────────────────

def test_contrapartida_de_venta_incluye_clientes_y_no_proveedores():
    es = cuentas_service.es_contrapartida
    assert es("13050501", es_venta=True), "1305 Clientes es la contrapartida de una venta a crédito"
    assert es("11050501", es_venta=True) and es("11100501", es_venta=True)
    assert es("28050501", es_venta=True), "anticipo recibido del cliente"
    assert not es("22050501", es_venta=True), "proveedores no es contrapartida de una venta"
    # Compras no cambia.
    assert es("22050501") and es("11050501") and es("12250501")
    assert not es("13050501")


def test_la_lista_de_contrapartidas_de_ventas_consulta_clientes():
    capturado = {}

    class _DB:
        def scalars(self, stmt):
            capturado["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            return _Resultado([])

    cuentas_service.listar_metodos_pago(_DB(), empresa_id=1, es_venta=True)
    for prefijo in ("11", "13", "27", "28"):
        assert f"LIKE '{prefijo}%'" in capturado["sql"]
    assert "LIKE '22%'" not in capturado["sql"]


@pytest.mark.parametrize("forma,medio,esperada", [
    ("Crédito", "", "13050501"),
    ("Contado", "Efectivo", "11050501"),
    ("Contado", "Transferencia débito bancaria", "11100501"),
])
def test_venta_contrapartida_por_forma_de_pago(forma, medio, esperada):
    codigo, origen = causacion_service._cuenta_pago_por_forma_pago(forma, medio, PAGO_VENTAS, es_venta=True)
    assert (codigo, origen) == (esperada, "forma_pago")


def test_compra_a_credito_sigue_en_proveedores():
    codigo, _ = causacion_service._cuenta_pago_por_forma_pago("Crédito", "", PAGO_COMPRAS)
    assert codigo == "22050501"


def test_venta_no_hereda_la_cuenta_de_proveedor_del_tercero(entorno, monkeypatch):
    """El tercero también es proveedor: su última contrapartida fue 2205. En la
    venta no debe sugerirse."""
    monkeypatch.setattr(causacion_service, "_obtener_cuentas_pago_batch",
                        lambda db, nits, empresa_id: {NIT_CLIENTE: "22050501"})
    res = sugerir([item()], mapeos=[mapeo("41353501")], cuentas_pago=PAGO_VENTAS, es_venta=True)
    assert res["0_0"].cuenta_pago is None


def test_venta_respeta_la_cuenta_de_cliente_aprendida(entorno, monkeypatch):
    monkeypatch.setattr(causacion_service, "_obtener_cuentas_pago_batch",
                        lambda db, nits, empresa_id: {NIT_CLIENTE: "13050501"})
    res = sugerir([item()], mapeos=[mapeo("41353501")], cuentas_pago=PAGO_VENTAS, es_venta=True)
    assert res["0_0"].cuenta_pago == "13050501"
    assert res["0_0"].cuenta_pago_origen == "aprendizaje"


# ─── Prompt de la IA según la naturaleza ──────────────────────────────────────

COMBOS = [("Cemento gris 50kg", "juridica", "Cliente de Prueba SAS")]
CUENTAS = [{"codigo": "41353501", "nombre": "Venta de materiales"}]


def test_prompt_de_venta_habla_de_ingresos():
    p = ai_service._construir_prompt_batch(COMBOS, CUENTAS, [], None, None, NATURALEZA_VENTA)
    assert "FACTURAS DE VENTA" in p
    assert "Cuentas PUC de ingreso disponibles" in p
    assert '"cuenta_ingreso"' in p
    assert "NUNCA uses cuentas de costo ni de gasto" in p
    assert 'cliente="Cliente de Prueba SAS"' in p
    assert "Cuentas PUC de gasto disponibles" not in p


def test_prompt_de_nc_venta_habla_de_devolucion():
    p = ai_service._construir_prompt_batch(COMBOS, CUENTAS, [], None, None, NATURALEZA_DEVOLUCION_VENTA)
    assert "NOTAS CRÉDITO DE VENTA" in p
    assert "DISMINUYE el ingreso" in p
    assert "devoluciones en ventas" in p


def test_prompt_de_compra_no_cambia():
    p = ai_service._construir_prompt_batch(COMBOS, CUENTAS, [], None, None)
    assert "Cuentas PUC de gasto disponibles" in p
    assert '"cuenta_gasto"' in p
    assert "tipos de gasto y su naturaleza contable" in p
    assert 'proveedor="Cliente de Prueba SAS"' in p


def test_la_respuesta_de_ventas_se_lee_de_cuenta_ingreso(monkeypatch):
    respuesta = {"resultados": [{"indice": 1, "cuenta_ingreso": "41353501", "confianza": 0.9, "explicacion": "venta"}]}

    class _Cliente:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

        @staticmethod
        def _crear(**_kw):
            msg = SimpleNamespace(content=json.dumps(respuesta))
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    monkeypatch.setattr(ai_service, "_OpenAI", _Cliente)
    out = ai_service._procesar_chunk_batch(COMBOS, CUENTAS, [], None, "modelo", "clave", None, NATURALEZA_VENTA)
    assert out[COMBOS[0]].cuenta_gasto == "41353501"


# ─── Partida contable de la venta y de su devolución (IVA generado) ───────────

def _factura(total=119000.0):
    return {"numero_dian": "FEV100", "cufe": "cufe", "fecha": "15/09/2026", "nit": NIT_CLIENTE,
            "razon_social": "Cliente de Prueba SAS", "total": total}


def _mapeo_venta(cuenta_ingreso: str, cuenta_iva: str = "24080101"):
    return {"descripcion": "Cemento gris 50kg", "base": 100000.0, "valor_impuesto": 19000.0,
            "porcentaje": 19.0, "cod_impuesto": "1", "es_retencion": False,
            "cuenta_gasto": cuenta_ingreso, "cuenta_impuesto_deb": cuenta_iva,
            "cuenta_impuesto_cre": "", "cuenta_pago": "", "cuenta_pago_nombre": ""}


@pytest.mark.contable
def test_venta_ingreso_e_iva_generado_al_credito():
    movs = construir_movimientos(_factura(), 1, [_mapeo_venta("41353501")], es_venta=True)
    por_cuenta = {m["Código cuenta contable"]: m for m in movs}
    assert float(por_cuenta["41353501"]["Crédito"]) == 100000.0
    assert float(por_cuenta["24080101"]["Crédito"]) == 19000.0
    assert por_cuenta["24080101"]["Descripción"] == "Iva generado"
    assert float(por_cuenta["130505"]["Débito"]) == 119000.0
    assert sumar(movs)[0] == sumar(movs)[1]


@pytest.mark.contable
def test_nc_venta_reversa_ingreso_e_iva_generado():
    """Devolución: débito a devoluciones en ventas y al IVA generado (lo
    disminuye), crédito al cliente."""
    movs = construir_movimientos(
        _factura(), 1, [_mapeo_venta("41750501")], es_venta=True, es_nota_credito=True,
    )
    por_cuenta = {m["Código cuenta contable"]: m for m in movs}
    assert float(por_cuenta["41750501"]["Débito"]) == 100000.0
    assert float(por_cuenta["24080101"]["Débito"]) == 19000.0
    assert por_cuenta["24080101"]["Descripción"] == "Iva devolucion en ventas"
    assert float(por_cuenta["130505"]["Crédito"]) == 119000.0
    assert sumar(movs)[0] == sumar(movs)[1]
