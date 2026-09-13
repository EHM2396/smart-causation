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
    es_venta: bool = False,
) -> list[dict]:
    """
    Construye la lista de movimientos contables para una factura.

    Parámetros:
        factura: dict parseado por core.parser
        consecutivo: número entero del comprobante en SIIGO (ej. 23)
        mapeos_confirmados: lista de MapeoItem serializados
        tipo_comprobante: código numérico SIIGO del tipo de comprobante (ej. "12")
        centro_costo: código de centro de costo (vacío si no aplica)
        es_nota_credito: la factura es una nota crédito (reversa la operación).
        es_venta: la operación es una VENTA (no una compra). Una venta es la
            partida de compra invertida (ingreso e IVA generado al crédito, cliente
            al débito), así que se construye igual que una compra y luego se decide
            la inversión con ``flip = es_venta XOR es_nota_credito``:
              - Compra          (F,F) → no invierte  (gasto/IVA débito, pago crédito)
              - NC compra        (F,T) → invierte
              - Venta            (T,F) → invierte     (ingreso/IVA crédito, cliente débito)
              - NC venta / devol.(T,T) → no invierte

    Retorna lista de filas listas para el DataFrame de exportación.
    """
    # Una venta es la imagen espejo de una compra; la nota crédito invierte de nuevo.
    flip = bool(es_venta) ^ bool(es_nota_credito)
    movimientos: list[dict] = []
    fecha = factura.get("fecha", "")
    nit   = str(factura.get("nit", "")).strip()
    num_factura = factura.get("numero_dian", "")
    cufe = str(factura.get("cufe", "") or "").strip()
    observaciones = f"{num_factura}-{cufe}" if cufe else num_factura

    total_debitos  = 0.0
    total_creditos = 0.0
    lineas_iva: list[dict] = []  # referencias a las filas de IVA (para ajuste de redondeo)

    # NO deduplicar los mapeos: cada ítem de la factura es una línea contable
    # independiente, aunque dos ítems sean idénticos (mismo producto, base e IVA
    # repetidos en varias líneas — algo común en facturas reales). Colapsarlos
    # dejaba IVAs por fuera y descuadraba el comprobante contra el total de la
    # factura. Las filas de "detalle de IVA" (base=0) de algunos exportes DIAN ya
    # se descartan en el parser, así que aquí no hay artefactos que filtrar.
    for m in mapeos_confirmados:
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
            if es_venta:
                desc_iva = "Iva devolucion en ventas" if es_nota_credito else "Iva generado"
            else:
                desc_iva = "Iva devolucion en compras" if es_nota_credito else "Iva descontable"
            fila_iva = _fila(
                tipo_comprobante, consecutivo, fecha, nit,
                cuenta_imp_d, val_imp, None,
                desc_iva,
                centro_costo, observaciones, cod_imp,
            )
            movimientos.append(fila_iva)
            lineas_iva.append(fila_iva)
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

        # ── Otros tributos de la línea (INC, bolsas, IBUA, ICUI, INPP, otros) ──
        # Todos se construyen como DÉBITO antes de invertir; el `flip` los deja en
        # el lado correcto según el módulo:
        #   - Compra / documento soporte: quedan al débito = MAYOR VALOR DEL GASTO
        #     (no descontables), sobre la misma cuenta de gasto del ítem.
        #   - Venta, tributo "independiente" (INC / bolsas): al invertir quedan al
        #     crédito = impuesto por pagar a la DIAN / cobro al cliente, sobre la
        #     cuenta del tributo tomada del catálogo de impuestos.
        #   - Venta, tributo "costo" (IBUA / ICUI / INPP / otros): al invertir queda
        #     al crédito sobre la cuenta de ingreso = MAYOR VALOR DEL INGRESO.
        for trib in (m.get("otros_tributos") or []):
            val_t = float(trib.get("valor", 0) or 0)
            if not val_t:
                continue
            grupo_t = str(trib.get("grupo", "costo"))
            nombre_t = str(trib.get("nombre", "Tributo"))
            cod_t = str(trib.get("cod_impuesto", "")).strip()
            if es_venta and grupo_t == "independiente":
                # Cuenta propia del tributo (catálogo). Si no está configurada, se
                # usa la de gasto/ingreso para no dejar la línea sin cuenta.
                cuenta_t = str(trib.get("cuenta", "")).strip() or cuenta_gasto
                desc_t = f"{nombre_t}{' devolucion' if es_nota_credito else ''}"
            else:
                # Mayor valor del gasto (compra/DS) o del ingreso (venta grupo costo).
                cuenta_t = cuenta_gasto
                desc_t = f"{desc} ({nombre_t})"[:100]
            if cuenta_t:
                movimientos.append(_fila(
                    tipo_comprobante, consecutivo, fecha, nit,
                    cuenta_t, val_t, None,
                    desc_t, centro_costo, observaciones, cod_t,
                ))
                total_debitos += val_t

    # ── Descuentos / recargos GLOBALES (a nivel de factura) ──
    # Cuenta representativa de gasto/ingreso: la primera cuenta de gasto usada.
    cuenta_gasto_repr = next(
        (str(m.get("cuenta_gasto", "")).strip() for m in mapeos_confirmados
         if str(m.get("cuenta_gasto", "")).strip()),
        "",
    )
    descuento_global = round(float(factura.get("descuento_global", 0) or 0), 2)
    recargo_global   = round(float(factura.get("recargo_global", 0) or 0), 2)
    if descuento_global and cuenta_gasto_repr:
        # Crédito sobre la cuenta de gasto/ingreso: menor valor del gasto (compra) y,
        # al invertir en la venta, menor valor de la venta.
        movimientos.append(_fila(
            tipo_comprobante, consecutivo, fecha, nit,
            cuenta_gasto_repr, None, descuento_global,
            "Descuento global", centro_costo, observaciones, "",
        ))
        total_creditos += descuento_global
    if recargo_global and cuenta_gasto_repr:
        # Débito sobre la cuenta de gasto/ingreso: mayor valor del gasto (compra) y,
        # al invertir en la venta, cobro adicional al cliente (mayor ingreso).
        movimientos.append(_fila(
            tipo_comprobante, consecutivo, fecha, nit,
            cuenta_gasto_repr, recargo_global, None,
            "Recargo global", centro_costo, observaciones, "",
        ))
        total_debitos += recargo_global

    # ── Ajuste de redondeo al total declarado por la factura ──
    # El IVA renglón por renglón puede diferir en unos pesos del IVA que declara el
    # encabezado de la factura (el proveedor redondea cada línea por separado). Para
    # que el comprobante cuadre EXACTO contra el total de la factura —y para no
    # tomarse más IVA descontable del que declara la DIAN— se absorbe esa diferencia
    # en la línea de IVA de mayor valor. Solo se aplica si la diferencia es pequeña
    # (redondeo); una diferencia grande indica otro problema y se deja intacta para
    # no ocultarlo.
    objetivo = round(float(factura.get("total", 0) or 0), 2)
    if objetivo > 0 and lineas_iva:
        # El descuento global es un crédito que reduce el total de la factura pero no
        # el total de débitos; se descuenta aquí para comparar contra el objetivo.
        delta = round((total_debitos - descuento_global) - objetivo, 2)
        tolerancia = max(2.0, len(mapeos_confirmados) * 1.0)
        if 0 < abs(delta) <= tolerancia:
            fila = max(lineas_iva, key=lambda r: float(r["Débito"] or 0))
            ajustado = round(float(fila["Débito"] or 0) - delta, 2)
            fila["Débito"] = ajustado if ajustado else ""
            total_debitos = round(total_debitos - delta, 2)

    # Cuenta de pago seleccionada o aprendida para el proveedor (activo/pasivo)
    cuenta_pago = str(mapeos_confirmados[0].get("cuenta_pago", "")).strip() if mapeos_confirmados else ""
    cuenta_pago_nombre = str(mapeos_confirmados[0].get("cuenta_pago_nombre", "")).strip() if mapeos_confirmados else ""
    if not cuenta_pago:
        cuenta_pago = str(factura.get("cuenta_pago", "")).strip()
        cuenta_pago_nombre = factura.get("razon_social", "")
    if not cuenta_pago:
        if es_venta:
            # Contrapartida de la venta: por defecto Clientes nacionales (venta a
            # crédito). El contador la ajusta a Caja/Banco cuando es de contado.
            cuenta_pago = "130505"
        else:
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

    # Inversión de la partida doble. Se invierte cuando ``flip`` es verdadero:
    #   - Nota crédito de compra (reversa la compra).
    #   - Venta (imagen espejo de la compra: ingreso e IVA generado al crédito,
    #     cliente/contrapartida al débito).
    # Una NC de venta (devolución) vuelve a invertir, quedando como una compra en
    # cuanto a lados (débito el ingreso/devolución, crédito el cliente). Así una
    # sola lógica cubre los cuatro casos sin duplicar código.
    if flip:
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
