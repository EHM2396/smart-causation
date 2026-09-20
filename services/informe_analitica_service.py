"""
Informe de analítica en Excel, para enviar fuera de Ciolix.

Lleva más detalle del que cabe en pantalla: además del resumen, va el listado
completo de documentos con su base, su IVA y su total, que es lo que un contador
necesita para revisar o cruzar contra otra fuente.

Cada hoja dice de qué empresa y de qué periodo habla, y de dónde salieron las
cifras. Un archivo que se envía por correo se lee lejos de la aplicación, sin
nadie que pueda explicar el contexto.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.auth import Empresa
from db.models.contabilidad import DocumentoDian
from services import analitica_service

# Identidad de la plataforma (mismos valores que --brand en globals.css).
MARCA = "#4F46E5"
MARCA_SUAVE = "#EEF2FF"
INGRESOS = "#10B981"
COSTOS = "#F43F5E"
GRIS = "#64748B"


def _formatos(wb):
    return {
        "titulo": wb.add_format({
            "bold": True, "font_size": 18, "font_color": MARCA, "valign": "vcenter",
        }),
        "subtitulo": wb.add_format({"font_size": 10, "font_color": GRIS}),
        "seccion": wb.add_format({
            "bold": True, "font_size": 11, "font_color": "#FFFFFF", "bg_color": MARCA,
            "align": "left", "valign": "vcenter", "border": 1, "border_color": MARCA,
        }),
        "encabezado": wb.add_format({
            "bold": True, "font_size": 10, "font_color": MARCA, "bg_color": MARCA_SUAVE,
            "border": 1, "border_color": "#C7D2FE", "valign": "vcenter", "text_wrap": True,
        }),
        "texto": wb.add_format({"font_size": 10, "valign": "top"}),
        "fecha": wb.add_format({"font_size": 10, "num_format": "yyyy-mm-dd"}),
        "dinero": wb.add_format({"font_size": 10, "num_format": "$ #,##0"}),
        "dinero_fuerte": wb.add_format({"bold": True, "font_size": 11, "num_format": "$ #,##0"}),
        "entero": wb.add_format({"font_size": 10, "num_format": "#,##0"}),
        "kpi_titulo": wb.add_format({
            "bold": True, "font_size": 9, "font_color": GRIS, "align": "center",
        }),
        "kpi_ingresos": wb.add_format({
            "bold": True, "font_size": 14, "font_color": INGRESOS,
            "num_format": "$ #,##0", "align": "center",
        }),
        "kpi_costos": wb.add_format({
            "bold": True, "font_size": 14, "font_color": COSTOS,
            "num_format": "$ #,##0", "align": "center",
        }),
        "kpi_resultado": wb.add_format({
            "bold": True, "font_size": 14, "font_color": MARCA,
            "num_format": "$ #,##0", "align": "center",
        }),
        "pie": wb.add_format({"font_size": 8, "font_color": GRIS, "italic": True}),
    }


def _hoja_resumen(wb, fmt, *, datos: dict, nombre_empresa: str, desde: date, hasta: date) -> None:
    ws = wb.add_worksheet("Resumen")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 34)
    ws.set_column("B:E", 18)

    ws.set_row(0, 30)
    ws.write("A1", "Ciolix", fmt["titulo"])
    ws.write("A2", "Informe de costos, gastos e ingresos", fmt["subtitulo"])
    ws.write("A3", nombre_empresa, fmt["subtitulo"])
    ws.write("A4", f"Periodo {desde.isoformat()} a {hasta.isoformat()} (por fecha de emisión)", fmt["subtitulo"])
    ws.write("A5", f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", fmt["subtitulo"])

    k = datos["kpis"]
    ws.merge_range("A7:E7", "Resultado del periodo", fmt["seccion"])
    for col, (titulo, valor, estilo) in enumerate([
        ("INGRESOS", k["ingresos"], "kpi_ingresos"),
        ("COSTOS Y GASTOS", k["costos_gastos"], "kpi_costos"),
        ("RESULTADO", k["resultado"], "kpi_resultado"),
        ("DOCUMENTOS", k["documentos"], "kpi_titulo"),
    ]):
        ws.write(8, col, titulo, fmt["kpi_titulo"])
        if titulo == "DOCUMENTOS":
            ws.write_number(9, col, valor, fmt["entero"])
        else:
            ws.write_number(9, col, valor, fmt[estilo])

    fila = 12
    ws.merge_range(fila, 0, fila, 4, "Por tipo de documento", fmt["seccion"])
    fila += 1
    for col, titulo in enumerate(["Documento", "Naturaleza", "Efecto", "Cantidad", "Valor"]):
        ws.write(fila, col, titulo, fmt["encabezado"])
    fila += 1
    for t in datos["por_tipo"]:
        ws.write(fila, 0, t["label"], fmt["texto"])
        ws.write(fila, 1, "Ingresos" if t["naturaleza"] == "ingresos" else "Costos y gastos", fmt["texto"])
        ws.write(fila, 2, "Suma" if t["signo"] == 1 else "Resta", fmt["texto"])
        ws.write_number(fila, 3, t["documentos"], fmt["entero"])
        ws.write_number(fila, 4, t["monto"] * t["signo"], fmt["dinero"])
        fila += 1

    fila += 2
    ws.merge_range(fila, 0, fila, 4, "Mes a mes", fmt["seccion"])
    fila += 1
    for col, titulo in enumerate(["Mes", "Ingresos", "Costos y gastos", "Resultado"]):
        ws.write(fila, col, titulo, fmt["encabezado"])
    fila += 1
    for m in datos["serie_mensual"]:
        ws.write(fila, 0, m["mes"], fmt["texto"])
        ws.write_number(fila, 1, m["ingresos"], fmt["dinero"])
        ws.write_number(fila, 2, m["costos_gastos"], fmt["dinero"])
        ws.write_number(fila, 3, m["resultado"], fmt["dinero_fuerte"])
        fila += 1

    fila += 2
    ws.merge_range(fila, 0, fila, 4, "Terceros con mayor peso en costos y gastos", fmt["seccion"])
    fila += 1
    for col, titulo in enumerate(["NIT", "Nombre", "Documentos", "Valor"]):
        ws.write(fila, col, titulo, fmt["encabezado"])
    fila += 1
    for t in datos["por_tercero"]:
        ws.write(fila, 0, t["nit"], fmt["texto"])
        ws.write(fila, 1, t["nombre"], fmt["texto"])
        ws.write_number(fila, 2, t["documentos"], fmt["entero"])
        ws.write_number(fila, 3, t["monto"], fmt["dinero"])
        fila += 1

    fila += 2
    ws.merge_range(
        fila, 0, fila, 4,
        "Las cifras salen de lo que la DIAN reporta para esta empresa, se haya causado o no. "
        "Las notas crédito restan y las débito suman. Se usa la base gravable (sin IVA), "
        "porque el IVA descontable no es un costo sino un saldo a favor.",
        fmt["pie"],
    )


def _hoja_documentos(wb, fmt, db: Session, *, empresa_ids: list[int], desde: date, hasta: date) -> None:
    """Detalle documento por documento: lo que no cabe en la pantalla."""
    ws = wb.add_worksheet("Documentos")
    ws.hide_gridlines(2)
    ws.freeze_panes(1, 0)
    anchos = [12, 26, 16, 14, 34, 16, 16, 16]
    for i, a in enumerate(anchos):
        ws.set_column(i, i, a)

    columnas = ["Fecha", "Documento", "Número", "NIT", "Tercero", "Base (sin IVA)", "IVA", "Total"]
    for col, titulo in enumerate(columnas):
        ws.write(0, col, titulo, fmt["encabezado"])

    filas = db.execute(
        select(DocumentoDian)
        .where(
            DocumentoDian.empresa_id.in_(empresa_ids),
            DocumentoDian.fecha_emision >= desde,
            DocumentoDian.fecha_emision <= hasta,
        )
        .order_by(DocumentoDian.fecha_emision.desc(), DocumentoDian.numero)
    ).scalars().all()

    for i, d in enumerate(filas, start=1):
        base = float(d.base_gravable or 0)
        total = float(d.total or 0)
        signo = analitica_service.SIGNO.get(d.tipo, 1)
        ws.write(i, 0, d.fecha_emision, fmt["fecha"])
        ws.write(i, 1, analitica_service.ETIQUETA.get(d.tipo, d.tipo), fmt["texto"])
        ws.write(i, 2, d.numero, fmt["texto"])
        ws.write(i, 3, d.nit_contraparte or "", fmt["texto"])
        ws.write(i, 4, d.razon_social or "", fmt["texto"])
        # Con el signo del documento: una nota crédito se lee en negativo, que es
        # lo que de verdad le hace al total.
        ws.write_number(i, 5, base * signo, fmt["dinero"])
        ws.write_number(i, 6, (total - base) * signo, fmt["dinero"])
        ws.write_number(i, 7, total * signo, fmt["dinero"])

    if filas:
        ws.autofilter(0, 0, len(filas), len(columnas) - 1)


def _hoja_items(wb, fmt, db: Session, *, empresa_ids: list[int], desde: date, hasta: date) -> None:
    """Un renglón por ítem, con su tarifa de IVA: la base del análisis tributario."""
    ws = wb.add_worksheet("Items")
    ws.hide_gridlines(2)
    ws.freeze_panes(1, 0)
    for i, a in enumerate([12, 16, 34, 52, 10, 16]):
        ws.set_column(i, i, a)

    for col, titulo in enumerate(["Fecha", "Número", "Tercero", "Concepto", "Tarifa IVA", "Base"]):
        ws.write(0, col, titulo, fmt["encabezado"])

    filas = db.execute(
        select(DocumentoDian)
        .where(
            DocumentoDian.empresa_id.in_(empresa_ids),
            DocumentoDian.fecha_emision >= desde,
            DocumentoDian.fecha_emision <= hasta,
        )
        .order_by(DocumentoDian.fecha_emision.desc())
    ).scalars().all()

    pct = wb.add_format({"font_size": 10, "num_format": '0"%"'})
    r = 1
    for d in filas:
        try:
            items = json.loads(d.items_json or "[]")
        except ValueError:
            continue
        for it in items:
            ws.write(r, 0, d.fecha_emision, fmt["fecha"])
            ws.write(r, 1, d.numero, fmt["texto"])
            ws.write(r, 2, d.razon_social or "", fmt["texto"])
            ws.write(r, 3, str(it.get("descripcion") or ""), fmt["texto"])
            ws.write_number(r, 4, float(it.get("porcentaje") or 0), pct)
            ws.write_number(r, 5, float(it.get("base") or 0), fmt["dinero"])
            r += 1

    if r > 1:
        ws.autofilter(0, 0, r - 1, 5)


def generar_xlsx(
    db: Session, *, empresa_ids: list[int], desde: date, hasta: date, nombre_empresa: str,
) -> BytesIO:
    import xlsxwriter

    datos = analitica_service.resumen(db, empresa_ids=empresa_ids, desde=desde, hasta=hasta)

    buffer = BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True, "default_date_format": "yyyy-mm-dd"})
    wb.set_properties({
        "title": "Informe de costos, gastos e ingresos",
        "company": "Ciolix",
        "comments": "Generado por Ciolix a partir de los documentos reportados por la DIAN.",
    })
    fmt = _formatos(wb)

    _hoja_resumen(wb, fmt, datos=datos, nombre_empresa=nombre_empresa, desde=desde, hasta=hasta)
    _hoja_documentos(wb, fmt, db, empresa_ids=empresa_ids, desde=desde, hasta=hasta)
    _hoja_items(wb, fmt, db, empresa_ids=empresa_ids, desde=desde, hasta=hasta)

    wb.close()
    buffer.seek(0)
    return buffer
