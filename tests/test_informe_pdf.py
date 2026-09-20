"""
El informe de analítica en PDF.

Se envía a clientes y a la gerencia, así que los errores acá salen de la
empresa. Lo que se protege es el formato de las cifras (un informe en pesos
colombianos mal formateado se lee mal) y que todo tipo de documento tenga color
propio en los gráficos.
"""
from __future__ import annotations

import pytest

from services import analitica_service, informe_pdf_service as pdf

pytestmark = pytest.mark.informe


# ─── Cifras en pesos ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("valor,esperado", [
    (1234567, "$ 1.234.567"),
    (0, "$ 0"),
    (1000, "$ 1.000"),
    (999, "$ 999"),
    # Las notas crédito restan: el negativo tiene que verse.
    (-45000, "-$ 45.000"),
    # Se redondea al peso: los centavos no aportan en un informe de gestión.
    (1234.56, "$ 1.235"),
])
def test_formato_en_pesos(valor, esperado):
    assert pdf._pesos(valor) == esperado


@pytest.mark.parametrize("valor,esperado", [
    (1_451_647_645, "1.5MM"),
    (602_698_138, "603M"),
    (45_000, "45k"),
    (850, "850"),
    (-120_000_000, "-120M"),
])
def test_cifra_corta_para_los_ejes(valor, esperado):
    """En el eje del gráfico la cifra completa no cabe."""
    assert pdf._corto(valor) == esperado


def test_mes_legible():
    assert pdf._mes_legible("2026-08") == "Ago\n26"
    assert pdf._mes_legible("2026-01") == "Ene\n26"


# ─── Identidad visual ────────────────────────────────────────────────────────

def test_usa_el_color_de_la_marca():
    """Mismo índigo que --brand en globals.css y que el Excel."""
    assert pdf.MARCA.hexval()[2:].upper() == "4F46E5"


def test_todo_tipo_de_documento_tiene_color_propio():
    """Un tipo sin color saldría gris en la torta, indistinguible de otro."""
    for tipo in analitica_service.SIGNO:
        assert tipo in pdf.COLOR_TIPO, f"{tipo} no tiene color en el gráfico"


# ─── Que el archivo realmente se arme ────────────────────────────────────────
#
# Las pruebas de arriba miran las piezas por separado, y eso no alcanzó: el PDF
# reventaba al construirse porque reportlab exige el '#' en los colores del
# marcado. Un error así solo aparece generando el archivo de verdad.

DATOS = {
    "kpis": {"ingresos": 217_271_073, "costos_gastos": 199_173_322,
             "resultado": 18_097_751, "documentos": 231},
    "por_tipo": [
        {"tipo": "ventas", "label": "Facturas de venta", "naturaleza": "ingresos",
         "signo": 1, "documentos": 142, "monto": 220_000_000},
        {"tipo": "nc_ventas", "label": "Notas crédito de venta", "naturaleza": "ingresos",
         "signo": -1, "documentos": 3, "monto": 10_680_000},
        {"tipo": "compras", "label": "Facturas de compra", "naturaleza": "costos_gastos",
         "signo": 1, "documentos": 86, "monto": 199_173_322},
    ],
    "serie_mensual": [
        {"mes": f"2026-{m:02d}", "ingresos": 20_000_000 * m,
         "costos_gastos": 15_000_000 * m, "resultado": 5_000_000 * m}
        for m in range(1, 10)
    ],
    "por_empresa": [],
    "por_tercero": [
        {"nit": "901694417", "nombre": "PROVEEDOR DE PRUEBA S.A.S.",
         "documentos": 12, "monto": 45_000_000},
    ],
}


@pytest.fixture
def datos_fijos(monkeypatch):
    """Evita la base de datos: lo que se prueba es el armado del archivo."""
    monkeypatch.setattr(analitica_service, "resumen", lambda *a, **k: DATOS)
    monkeypatch.setattr(pdf.analitica_service, "resumen", lambda *a, **k: DATOS)


def test_el_pdf_se_genera_y_es_un_pdf(datos_fijos):
    from datetime import date

    salida = pdf.generar_pdf(
        None, empresa_ids=[1], desde=date(2026, 1, 1), hasta=date(2026, 9, 30),
        nombre_empresa="BELTRAN INGENIERIA SAS",
    )
    contenido = salida.getvalue()
    assert contenido.startswith(b"%PDF-"), "no salió un PDF válido"
    assert len(contenido) > 2000, "el PDF salió sospechosamente vacío"


def test_el_pdf_no_falla_sin_datos(datos_fijos, monkeypatch):
    """Un periodo sin movimiento tiene que dar un PDF que diga eso, no un error."""
    from datetime import date

    vacio = {"kpis": {"ingresos": 0, "costos_gastos": 0, "resultado": 0, "documentos": 0},
             "por_tipo": [], "serie_mensual": [], "por_empresa": [], "por_tercero": []}
    monkeypatch.setattr(pdf.analitica_service, "resumen", lambda *a, **k: vacio)

    salida = pdf.generar_pdf(
        None, empresa_ids=[1], desde=date(2026, 1, 1), hasta=date(2026, 1, 31),
        nombre_empresa="EMPRESA SIN MOVIMIENTO",
    )
    assert salida.getvalue().startswith(b"%PDF-")
