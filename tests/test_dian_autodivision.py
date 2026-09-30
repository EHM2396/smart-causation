"""
Auto-división del rango de fechas al consultar la DIAN.

El portal de la DIAN corre sobre Cosmos DB y NO pagina de forma confiable por
offset: al pedir la 2.ª página el orden se re-baraja y quedan documentos afuera
en silencio. Por eso se perdían facturas en rangos amplios SIN ningún aviso.

La cura es no confiar en el paginado: se usa solo la PRIMERA página (la única
confiable) como sonda y, si vino llena, se parte el rango de fechas a la mitad y
se re-consulta cada mitad hasta que cada subrango entra en una sola página. Estas
pruebas simulan el tope de página de la DIAN y verifican que NO se pierda ningún
documento, sin importar cuántos haya ni cómo estén repartidos por fecha.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

import services.dian_service as ds

pytestmark = pytest.mark.dian

TOKEN = "https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=1|2&rk=901694417&token=abc"


# ─── Simulador de la DIAN (solo primera página, como la sonda real) ───────────

def _instalar_dian_falsa(monkeypatch, docs_por_dia: dict[date, int], tope: int):
    """Reemplaza ``consultar_documentos`` por una DIAN de mentira que, igual que
    la real con ``max_paginas=1``, SOLO devuelve la primera página del rango
    (los ``tope`` documentos más recientes) y marca ``incompleto`` si había más.

    Como la sonda nunca ve más allá de la primera página, la ÚNICA forma de que
    ``consultar_documentos_completo`` recupere todo es partiendo el rango: eso es
    justo lo que se quiere probar. Devuelve el universo de ids para comparar.
    """
    universo: list[dict] = []
    for d, n in docs_por_dia.items():
        for i in range(n):
            universo.append({
                "id": f"{d.isoformat()}-{i}",
                "numero": f"F{i}",
                "fecha": d.strftime("%d/%m/%Y"),
                "proveedor": "Proveedor",
                "tipo": "Factura",
            })

    llamadas = {"n": 0}

    def _fake(auth_url, fecha_desde, fecha_hasta, modo="compras", max_paginas=None):
        llamadas["n"] += 1
        try:
            d1 = datetime.strptime(fecha_desde, "%d/%m/%Y").date()
            d2 = datetime.strptime(fecha_hasta, "%d/%m/%Y").date()
        except ValueError:
            # La DIAN real no parsea las fechas, solo las reenvía. Aquí, ante un
            # formato que no reconocemos, devolvemos vacío sin reventar.
            return {"success": True, "total": 0, "total_dian": 0, "incompleto": False, "documents": []}
        en_rango = [x for x in universo
                    if d1 <= datetime.strptime(x["fecha"], "%d/%m/%Y").date() <= d2]
        # La DIAN ordena por fecha DESCENDENTE; la 1.ª página son los más recientes.
        en_rango.sort(key=lambda x: datetime.strptime(x["fecha"], "%d/%m/%Y").date(), reverse=True)
        total = len(en_rango)
        pagina = en_rango[:tope]
        return {
            "success": True,
            "total": len(pagina),
            "total_dian": total,
            "incompleto": len(pagina) < total,
            "documents": pagina,
        }

    monkeypatch.setattr(ds, "_PAGINA", tope)
    monkeypatch.setattr(ds, "consultar_documentos", _fake)
    return universo, llamadas


def _ids(res: dict) -> set[str]:
    return {d["id"] for d in res["documents"]}


# ─── El rango cabe en una sola página → una sola consulta, sin partir ─────────

def test_rango_pequeno_no_biseca_y_trae_todo(monkeypatch):
    dia = date(2026, 3, 10)
    universo, llamadas = _instalar_dian_falsa(monkeypatch, {dia: 3}, tope=5)

    res = ds.consultar_documentos_completo(TOKEN, "01/03/2026", "31/03/2026")

    assert _ids(res) == {d["id"] for d in universo}
    assert res["incompleto"] is False
    assert llamadas["n"] == 1  # cupo en la primera página: no hizo falta partir


# ─── Muchos documentos repartidos en fechas → se parte hasta traerlos TODOS ───

def test_rango_con_mas_del_tope_biseca_y_no_pierde_nada(monkeypatch):
    # 3 documentos por día durante 20 días = 60 documentos; con tope 5 por página,
    # una sola consulta jamás los traería. La auto-división debe recuperarlos todos.
    base = date(2026, 1, 1)
    docs_por_dia = {base + timedelta(days=k): 3 for k in range(20)}
    universo, llamadas = _instalar_dian_falsa(monkeypatch, docs_por_dia, tope=5)

    res = ds.consultar_documentos_completo(TOKEN, "01/01/2026", "20/01/2026")

    assert res["total"] == 60
    assert _ids(res) == {d["id"] for d in universo}
    assert res["incompleto"] is False
    assert llamadas["n"] > 1  # tuvo que partir el rango


def test_no_duplica_aunque_los_subrangos_se_solapen(monkeypatch):
    # Un solo día muy cargado dentro de un rango grande: al partir, varios
    # subrangos incluyen ese día. El dedup por id debe dejar cada documento una vez.
    docs_por_dia = {date(2026, 6, 15): 4}
    for k in range(30):
        docs_por_dia.setdefault(date(2026, 6, 1) + timedelta(days=k), 0)
    docs_por_dia[date(2026, 6, 3)] = 3
    docs_por_dia[date(2026, 6, 25)] = 3
    universo, _ = _instalar_dian_falsa(monkeypatch, docs_por_dia, tope=5)

    res = ds.consultar_documentos_completo(TOKEN, "01/06/2026", "30/06/2026")

    ids = [d["id"] for d in res["documents"]]
    assert len(ids) == len(set(ids))  # sin duplicados
    assert set(ids) == {d["id"] for d in universo}


# ─── Caso extremo: un SOLO día con más documentos que el tope ─────────────────

def test_un_dia_saturado_avisa_en_vez_de_perder_en_silencio(monkeypatch):
    # 8 documentos el mismo día, tope 5: ni partiendo se puede bajar de 5 (es un
    # solo día). Antes se perdían 3 sin aviso; ahora debe marcar incompleto y
    # nombrar el día para que el usuario lo revise.
    dia = date(2026, 4, 7)
    _instalar_dian_falsa(monkeypatch, {dia: 8}, tope=5)

    res = ds.consultar_documentos_completo(TOKEN, "01/04/2026", "30/04/2026")

    assert res["incompleto"] is True
    assert "07/04/2026" in res["advertencia"]
    # Igual devuelve lo que sí pudo traer (la primera página de ese día).
    assert res["total"] == 5


# ─── Formato de fecha inesperado → cae a una consulta normal, sin romperse ────

def test_fecha_invalida_no_revienta(monkeypatch):
    _instalar_dian_falsa(monkeypatch, {date(2026, 5, 1): 2}, tope=5)
    # 'consultar_documentos' está mockeado; con fechas no DD/MM/YYYY el completo
    # delega en él sin intentar bisecar.
    res = ds.consultar_documentos_completo(TOKEN, "2026-05-01", "2026-05-31")
    assert res["success"] is True


# ─── Respuestas que no cuadran (caso real: 185 docs ene–abr salían como 94) ───

def _caso_real(monkeypatch):
    """94 documentos en ene–1 mar y 91 en 2 mar–abr (185), tope 150: el rango
    entero se parte en dos mitades, igual que en la DIAN real."""
    docs_por_dia = {}
    for k in range(60):   # 01/01 .. 01/03
        docs_por_dia[date(2026, 1, 1) + timedelta(days=k)] = 0
    for k in range(94):
        docs_por_dia[date(2026, 1, 1) + timedelta(days=k % 60)] += 1
    for k in range(91):
        d = date(2026, 3, 2) + timedelta(days=k % 59)
        docs_por_dia[d] = docs_por_dia.get(d, 0) + 1
    universo, _ = _instalar_dian_falsa(monkeypatch, docs_por_dia, tope=150)
    return universo, ds.consultar_documentos


def _con_falla(monkeypatch, real, rango: str, respuesta, veces: int = 1):
    """La DIAN falla ``veces`` para ``rango`` devolviendo ``respuesta(real)``."""
    fallas = {"n": 0}

    def _fake(auth_url, fecha_desde, fecha_hasta, modo="compras", max_paginas=None):
        if f"{fecha_desde}-{fecha_hasta}" == rango and fallas["n"] < veces:
            fallas["n"] += 1
            return respuesta(real)
        return real(auth_url, fecha_desde, fecha_hasta, modo=modo, max_paginas=max_paginas)

    monkeypatch.setattr(ds, "consultar_documentos", _fake)


def test_filtro_de_fechas_viejo_se_detecta_y_reintenta(monkeypatch):
    # La DIAN no aplicó el filtro de mar–abr y devolvió otra vez ene–feb.
    universo, real = _caso_real(monkeypatch)
    _con_falla(monkeypatch, real, "02/03/2026-30/04/2026",
               lambda r: r(TOKEN, "01/01/2026", "01/03/2026", max_paginas=1))

    res = ds.consultar_documentos_completo(TOKEN, "01/01/2026", "30/04/2026")

    assert res["total"] == 185
    assert _ids(res) == {d["id"] for d in universo}
    assert res["incompleto"] is False


def test_mitad_vacia_no_cuadra_con_el_total_y_se_reconsulta(monkeypatch):
    universo, real = _caso_real(monkeypatch)
    vacio = {"success": True, "total": 0, "total_dian": 0, "incompleto": False, "documents": []}
    _con_falla(monkeypatch, real, "02/03/2026-30/04/2026", lambda r: vacio)

    res = ds.consultar_documentos_completo(TOKEN, "01/01/2026", "30/04/2026")

    assert res["total"] == 185
    assert _ids(res) == {d["id"] for d in universo}


def test_si_la_dian_sigue_fallando_avisa_en_vez_de_dar_un_numero_corto(monkeypatch):
    _, real = _caso_real(monkeypatch)
    vacio = {"success": True, "total": 0, "total_dian": 0, "incompleto": False, "documents": []}
    _con_falla(monkeypatch, real, "02/03/2026-30/04/2026", lambda r: vacio, veces=99)

    res = ds.consultar_documentos_completo(TOKEN, "01/01/2026", "30/04/2026")

    assert res["incompleto"] is True
    assert "reporta 185" in res["advertencia"]


# ─── Clase del documento desde el listado (separar factura / NC antes de bajar) ─

@pytest.mark.parametrize("tipo, clase", [
    ("Factura electrónica", "factura"),
    ("Factura electrónica de exportación", "factura"),
    ("Nota Crédito electrónica", "nota_credito"),
    ("Nota credito", "nota_credito"),
    ("Nota débito electrónica", "nota_debito"),
    ("01", "factura"),
    ("91", "nota_credito"),
    ("92", "nota_debito"),
    ("Application Response", "desconocido"),
    ("", "desconocido"),
])
def test_clase_del_listado(tipo, clase):
    assert ds.clase_del_listado(tipo) == clase


def test_normalizar_documentos_incluye_la_clase():
    res = {"data": [
        {"DT_RowId": "a", "DocumentType": "Factura electrónica"},
        {"DT_RowId": "b", "DocumentType": "<span>Nota Crédito electrónica</span>"},
        {"DT_RowId": "c"},
        # Formato real de GetReceivedDocuments: el tipo viene en ``docTypeName``.
        {"DT_RowId": "d", "docTypeName": "Factura electrónica"},
        {"DT_RowId": "e", "docTypeName": "Nota Crédito electrónica"},
    ]}
    clases = {d["id"]: d["clase"] for d in ds._normalizar_documentos(res)}
    assert clases == {"a": "factura", "b": "nota_credito", "c": "desconocido",
                      "d": "factura", "e": "nota_credito"}


# ─── El control de páginas de _paginar_datatables ─────────────────────────────

class _FakeResp:
    def __init__(self, data, total):
        self._data, self._total, self.status_code = data, total, 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": self._data, "recordsTotal": self._total}


class _FakeSession:
    """Devuelve páginas según el ``start`` que pida el paginador."""
    def __init__(self, paginas: list[list[dict]]):
        self.paginas = paginas
        self.llamadas = 0

    def post(self, url, data=None, headers=None, timeout=None):
        self.llamadas += 1
        start = int(data["start"])
        idx = start // ds._PAGINA
        page = self.paginas[idx] if idx < len(self.paginas) else []
        total = sum(len(p) for p in self.paginas)
        return _FakeResp(page, total)


def test_paginar_sonda_una_pagina_frena_en_la_primera():
    # Dos páginas disponibles, pero como sonda (max_paginas=1) solo debe pedir una.
    p1 = [{"DT_RowId": f"a{i}"} for i in range(ds._PAGINA)]  # primera página llena
    p2 = [{"DT_RowId": "b0"}]
    ses = _FakeSession([p1, p2])

    res = ds._paginar_datatables(ses, "http://x", {}, {}, max_paginas=1)

    assert ses.llamadas == 1
    assert len(res["data"]) == ds._PAGINA


def test_paginar_sin_tope_recorre_todas_las_paginas():
    p1 = [{"DT_RowId": f"a{i}"} for i in range(ds._PAGINA)]  # llena → hay más
    p2 = [{"DT_RowId": "b0"}, {"DT_RowId": "b1"}]            # parcial → última
    ses = _FakeSession([p1, p2])

    res = ds._paginar_datatables(ses, "http://x", {}, {})

    assert ses.llamadas == 2
    assert len(res["data"]) == ds._PAGINA + 2
