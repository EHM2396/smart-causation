"""
Exportador: genera el archivo importacion_SIIGO_YYYYMMDD.xlsx respetando
exactamente la estructura de columnas de modelo_importacion.xlsx.
"""

from __future__ import annotations

import os
from datetime import date
from io import BytesIO

import pandas as pd

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
_RUTA_MODELO = os.path.join(BASE_DIR, "modelo_importacion.xlsx")

# SIIGO acepta como máximo 500 líneas por archivo de importación, incluyendo el
# encabezado → 499 filas de datos (movimientos contables). Un archivo con más
# filas es rechazado por SIIGO, por eso la causación se divide en tandas.
MAX_FILAS_ARCHIVO = 499

# Columnas exactas del modelo SIIGO (mismo orden que modelo_importacion.xlsx)
_COLUMNAS_MODELO = [
    "Tipo de comprobante",
    "Consecutivo comprobante",
    "Fecha de elaboración ",          # trailing space intencional (coincide con el archivo)
    "Sigla moneda",
    "Tasa de cambio",
    "Código cuenta contable",
    "Identificación tercero",
    "Sucursal",
    "Código producto",
    "Código de bodega",
    "Acción",
    "Cantidad producto",
    "Prefijo",
    "Consecutivo",
    "No. cuota",
    "Fecha vencimiento",
    "Código impuesto",
    "Código grupo activo fijo",
    "Código activo fijo",
    "Descripción",
    "Código centro/subcentro de costos",
    "Débito",
    "Crédito",
    "Observaciones",
    "Base gravable libro compras/ventas  ",  # trailing spaces intencionales
    "Base exenta libro compras/ventas",
    "Mes de cierre",
]


def _leer_columnas_modelo() -> list[str]:
    """Lee la primera fila del modelo para obtener el orden exacto de columnas."""
    try:
        df = pd.read_excel(_RUTA_MODELO, nrows=0, dtype=str)
        cols = [str(c) for c in df.columns if str(c).strip() not in ("nan", "")]
        return cols if cols else _COLUMNAS_MODELO
    except Exception:
        return _COLUMNAS_MODELO


def construir_movimientos(
    factura: dict,
    consecutivo: int | str,
    mapeos_confirmados: list[dict],
    tipo_comprobante: str = "12",
    centro_costo: str = "",
    es_nota_credito: bool = False,
) -> list[dict]:
    """
    Construye la lista de movimientos contables para una factura.

    Parámetros:
        factura: dict parseado por core.parser
        consecutivo: número entero del comprobante en SIIGO (ej. 23)
        mapeos_confirmados: lista de MapeoItem serializados
        tipo_comprobante: código numérico SIIGO del tipo de comprobante (ej. "12")
        centro_costo: código de centro de costo (vacío si no aplica)

    Retorna lista de filas listas para el DataFrame de exportación.
    """
    movimientos: list[dict] = []
    fecha = factura.get("fecha", "")
    nit   = str(factura.get("nit", "")).strip()
    num_factura = factura.get("numero_dian", "")
    cufe = str(factura.get("cufe", "") or "").strip()
    observaciones = f"{num_factura}-{cufe}" if cufe else num_factura

    total_debitos  = 0.0
    total_creditos = 0.0

    # Deduplicar mapeos exactos para evitar filas dobles por formatos DIAN con filas de impuesto separadas
    seen_mapeos: set[tuple] = set()
    mapeos_unicos: list[dict] = []
    for m in mapeos_confirmados:
        key = (
            str(m.get("descripcion", "")),
            round(float(m.get("base", 0) or 0), 2),
            round(float(m.get("valor_impuesto", 0) or 0), 2),
            str(m.get("cuenta_gasto", "")),
            bool(m.get("es_retencion", False)),
        )
        if key not in seen_mapeos:
            seen_mapeos.add(key)
            mapeos_unicos.append(m)

    for m in mapeos_unicos:
        base        = float(m.get("base", 0) or 0)
        val_imp     = float(m.get("valor_impuesto", 0) or 0)
        es_ret      = bool(m.get("es_retencion", False))
        cuenta_gasto = str(m.get("cuenta_gasto", "")).strip()
        cuenta_imp_d = str(m.get("cuenta_impuesto_deb", "")).strip()
        cuenta_imp_c = str(m.get("cuenta_impuesto_cre", "")).strip()
        cod_imp      = str(m.get("cod_impuesto", "")).strip()
        pct          = float(m.get("porcentaje", 0) or 0)
        desc         = str(m.get("descripcion", ""))

        # ¿El ítem está gravado con IVA? Se decide por la TARIFA (porcentaje), no
        # por el valor: un código 0% (exento) puede arrastrar un valor de IVA viejo
        # extraído del PDF, pero sigue siendo exento.
        tiene_iva = (pct > 0) and (not es_ret)

        # Fila de gasto/costo (débito). La base va a "Base gravable" si el ítem
        # tiene IVA (tarifa > 0), o a "Base exenta" si es exento/0%.
        if base and cuenta_gasto:
            movimientos.append(_fila(
                tipo_comprobante, consecutivo, fecha, nit,
                cuenta_gasto, base, None,
                desc, centro_costo, observaciones, "",
                base_gravable=base if tiene_iva else "",
                base_exenta="" if tiene_iva else base,
            ))
            total_debitos += base

        # Fila de IVA (débito) — solo si realmente hay tarifa > 0. En una nota
        # crédito es "Iva devolución en compras" (luego se invierte a crédito).
        if val_imp and cuenta_imp_d and not es_ret and pct > 0:
            desc_iva = "Iva devolucion en compras" if es_nota_credito else "Iva descontable"
            movimientos.append(_fila(
                tipo_comprobante, consecutivo, fecha, nit,
                cuenta_imp_d, val_imp, None,
                desc_iva,
                centro_costo, observaciones, cod_imp,
            ))
            total_debitos += val_imp

        # Fila de retención practicada (crédito)
        if val_imp and cuenta_imp_c and es_ret:
            movimientos.append(_fila(
                tipo_comprobante, consecutivo, fecha, nit,
                cuenta_imp_c, None, val_imp,
                desc,
                centro_costo, observaciones, cod_imp,
            ))
            total_creditos += val_imp

    # Cuenta de pago seleccionada o aprendida para el proveedor (activo/pasivo)
    cuenta_pago = str(mapeos_unicos[0].get("cuenta_pago", "")).strip() if mapeos_unicos else ""
    cuenta_pago_nombre = str(mapeos_unicos[0].get("cuenta_pago_nombre", "")).strip() if mapeos_unicos else ""
    if not cuenta_pago:
        cuenta_pago = str(factura.get("cuenta_pago", "")).strip()
        cuenta_pago_nombre = factura.get("razon_social", "")
    if not cuenta_pago:
        cuenta_pago = "220510" if factura.get("tipo_proveedor") == "natural" else "220505"
        cuenta_pago_nombre = factura.get("razon_social", "")
    neto = round(total_debitos - total_creditos, 2)
    if neto != 0:
        movimientos.append(_fila(
            tipo_comprobante, consecutivo, fecha, nit,
            cuenta_pago, None, neto,
            cuenta_pago_nombre or factura.get("razon_social", ""),
            centro_costo, observaciones, "",
        ))
        total_creditos += neto

    # Nota crédito: reversa la compra → se invierte toda la partida doble
    # (lo que iba a débito va a crédito y viceversa). Así queda balanceada y
    # contablemente correcta sin duplicar la lógica.
    if es_nota_credito:
        for m in movimientos:
            m["Débito"], m["Crédito"] = m["Crédito"], m["Débito"]

    return movimientos


