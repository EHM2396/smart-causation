"""
Informe de analítica en PDF, pensado para enviar a un cliente o a la gerencia.

Divide el trabajo con el Excel en vez de duplicarlo:
  · PDF   → presentable, con marca, para LEER. Resumen y gráficos.
  · Excel → para TRABAJAR: el detalle documento por documento y los ítems, que
            en PDF serían cientos de páginas que nadie abre.

Los gráficos se dibujan desde los mismos datos, no son una captura de pantalla:
una captura sale borrosa al imprimir y se arrastra el tema oscuro de la web.
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from sqlalchemy.orm import Session

from services import analitica_service

# Identidad de la plataforma (mismos valores que --brand en globals.css).
MARCA = colors.HexColor("#4F46E5")
MARCA_SUAVE = colors.HexColor("#EEF2FF")
INGRESOS = colors.HexColor("#10B981")
COSTOS = colors.HexColor("#F43F5E")
GRIS = colors.HexColor("#64748B")
GRIS_CLARO = colors.HexColor("#E2E8F0")

COLOR_TIPO = {
    "ventas": colors.HexColor("#10B981"), "nc_ventas": colors.HexColor("#6EE7B7"),
    "nd_ventas": colors.HexColor("#34D399"), "compras": colors.HexColor("#F43F5E"),
    "nc": colors.HexColor("#FDA4AF"), "nd": colors.HexColor("#FB7185"),
    "soporte": colors.HexColor("#F59E0B"), "nc_soporte": colors.HexColor("#FCD34D"),
}


def _pesos(n: float) -> str:
    """$ 1.234.567 — separador de miles con punto, como se usa en Colombia."""
    signo = "-" if n < 0 else ""
    return f"{signo}$ {abs(round(n)):,}".replace(",", ".")


def _corto(n: float) -> str:
    """Para los ejes del gráfico, donde la cifra completa no cabe."""
    a = abs(n)
    s = "-" if n < 0 else ""
    if a >= 1_000_000_000:
        return f"{s}{a / 1_000_000_000:.1f}MM"
    if a >= 1_000_000:
        return f"{s}{round(a / 1_000_000)}M"
    if a >= 1_000:
        return f"{s}{round(a / 1_000)}k"
    return f"{s}{round(a)}"


def _mes_legible(iso: str) -> str:
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    y, m = iso.split("-")
    return f"{meses[int(m) - 1]}\n{y[2:]}"


def _marca_de_agua(canvas, doc):
    """Marca de agua y pie, en cada página."""
    canvas.saveState()

    canvas.setFont("Helvetica-Bold", 68)
    canvas.setFillColor(colors.HexColor("#4F46E5"))
    canvas.setFillAlpha(0.05)
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(38)
    canvas.drawCentredString(0, 0, "CIOLIX")
    canvas.restoreState()

    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRIS)
    canvas.drawString(18 * mm, 12 * mm, "Generado por Ciolix a partir de los documentos reportados por la DIAN")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {canvas.getPageNumber()}")
    canvas.setStrokeColor(GRIS_CLARO)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.restoreState()


def _grafico_meses(serie: list[dict], ancho: float) -> Drawing:
    """Ingresos contra costos y gastos, mes a mes."""
    d = Drawing(ancho, 170)
    if not serie:
        d.add(String(ancho / 2, 80, "Sin movimientos en el periodo",
                     fontSize=9, fillColor=GRIS, textAnchor="middle"))
        return d

    # Con muchos meses las barras se vuelven ilegibles; se muestran los últimos 12.
    serie = serie[-12:]
    grafico = VerticalBarChart()
    grafico.x, grafico.y = 42, 34
    grafico.width, grafico.height = ancho - 60, 118
    grafico.data = [
        [m["ingresos"] for m in serie],
        [m["costos_gastos"] for m in serie],
    ]
    grafico.categoryAxis.categoryNames = [_mes_legible(m["mes"]) for m in serie]
    grafico.categoryAxis.labels.fontSize = 6
    grafico.categoryAxis.labels.dy = -10
    grafico.valueAxis.labelTextFormat = lambda v: _corto(v)
    grafico.valueAxis.labels.fontSize = 6
    grafico.bars[0].fillColor = INGRESOS
    grafico.bars[1].fillColor = COSTOS
    grafico.bars.strokeWidth = 0
    grafico.groupSpacing = 6
    grafico.barSpacing = 1
    d.add(grafico)

    # Leyenda propia: la de reportlab es más rígida de posicionar.
    for i, (etiqueta, color) in enumerate([("Ingresos", INGRESOS), ("Costos y gastos", COSTOS)]):
        x = 42 + i * 110
        d.add(String(x + 12, 8, etiqueta, fontSize=7, fillColor=GRIS))
        from reportlab.graphics.shapes import Rect
        d.add(Rect(x, 6, 8, 8, fillColor=color, strokeColor=None))
    return d


def _grafico_tipos(por_tipo: list[dict], ancho: float) -> Drawing:
    """Cuántos documentos de cada tipo."""
    d = Drawing(ancho, 170)
    if not por_tipo:
        return d
    torta = Pie()
    torta.x, torta.y = 20, 26
    torta.width = torta.height = 118
    torta.data = [t["documentos"] for t in por_tipo]
    torta.labels = [str(t["documentos"]) for t in por_tipo]
    torta.slices.strokeWidth = 0.5
    torta.slices.strokeColor = colors.white
    torta.slices.fontSize = 7
    torta.slices.labelRadius = 0.7
    for i, t in enumerate(por_tipo):
        torta.slices[i].fillColor = COLOR_TIPO.get(t["tipo"], GRIS)
    d.add(torta)

    from reportlab.graphics.shapes import Rect
    for i, t in enumerate(por_tipo):
        y = 140 - i * 13
        d.add(Rect(152, y, 8, 8, fillColor=COLOR_TIPO.get(t["tipo"], GRIS), strokeColor=None))
        d.add(String(165, y + 1, f"{t['label']} ({t['documentos']})", fontSize=7, fillColor=GRIS))
    return d


def generar_pdf(
    db: Session, *, empresa_ids: list[int], desde: date, hasta: date, nombre_empresa: str,
) -> BytesIO:
    datos = analitica_service.resumen(db, empresa_ids=empresa_ids, desde=desde, hasta=hasta)
    k = datos["kpis"]

    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
        title="Informe de costos, gastos e ingresos", author="Ciolix",
        subject=f"{nombre_empresa} · {desde.isoformat()} a {hasta.isoformat()}",
    )
    marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="cuerpo")
    doc.addPageTemplates([PageTemplate(id="ciolix", frames=[marco], onPage=_marca_de_agua)])

    base = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=base["Title"], fontSize=22, textColor=MARCA,
                            alignment=0, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=9.5, textColor=GRIS, spaceAfter=1)
    seccion = ParagraphStyle("seccion", parent=base["Heading2"], fontSize=11.5,
                             textColor=MARCA, spaceBefore=14, spaceAfter=6)
    nota = ParagraphStyle("nota", parent=base["Normal"], fontSize=7.5, textColor=GRIS, leading=11)
    kpi_lbl = ParagraphStyle("kpilbl", parent=base["Normal"], fontSize=7.5,
                             textColor=GRIS, alignment=TA_CENTER)

    hist = []
    hist.append(Paragraph("Ciolix", titulo))
    hist.append(Paragraph("Informe de costos, gastos e ingresos", sub))
    hist.append(Paragraph(f"<b>{nombre_empresa}</b>", sub))
    hist.append(Paragraph(
        f"Periodo {desde.strftime('%d/%m/%Y')} a {hasta.strftime('%d/%m/%Y')} · por fecha de emisión", sub))
    hist.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", sub))
    hist.append(Spacer(1, 12))

    # ── KPIs ────────────────────────────────────────────────────────────────
    def celda_kpi(label, valor, color):
        # El marcado de reportlab exige el '#': sin él rechaza el color.
        hex_color = f"#{color.hexval()[2:]}"
        return [Paragraph(label, kpi_lbl),
                Paragraph(f'<font size="14" color="{hex_color}"><b>{valor}</b></font>', kpi_lbl)]

    kpis = Table(
        list(zip(*[
            celda_kpi("INGRESOS", _pesos(k["ingresos"]), INGRESOS),
            celda_kpi("COSTOS Y GASTOS", _pesos(k["costos_gastos"]), COSTOS),
            celda_kpi("RESULTADO", _pesos(k["resultado"]), MARCA),
            celda_kpi("DOCUMENTOS", f'{k["documentos"]:,}'.replace(",", "."), GRIS),
        ])),
        colWidths=[doc.width / 4] * 4,
    )
    kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MARCA_SUAVE),
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS_CLARO),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    hist.append(kpis)

    # ── Gráficos ────────────────────────────────────────────────────────────
    hist.append(Paragraph("Evolución mensual", seccion))
    hist.append(_grafico_meses(datos["serie_mensual"], doc.width))

    hist.append(Paragraph("Documentos por tipo", seccion))
    hist.append(_grafico_tipos(datos["por_tipo"], doc.width))

    # ── Tabla por tipo ──────────────────────────────────────────────────────
    hist.append(Paragraph("Detalle por tipo de documento", seccion))
    filas = [["Documento", "Naturaleza", "Efecto", "Cantidad", "Valor"]]
    for t in datos["por_tipo"]:
        filas.append([
            t["label"],
            "Ingresos" if t["naturaleza"] == "ingresos" else "Costos y gastos",
            "Suma" if t["signo"] == 1 else "Resta",
            f'{t["documentos"]:,}'.replace(",", "."),
            _pesos(t["monto"] * t["signo"]),
        ])
    hist.append(_tabla(filas, [doc.width * x for x in (0.30, 0.22, 0.13, 0.15, 0.20)]))

    # ── Terceros ────────────────────────────────────────────────────────────
    if datos["por_tercero"]:
        hist.append(Paragraph("Terceros con mayor peso en costos y gastos", seccion))
        filas = [["NIT", "Nombre", "Documentos", "Valor"]]
        for t in datos["por_tercero"]:
            filas.append([t["nit"], t["nombre"][:46],
                          f'{t["documentos"]:,}'.replace(",", "."), _pesos(t["monto"])])
        hist.append(_tabla(filas, [doc.width * x for x in (0.18, 0.47, 0.15, 0.20)]))

    hist.append(Spacer(1, 14))
    hist.append(Paragraph(
        "Las cifras salen de lo que la DIAN reporta para esta empresa, se haya causado o no. "
        "Las notas crédito restan y las notas débito suman. Se usa la base gravable (sin IVA), "
        "porque el IVA descontable no es un costo sino un saldo a favor. "
        "El detalle documento por documento está en la versión en Excel de este informe.", nota))

    doc.build(hist)
    buffer.seek(0)
    return buffer


def _tabla(filas: list[list[str]], anchos: list[float]) -> Table:
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), MARCA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (-2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t
