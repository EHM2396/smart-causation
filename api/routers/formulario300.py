"""
Router: /formulario-300 – clasificación tributaria de las operaciones a tarifa
0%, previo al reporte del Formulario 300.

Por ahora es SOLO para el administrador de la cuenta (Dayana, en el caso de
Salamanca): es la pantalla donde se toman decisiones de clasificación
tributaria compartidas por toda la firma, y la restricción evita que un
causador clasifique algo sin que quien lleva impuestos lo haya visto. Abrirlo
a causadores más adelante es cambiar una dependencia, no rehacer el módulo.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from db.models.auth import CuentaCliente, Empresa, Usuario
from db.models.tributario import IVA_DESCONTABLE_ESTADOS, TIPOS_ITEM, TRATAMIENTOS
from db.session import get_db
from services import formulario_300_service as f300

router = APIRouter(prefix="/formulario-300", tags=["Formulario 300"])

DB = Annotated[Session, Depends(get_db)]


def require_org_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if current_user.rol not in ("org_admin", "admin"):
        raise HTTPException(status_code=403, detail="Requiere permisos de administrador de la cuenta")
    return current_user


OrgAdmin = Annotated[Usuario, Depends(require_org_admin)]


def _cuenta_de(db: Session, user: Usuario) -> CuentaCliente:
    if not user.cuenta_id:
        raise HTTPException(status_code=400, detail="Tu usuario no está asociado a una cuenta")
    cuenta = db.get(CuentaCliente, user.cuenta_id)
    if cuenta is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return cuenta


def _empresas_de_cuenta(db: Session, cuenta_id: int) -> list[int]:
    return list(db.scalars(
        select(Empresa.id).where(Empresa.cuenta_id == cuenta_id, Empresa.activa.is_(True))
    ).all())


def _parse_rango(desde: str | None, hasta: str | None) -> tuple[date, date]:
    hoy = date.today()
    try:
        d = date.fromisoformat(desde) if desde else date(hoy.year, 1, 1)
    except ValueError:
        d = date(hoy.year, 1, 1)
    try:
        h = date.fromisoformat(hasta) if hasta else hoy
    except ValueError:
        h = hoy
    if h < d:
        d, h = h, d
    return d, h


@router.get("/proveedores")
def proveedores(
    db: DB,
    admin: OrgAdmin,
    desde: str | None = None,
    hasta: str | None = None,
    empresa_id: int | None = None,
    tarifa: float = 0.0,
    todas_tarifas: bool = False,
    origen: str = "compras",
):
    """Proveedores con operaciones a la tarifa dada, con su concepto
    predominante y los secundarios, cada uno con su clasificación actual.

    `origen` separa la pantalla en dos flujos —"ventas" o "compras"— que nunca
    se mezclan: en ventas exento y excluido siempre quedan separados, en
    compras se agrupan en la presentación principal.

    `todas_tarifas` ignora `tarifa` y trae conceptos de cualquier tarifa —
    hace falta para clasificar IVA descontable (Fase 2), que aplica sobre
    todo a los ítems gravados (5%/19%), no a los de tarifa 0%."""
    if origen not in ("ventas", "compras"):
        raise HTTPException(status_code=400, detail="origen debe ser 'ventas' o 'compras'")

    cuenta = _cuenta_de(db, admin)
    d, h = _parse_rango(desde, hasta)
    empresas = _empresas_de_cuenta(db, cuenta.id)

    if empresa_id is not None:
        if empresa_id not in empresas:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        empresas = [empresa_id]

    if not empresas:
        return {"periodo": {"desde": d.isoformat(), "hasta": h.isoformat()}, "proveedores": []}

    resultado = f300.resumen_por_proveedor(
        db, empresa_ids=empresas, desde=d, hasta=h, tarifa=tarifa,
        todas_tarifas=todas_tarifas, origen=origen, cuenta_id=cuenta.id,
    )

    def _concepto(c) -> dict:
        return {
            "concepto": c.concepto,
            "nit_proveedor": c.nit_proveedor,
            "referencia": c.referencia,
            "base_acumulada": c.base_acumulada,
            "documentos": c.documentos,
            "participacion": c.participacion,
            "tratamiento": c.clasificacion.tratamiento,
            "estado": c.clasificacion.estado,
            "origen": c.clasificacion.origen,
            "requiere_revision": c.clasificacion.requiere_revision,
            "es_excepcion": c.clasificacion.es_excepcion,
            "articulo_et": c.clasificacion.articulo_et,
            "norma": c.clasificacion.norma,
            "tipo_item": c.clasificacion.tipo_item,
            "tipo_item_confirmado": c.clasificacion.tipo_item_confirmado,
            "iva_descontable": c.clasificacion.iva_descontable,
            "iva_descontable_confirmado": c.clasificacion.iva_descontable_confirmado,
        }

    return {
        "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
        "tarifa": tarifa,
        "todas_tarifas": todas_tarifas,
        "origen": origen,
        "proveedores": [
            {
                "nit": p.nit,
                "razon_social": p.razon_social,
                "base_total": p.base_total,
                "documentos": p.documentos,
                "pendientes": p.pendientes,
                "tipos_documento": p.tipos_documento,
                "predominante": _concepto(p.predominante),
                "secundarios": [_concepto(c) for c in p.secundarios],
            }
            for p in resultado
        ],
    }


@router.get("/reporte")
def reporte(
    db: DB, admin: OrgAdmin,
    desde: str | None = None, hasta: str | None = None,
    empresa_id: int | None = None,
):
    """Resumen consolidado por categoría tributaria para el período dado.
    Incluye ventas (base + IVA generado) y compras (base + IVA facturado +
    IVA descontable), listo para construir la declaración del Formulario 300."""
    cuenta = _cuenta_de(db, admin)
    d, h = _parse_rango(desde, hasta)
    empresas = _empresas_de_cuenta(db, cuenta.id)
    if empresa_id is not None:
        if empresa_id not in empresas:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        empresas = [empresa_id]
    return f300.reporte_resumen(db, empresa_ids=empresas, desde=d, hasta=h, cuenta_id=cuenta.id)


@router.get("/reporte/excel")
def reporte_excel(
    db: DB, admin: OrgAdmin,
    desde: str | None = None, hasta: str | None = None,
    empresa_id: int | None = None,
):
    """Descarga el reporte como archivo Excel (.xlsx)."""
    cuenta = _cuenta_de(db, admin)
    d, h = _parse_rango(desde, hasta)
    empresas = _empresas_de_cuenta(db, cuenta.id)
    nombre_empresa = "Todas las empresas"
    if empresa_id is not None:
        if empresa_id not in empresas:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        empresas = [empresa_id]
        emp = db.get(Empresa, empresa_id)
        if emp:
            nombre_empresa = emp.nombre

    datos = f300.reporte_resumen(db, empresa_ids=empresas, desde=d, hasta=h, cuenta_id=cuenta.id)
    buf = _generar_excel(datos, nombre_empresa)
    filename = f"formulario300_{d}_{h}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reporte/pdf")
def reporte_pdf(
    db: DB, admin: OrgAdmin,
    desde: str | None = None, hasta: str | None = None,
    empresa_id: int | None = None,
):
    """Descarga el reporte como archivo PDF."""
    cuenta = _cuenta_de(db, admin)
    d, h = _parse_rango(desde, hasta)
    empresas = _empresas_de_cuenta(db, cuenta.id)
    nombre_empresa = "Todas las empresas"
    if empresa_id is not None:
        if empresa_id not in empresas:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        empresas = [empresa_id]
        emp = db.get(Empresa, empresa_id)
        if emp:
            nombre_empresa = emp.nombre

    datos = f300.reporte_resumen(db, empresa_ids=empresas, desde=d, hasta=h, cuenta_id=cuenta.id)
    buf = _generar_pdf(datos, nombre_empresa)
    filename = f"formulario300_{d}_{h}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Generación de exportables ─────────────────────────────────────────────────

def _fmt_cop(n: float) -> str:
    return f"${n:,.0f}".replace(",", ".")


def _generar_excel(datos: dict, nombre_empresa: str) -> io.BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, numbers
    from openpyxl.utils import get_column_letter

    GRIS = "F2F2F2"
    AZUL = "1E3A5F"
    AZUL_CLARO = "D6E4F0"
    VERDE = "E8F5E9"

    wb = Workbook()
    ws = wb.active
    ws.title = "Formulario 300"

    def _bold(cell, size=11): cell.font = Font(bold=True, size=size)
    def _fill(cell, color): cell.fill = PatternFill("solid", fgColor=color)
    def _center(cell): cell.alignment = Alignment(horizontal="center", vertical="center")

    # Encabezado
    ws.merge_cells("A1:F1")
    ws["A1"] = "REPORTE FORMULARIO 300 — CLASIFICACIÓN TRIBUTARIA DE IVA"
    ws["A1"].font = Font(bold=True, size=13, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=AZUL)
    _center(ws["A1"])

    ws.merge_cells("A2:F2")
    ws["A2"] = f"{nombre_empresa}   ·   {datos['periodo']['desde']}  al  {datos['periodo']['hasta']}"
    ws["A2"].font = Font(italic=True, size=10)
    _center(ws["A2"])

    fila = 4

    def _seccion(titulo: str, cols: list[str], filas_datos: list[list], totales: list):
        nonlocal fila
        ws.merge_cells(f"A{fila}:F{fila}")
        ws[f"A{fila}"] = titulo
        ws[f"A{fila}"].font = Font(bold=True, size=11, color="FFFFFF")
        ws[f"A{fila}"].fill = PatternFill("solid", fgColor=AZUL)
        _center(ws[f"A{fila}"])
        fila += 1

        for ci, col in enumerate(cols, 1):
            cell = ws.cell(row=fila, column=ci, value=col)
            _bold(cell, 10)
            _fill(cell, AZUL_CLARO)
            _center(cell)
        fila += 1

        for i, row_data in enumerate(filas_datos):
            color = GRIS if i % 2 == 0 else "FFFFFF"
            for ci, val in enumerate(row_data, 1):
                cell = ws.cell(row=fila, column=ci, value=val)
                if isinstance(val, (int, float)) and ci > 1:
                    cell.number_format = "#,##0"
                    cell.alignment = Alignment(horizontal="right")
                _fill(cell, color)
            fila += 1

        # Fila TOTAL
        for ci, val in enumerate(totales, 1):
            cell = ws.cell(row=fila, column=ci, value=val)
            _bold(cell, 10)
            _fill(cell, VERDE)
            if isinstance(val, (int, float)) and ci > 1:
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right")
        fila += 2

    cats = f300.CATS_LABEL

    # --- VENTAS ---
    v = datos["ventas"]
    filas_v = [
        [cats[cat], v[cat]["base"], v[cat]["iva"]]
        for cat in f300._CATS_REPORTE
        if v[cat]["base"] != 0 or v[cat]["iva"] != 0
    ]
    total_base_v = sum(v[cat]["base"] for cat in f300._CATS_REPORTE)
    total_iva_v = datos["totales"]["iva_generado"]
    _seccion("VENTAS E INGRESOS", ["Tratamiento", "Base gravable (COP)", "IVA generado (COP)"],
             filas_v, ["TOTAL", total_base_v, total_iva_v])

    # --- COMPRAS ---
    c = datos["compras"]
    filas_c = [
        [cats[cat], c[cat]["base"], c[cat]["iva_facturado"], c[cat]["iva_descontable"]]
        for cat in f300._CATS_REPORTE
        if c[cat]["base"] != 0 or c[cat]["iva_facturado"] != 0
    ]
    total_base_c = sum(c[cat]["base"] for cat in f300._CATS_REPORTE)
    _seccion(
        "COMPRAS Y COSTOS",
        ["Tratamiento", "Base (COP)", "IVA facturado (COP)", "IVA descontable (COP)"],
        filas_c,
        ["TOTAL", total_base_c, datos["totales"]["iva_descontable"], datos["totales"]["iva_descontable"]],
    )

    # --- BALANCE ---
    ws.merge_cells(f"A{fila}:F{fila}")
    ws[f"A{fila}"] = "BALANCE ANALÍTICO DE IVA"
    ws[f"A{fila}"].font = Font(bold=True, size=11, color="FFFFFF")
    ws[f"A{fila}"].fill = PatternFill("solid", fgColor=AZUL)
    _center(ws[f"A{fila}"])
    fila += 1

    for label, key in [("IVA generado (ventas)", "iva_generado"),
                        ("IVA descontable (compras)", "iva_descontable"),
                        ("Balance analítico de IVA", "balance_analitico_iva")]:
        ws.cell(row=fila, column=1, value=label).font = Font(bold=(key == "balance_analitico_iva"), size=10)
        cell = ws.cell(row=fila, column=2, value=datos["totales"][key])
        cell.number_format = "#,##0"
        cell.alignment = Alignment(horizontal="right")
        if key == "balance_analitico_iva":
            _bold(cell, 10)
            _fill(ws.cell(row=fila, column=1), VERDE)
            _fill(cell, VERDE)
        fila += 1

    if datos["conceptos_pendientes"] > 0:
        fila += 1
        ws.merge_cells(f"A{fila}:F{fila}")
        ws[f"A{fila}"] = (
            f"⚠ {datos['conceptos_pendientes']} concepto(s) aún sin clasificar — "
            "el reporte puede estar incompleto."
        )
        ws[f"A{fila}"].font = Font(italic=True, size=9, color="D97706")

    # Ancho de columnas
    ws.column_dimensions["A"].width = 30
    for col in ["B", "C", "D", "E", "F"]:
        ws.column_dimensions[col].width = 22

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _generar_pdf(datos: dict, nombre_empresa: str) -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    AZUL = colors.HexColor("#1E3A5F")
    AZUL_CLARO = colors.HexColor("#D6E4F0")
    GRIS = colors.HexColor("#F2F2F2")
    VERDE = colors.HexColor("#E8F5E9")
    NARANJA = colors.HexColor("#D97706")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("titulo", parent=styles["Heading1"],
                                  fontSize=14, textColor=colors.white,
                                  spaceAfter=4, alignment=1)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"],
                               fontSize=9, textColor=colors.gray,
                               spaceAfter=2, alignment=1)
    seccion_style = ParagraphStyle("sec", parent=styles["Heading2"],
                                   fontSize=11, textColor=colors.white, alignment=0)
    nota_style = ParagraphStyle("nota", parent=styles["Normal"],
                                fontSize=8, textColor=NARANJA)

    def _cop(n: float) -> str:
        return f"${n:,.0f}".replace(",", ".")

    story = []
    cats = f300.CATS_LABEL

    def _tabla_seccion(titulo: str, encabezados: list, filas: list, totales: list):
        story.append(Spacer(1, 0.3*cm))
        data = [encabezados] + filas + [totales]
        n_cols = len(encabezados)
        col_w = [8*cm] + [4.5*cm] * (n_cols - 1)

        ts = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_CLARO),
            ("TEXTCOLOR", (0, 0), (-1, 0), AZUL),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [GRIS, colors.white]),
            ("BACKGROUND", (0, -1), (-1, -1), VERDE),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])

        p_titulo = Paragraph(titulo, ParagraphStyle("h", fontName="Helvetica-Bold",
                                                    fontSize=10, textColor=colors.white))
        header_table = Table([[p_titulo]], colWidths=[sum(col_w)])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), AZUL),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(header_table)
        t = Table(data, colWidths=col_w)
        t.setStyle(ts)
        story.append(t)

    # Título
    p_titulo = Paragraph("REPORTE FORMULARIO 300 — CLASIFICACIÓN TRIBUTARIA DE IVA", titulo_style)
    tbl_titulo = Table([[p_titulo]], colWidths=[doc.width])
    tbl_titulo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl_titulo)
    story.append(Paragraph(
        f"{nombre_empresa}   ·   {datos['periodo']['desde']}  al  {datos['periodo']['hasta']}",
        sub_style,
    ))
    story.append(Spacer(1, 0.4*cm))

    # VENTAS
    v = datos["ventas"]
    filas_v = [
        [cats[cat], _cop(v[cat]["base"]), _cop(v[cat]["iva"])]
        for cat in f300._CATS_REPORTE
        if v[cat]["base"] != 0 or v[cat]["iva"] != 0
    ]
    total_base_v = sum(v[cat]["base"] for cat in f300._CATS_REPORTE)
    _tabla_seccion(
        "VENTAS E INGRESOS",
        ["Tratamiento", "Base gravable (COP)", "IVA generado (COP)"],
        filas_v,
        ["TOTAL", _cop(total_base_v), _cop(datos["totales"]["iva_generado"])],
    )

    # COMPRAS
    c = datos["compras"]
    filas_c = [
        [cats[cat], _cop(c[cat]["base"]), _cop(c[cat]["iva_facturado"]), _cop(c[cat]["iva_descontable"])]
        for cat in f300._CATS_REPORTE
        if c[cat]["base"] != 0 or c[cat]["iva_facturado"] != 0
    ]
    total_base_c = sum(c[cat]["base"] for cat in f300._CATS_REPORTE)
    _tabla_seccion(
        "COMPRAS Y COSTOS",
        ["Tratamiento", "Base (COP)", "IVA facturado (COP)", "IVA descontable (COP)"],
        filas_c,
        ["TOTAL", _cop(total_base_c), _cop(datos["totales"]["iva_descontable"]),
         _cop(datos["totales"]["iva_descontable"])],
    )

    # BALANCE
    story.append(Spacer(1, 0.4*cm))
    bal_data = [
        ["IVA generado (ventas)", _cop(datos["totales"]["iva_generado"])],
        ["IVA descontable (compras)", _cop(datos["totales"]["iva_descontable"])],
        ["Balance analítico de IVA", _cop(datos["totales"]["balance_analitico_iva"])],
    ]
    p_bal = Paragraph("BALANCE ANALÍTICO DE IVA", ParagraphStyle(
        "hbal", fontName="Helvetica-Bold", fontSize=10, textColor=colors.white))
    th = Table([[p_bal]], colWidths=[12.5*cm])
    th.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AZUL),
                             ("TOPPADDING", (0, 0), (-1, -1), 5),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(th)
    tb = Table(bal_data, colWidths=[8*cm, 4.5*cm])
    tb.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GRIS, colors.white, VERDE]),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tb)

    if datos["conceptos_pendientes"] > 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(
            f"⚠ {datos['conceptos_pendientes']} concepto(s) aún sin clasificar — "
            "el reporte puede estar incompleto.",
            nota_style,
        ))

    doc.build(story)
    buf.seek(0)
    return buf


class ClasificarRequest(BaseModel):
    empresa_id: int
    concepto: str = Field(..., min_length=1)
    tratamiento: str
    # Con NIT: la decisión solo vale para ese proveedor (queda como excepción,
    # no se comparte). Sin NIT: es una regla general del concepto y se propone
    # también a las demás empresas de la firma.
    nit_tercero: str | None = None
    # Código/referencia del producto (si el XML la trae) — afina la memoria
    # cuando el mismo proveedor vende bienes y servicios con textos parecidos.
    referencia: str | None = None
    # bien | servicio, confirmado por el contador — opcional, es un eje
    # independiente del tratamiento de IVA.
    tipo_item: str | None = None
    # descontable | no_descontable, confirmado por el contador — opcional,
    # Fase 2. Nunca se propaga al catálogo de la firma (ver
    # validar_clasificacion).
    iva_descontable: str | None = None
    articulo_et: str | None = None
    norma: str | None = None


@router.post("/clasificar")
def clasificar_endpoint(body: ClasificarRequest, db: DB, admin: OrgAdmin):
    cuenta = _cuenta_de(db, admin)
    empresa = db.get(Empresa, body.empresa_id)
    if empresa is None or empresa.cuenta_id != cuenta.id:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if body.tratamiento not in TRATAMIENTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Tratamiento inválido. Debe ser uno de: {', '.join(TRATAMIENTOS)}",
        )
    if body.tipo_item is not None and body.tipo_item not in TIPOS_ITEM:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de ítem inválido. Debe ser uno de: {', '.join(TIPOS_ITEM)}",
        )
    if body.iva_descontable is not None and body.iva_descontable not in IVA_DESCONTABLE_ESTADOS:
        raise HTTPException(
            status_code=400,
            detail=f"IVA descontable inválido. Debe ser uno de: {', '.join(IVA_DESCONTABLE_ESTADOS)}",
        )

    fila = f300.validar_clasificacion(
        db, empresa=empresa, usuario=admin, concepto=body.concepto,
        tratamiento=body.tratamiento, nit_tercero=body.nit_tercero,
        referencia=body.referencia, tipo_item=body.tipo_item,
        iva_descontable=body.iva_descontable,
        articulo_et=body.articulo_et, norma=body.norma,
    )
    return {
        "id": fila.id, "concepto": fila.concepto, "tratamiento": fila.tratamiento,
        "estado": fila.estado, "es_excepcion": fila.es_excepcion,
        "tipo_item": fila.tipo_item, "iva_descontable": fila.iva_descontable,
    }