def _fila(
    tipo_comp: str,
    consecutivo: int | str,
    fecha: str,
    nit: str,
    cuenta: str,
    debito: float | None,
    credito: float | None,
    descripcion: str,
    centro_costo: str,
    observaciones: str,
    cod_imp: str,
    base_gravable: float | str = "",
    base_exenta: float | str = "",
) -> dict:
    return {
        "Tipo de comprobante":               tipo_comp,
        "Consecutivo comprobante":           consecutivo,
        "Fecha de elaboración ":             fecha,
        "Sigla moneda":                      "",
        "Tasa de cambio":                    "",
        "Código cuenta contable":            cuenta,
        "Identificación tercero":            nit,
        "Sucursal":                          "",
        "Código producto":                   "",
        "Código de bodega":                  "",
        "Acción":                            "",
        "Cantidad producto":                 "",
        "Prefijo":                           "",
        "Consecutivo":                       "",
        "No. cuota":                         "",
        "Fecha vencimiento":                 "",
        "Código impuesto":                   cod_imp if cod_imp else "",
        "Código grupo activo fijo":          "",
        "Código activo fijo":                "",
        "Descripción":                       descripcion[:100],
        "Código centro/subcentro de costos": centro_costo,
        "Débito":                            round(debito, 2) if debito else "",
        "Crédito":                           round(credito, 2) if credito else "",
        "Observaciones":                     observaciones,
        "Base gravable libro compras/ventas  ": round(base_gravable, 2) if base_gravable else "",
        "Base exenta libro compras/ventas":  round(base_exenta, 2) if base_exenta else "",
        "Mes de cierre":                     "",
    }


def generar_xlsx(movimientos: list[dict]) -> BytesIO:
    """
    Genera el archivo xlsx de importación SIIGO con las columnas en el orden exacto
    del modelo_importacion.xlsx. Formato con encabezados azul oscuro.

    Retorna un BytesIO listo para descargar desde Streamlit.
    """
    columnas = _leer_columnas_modelo()
    df = pd.DataFrame(movimientos)

    # Asegurar que todas las columnas del modelo existan
    for col in columnas:
        if col not in df.columns:
            df[col] = ""

    # Mantener solo columnas del modelo en el orden correcto
    df = df[columnas]

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
        wb = writer.book
        ws = writer.sheets["Datos"]

        fmt_header = wb.add_format({
            "bold": True,
            "bg_color": "#1F4E79",
            "font_color": "#FFFFFF",
            "border": 1,
            "text_wrap": True,
            "valign": "vcenter",
        })
        fmt_money = wb.add_format({"num_format": "#,##0.00"})
        fmt_date  = wb.add_format({"num_format": "yyyy-mm-dd"})

        # Anchos por columna
        anchos = {
            "Tipo de comprobante": 18,
            "Consecutivo comprobante": 22,
            "Fecha de elaboración ": 20,
            "Código cuenta contable": 22,
            "Identificación tercero": 22,
            "Código impuesto": 16,
            "Descripción": 40,
            "Código centro/subcentro de costos": 28,
            "Débito": 18,
            "Crédito": 18,
            "Observaciones": 18,
        }

        for col_idx, col_name in enumerate(df.columns):
            # Sobreescribir el encabezado con formato azul
            ws.write(0, col_idx, col_name.strip(), fmt_header)
            ancho = anchos.get(col_name, 16)
            if col_name in ("Débito", "Crédito"):
                ws.set_column(col_idx, col_idx, ancho, fmt_money)
            else:
                ws.set_column(col_idx, col_idx, ancho)

        # Congelar la primera fila
        ws.freeze_panes(1, 0)

    buffer.seek(0)
    return buffer


def nombre_archivo_salida() -> str:
    return f"importacion_SIIGO_{date.today().strftime('%Y%m%d')}.xlsx"
