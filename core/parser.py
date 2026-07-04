"""
Parser de archivos de facturas electronicas.

Soporta tres formatos:
  1. Token DIAN (tabular xlsx): un archivo con MULTIPLES facturas, una fila por item.
  2. Individual (xlsx): un xlsx por factura (formato clave-valor + tabla de detalle).
  3. ZIP DIAN: un ZIP con un XML UBL 2.1 y un PDF, formato de factura electronica DIAN.

La funcion principal `parsear_archivo()` detecta automaticamente el formato
y retorna una lista de facturas (incluso si es solo una).
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from typing import Any

import pandas as pd


# Normalizacion

def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto).lower())
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", sin_acentos).strip()


def _to_float(valor: Any) -> float:
    if pd.isna(valor):
        return 0.0
    limpio = re.sub(r"[^\d.,\-]", "", str(valor)).replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def _to_fecha(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    # Intentar formatos comunes usados en archivos DIAN
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            ts = pd.to_datetime(valor, format=fmt)
            return ts.strftime("%d/%m/%Y")
        except Exception:
            pass
    try:
        ts = pd.to_datetime(valor)
        return ts.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


# Sinonimos para formato token DIAN

_COLS_TOKEN: dict[str, list[str]] = {
    "tipo_id":     ["tipo id", "tipo de id", "tipo identificacion", "tipo persona"],
    "nit":         ["nit del", "nit pro", "identificacion del", "nit"],
    "razon_social":["nombre del", "nombre de", "razon social", "proveedor"],
    "numero_dian": ["numero f", "numero de factura", "num factura", "numero factura", "numfact", "prefijo"],
    "fecha":       ["fecha emision", "fecha de emision", "fecha factura", "fecha"],
    "fecha_vence": ["fecha vencim", "fecha de venc", "vencim"],
    "concepto":    ["concepto"],
    "descripcion": ["descripcion de prod", "descripcion prod", "descripcion", "descripci"],
    "precio_unit": ["precio uni", "precio unitario", "valor unitario", "precio"],
    "cantidad":    ["cantidad", "cant"],
    "total_imp":   ["total de ir", "total de im", "total impuesto", "total iva", "valor iva", "impuesto"],
    "porcentaje":  ["porcentaje iva", "porcentaje imp", "tarifa iva", "tarifa imp", "tarifa"],
    "descuento":   ["porcentaje de desc", "descuento", "dto"],
    "total_linea": ["total"],
    "ciudad":      ["ciudad"],
    "direccion":   ["direccion"],
    "cufe":        ["cufe"],
}


def _detectar_cols_token(df: pd.DataFrame) -> dict[str, str | None]:
    cols_norm = {_norm(c): c for c in df.columns}
    asignadas: set[str] = set()
    result: dict[str, str | None] = {}

    PRIORITY = [
        "tipo_id", "nit", "razon_social", "numero_dian", "fecha", "fecha_vence",
        "concepto", "descripcion", "precio_unit", "cantidad",
        "total_imp", "porcentaje", "descuento", "total_linea",
        "ciudad", "direccion", "cufe",
    ]

    for campo in PRIORITY:
        sinonimos = _COLS_TOKEN[campo]
        found = None

        for s in sinonimos:
            for col_n, col_orig in cols_norm.items():
                if col_n == s and col_orig not in asignadas:
                    found = col_orig
                    break
            if found:
                break

        if not found:
            for s in sinonimos:
                for col_n, col_orig in cols_norm.items():
                    if s in col_n and col_orig not in asignadas:
                        found = col_orig
                        break
                if found:
                    break

        if found:
            asignadas.add(found)
        result[campo] = found

    return result


def _es_formato_token_dian(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    col = _detectar_cols_token(df)
    hits = sum(1 for campo in ["nit", "numero_dian", "cantidad", "precio_unit", "cufe"] if col.get(campo))
    return hits >= 3


def _parsear_token_dian(archivo: BytesIO | str, nombre_archivo: str = "") -> list[dict]:
    df = pd.read_excel(archivo, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)

    col = _detectar_cols_token(df)

    if not col.get("numero_dian"):
        raise ValueError(
            f"'{nombre_archivo}': No se detecto columna de numero de factura. "
            "Verifique que el archivo sea un export del token DIAN."
        )

    facturas: dict[str, dict] = {}

    for _, row in df.iterrows():
        num_dian = str(row[col["numero_dian"]]).strip() if col.get("numero_dian") else ""
        if not num_dian or num_dian.lower() in ("nan", "numero f.", "numero factura"):
            continue

        if num_dian not in facturas:
            nit = str(row[col["nit"]]).strip() if col.get("nit") else ""
            nit = re.sub(r"[^\d\-]", "", nit)

            razon = str(row[col["razon_social"]]).strip() if col.get("razon_social") else ""
            if razon.lower() == "nan":
                razon = ""

            fecha = _to_fecha(row[col["fecha"]]) if col.get("fecha") else ""
            tipo_id = str(row[col["tipo_id"]]).strip().lower() if col.get("tipo_id") else "nit"
            cufe = str(row[col["cufe"]]).strip() if col.get("cufe") else ""
            if cufe.lower() == "nan":
                cufe = ""
            ciudad = str(row[col["ciudad"]]).strip() if col.get("ciudad") else ""
            if ciudad.lower() == "nan":
                ciudad = ""

            tipo_prov = "juridica"
            if tipo_id in ("cc", "cedula", "ce", "pasaporte", "c.c.", "cedula de ciudadania"):
                tipo_prov = "natural"

            facturas[num_dian] = {
                "numero_dian":   num_dian,
                "cufe":          cufe,
                "fecha":         fecha,
                "nit":           nit,
                "razon_social":  razon,
                "tipo_proveedor":tipo_prov,
                "regimen":       "",
                "ciudad":        ciudad,
                "total":         0.0,
                "items":         [],
                "advertencias":  [],
            }

        precio_unit = _to_float(row[col["precio_unit"]]) if col.get("precio_unit") else 0.0
        cantidad    = _to_float(row[col["cantidad"]])    if col.get("cantidad")    else 1.0
        total_imp   = _to_float(row[col["total_imp"]])  if col.get("total_imp")   else 0.0
        total_linea = _to_float(row[col["total_linea"]]) if col.get("total_linea") else 0.0
        porcentaje  = _to_float(row[col["porcentaje"]]) if col.get("porcentaje")  else 0.0
        descuento   = _to_float(row[col["descuento"]])  if col.get("descuento")   else 0.0

        desc = ""
        for campo_desc in ("descripcion", "concepto"):
            if col.get(campo_desc):
                val = str(row[col[campo_desc]]).strip()
                if val and val.lower() not in ("nan", ""):
                    desc = val
                    break
        if not desc:
            desc = f"Item {num_dian}"

        if precio_unit > 0 and cantidad > 0:
            base = round(precio_unit * cantidad - descuento, 2)
        elif total_linea > 0:
            base = round(total_linea - total_imp, 2)
        else:
            base = 0.0

        # Saltar filas de detalle de IVA que algunos exports DIAN incluyen como fila separada:
        # tienen base=0 pero impuesto>0 o total_linea>0 → su IVA ya está en la fila del producto.
        if base == 0.0 and (total_imp > 0.0 or total_linea > 0.0):
            continue

        if porcentaje == 0.0 and total_imp > 0 and base > 0:
            porcentaje = round(total_imp / base * 100, 2)

        if total_linea == 0.0:
            total_linea = round(base + total_imp, 2)

        cod_impuesto = _inferir_cod_impuesto(porcentaje)

        item = {
            "descripcion":    desc,
            "base":           base,
            "cod_impuesto":   cod_impuesto,
            "porcentaje":     porcentaje,
            "valor_impuesto": total_imp,
            "total_linea":    total_linea,
        }
        facturas[num_dian]["items"].append(item)

    result: list[dict] = []
    for fac in facturas.values():
        # Eliminar ítems duplicados exactos (descripcion + base + valor_impuesto)
        # que aparecen en algunos exportes DIAN que incluyen filas de impuesto separadas
        seen: set[tuple] = set()
        items_unicos: list[dict] = []
        for it in fac["items"]:
            key = (it["descripcion"], round(it["base"], 2), round(it["valor_impuesto"], 2))
            if key not in seen:
                seen.add(key)
                items_unicos.append(it)
        fac["items"] = items_unicos
        fac["total"] = round(sum(i["total_linea"] for i in fac["items"]), 2)
        if not fac["items"]:
            fac["advertencias"].append("No se detectaron items para esta factura.")
        result.append(fac)

    if not result:
        raise ValueError(
            f"'{nombre_archivo}': No se pudieron extraer facturas. "
            "Verifique que el archivo tenga datos de facturas electronicas."
        )

    return result


def _inferir_cod_impuesto(porcentaje: float) -> str:
    """Infiere el código numérico de impuesto SIIGO según la tarifa.

    Coincide con los códigos de codigos_impuestos.xlsx:
      1=IVA 19%, 2=IVA 5%, 22=IVA 0% (exento/excluido).
    """
    if porcentaje == 0.0:
        return "22"   # IVA 0%
    # Tabla: tarifa → código SIIGO
    _TABLA = [
        (19.0, "1"),
        (5.0,  "2"),
        (0.0,  "22"),
    ]
    for rate, cod in _TABLA:
        if abs(porcentaje - rate) < 0.5:
            return cod
    return ""   # Tarifa no reconocida — usuario debe seleccionar manualmente


def parsear_archivo(archivo: BytesIO | str, nombre_archivo: str = "") -> list[dict]:
    if nombre_archivo.lower().endswith(".zip"):
        return _parsear_zip_dian(archivo, nombre_archivo)

    try:
        df_check = pd.read_excel(archivo, dtype=str, nrows=5)
    except Exception as e:
        raise ValueError(f"No se pudo leer '{nombre_archivo}': {e}") from e

    if hasattr(archivo, "seek"):
        archivo.seek(0)

    if _es_formato_token_dian(df_check):
        return _parsear_token_dian(archivo, nombre_archivo)
    else:
        return [_parsear_factura_individual(archivo, nombre_archivo)]


# ─── Parser ZIP / XML DIAN (UBL 2.1) ─────────────────────────────────────────

# Namespaces del estándar UBL 2.1 usado por DIAN
_NS = {
    "invoice": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cbc":     "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac":     "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ext":     "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sts":     "dian:gov:co:facturaelectronica:Structures-2-1",
    "ds":      "http://www.w3.org/2000/09/xmldsig#",
    "xades":   "http://uri.etsi.org/01903/v1.3.2#",
    "ad":      "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2",
}


def _parsear_zip_dian(archivo: BytesIO | str, nombre_archivo: str = "") -> list[dict]:
    """Abre el ZIP DIAN, extrae el XML y lo parsea. Retorna lista con una factura."""
    if isinstance(archivo, str):
        with open(archivo, "rb") as f:
            archivo = BytesIO(f.read())

    try:
        with zipfile.ZipFile(archivo) as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_names:
                raise ValueError(f"'{nombre_archivo}': El ZIP no contiene ningún archivo XML.")
            xml_bytes = zf.read(xml_names[0])
    except zipfile.BadZipFile as e:
        raise ValueError(f"'{nombre_archivo}': No es un archivo ZIP válido.") from e

    return [_parsear_xml_dian(xml_bytes, nombre_archivo)]


def _xml_text(el: ET.Element | None) -> str:
    return el.text.strip() if el is not None and el.text else ""


def _xml_float(el: ET.Element | None) -> float:
    txt = _xml_text(el)
    try:
        return float(txt.replace(",", ".")) if txt else 0.0
    except ValueError:
        return 0.0


def _parsear_xml_dian(xml_bytes: bytes, nombre_archivo: str = "") -> dict:
    """
    Parsea el XML UBL 2.1 de la DIAN y devuelve el mismo dict que los parsers Excel:
    numero_dian, cufe, fecha, nit, razon_social, tipo_proveedor, regimen,
    ciudad, total, items, advertencias.
    """
    advertencias: list[str] = []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"'{nombre_archivo}': XML inválido: {e}") from e

    # El DIAN puede envolver la factura en un AttachedDocument — extraer Invoice interno
    tag = root.tag
    if "AttachedDocument" in tag or "ApplicationResponse" in tag:
        ns_inv = f"{{{_NS['invoice']}}}Invoice"
        invoice = root.find(f".//{ns_inv}")
        if invoice is None:
            invoice = root.find(".//Invoice")
        if invoice is None:
            raise ValueError(f"'{nombre_archivo}': No se encontró Invoice dentro del AttachedDocument.")
        root = invoice

    cbc = _NS["cbc"]
    cac = _NS["cac"]

    def find(path: str) -> ET.Element | None:
        return root.find(path, _NS)

    def findall(path: str) -> list[ET.Element]:
        return root.findall(path, _NS)

    # ── Encabezado ──
    numero_dian = _xml_text(find("cbc:ID"))
    if not numero_dian:
        numero_dian = re.sub(r"\.(zip|xml)$", "", nombre_archivo, flags=re.I)

    cufe = _xml_text(find("cbc:UUID"))
    fecha = _to_fecha(_xml_text(find("cbc:IssueDate")))

    # ── Proveedor ──
    nit = ""
    razon_social = ""
    tipo_proveedor = "juridica"
    ciudad = ""

    supplier = find("cac:AccountingSupplierParty/cac:Party")
    if supplier is not None:
        # NIT
        tax_scheme = supplier.find("cac:PartyTaxScheme", _NS)
        if tax_scheme is not None:
            nit_el = tax_scheme.find("cbc:CompanyID", _NS)
            if nit_el is not None and nit_el.text:
                nit = re.sub(r"[^\d\-]", "", nit_el.text.strip())
                scheme_id = (nit_el.get("schemeID") or "").strip()
                if scheme_id in ("13", "22", "31"):
                    tipo_proveedor = "natural" if scheme_id in ("13", "22") else "juridica"

        # Razón social
        legal = supplier.find("cac:PartyLegalEntity", _NS)
        if legal is not None:
            razon_social = _xml_text(legal.find("cbc:RegistrationName", _NS))
        if not razon_social:
            pname = supplier.find("cac:PartyName", _NS)
            if pname is not None:
                razon_social = _xml_text(pname.find("cbc:Name", _NS))

        # Ciudad
        addr = supplier.find("cac:PhysicalLocation/cac:Address", _NS)
        if addr is None:
            addr = supplier.find("cac:PostalAddress", _NS)
        if addr is not None:
            ciudad = _xml_text(addr.find("cbc:CityName", _NS))

    # ── Total ──
    monetary = find("cac:LegalMonetaryTotal")
    total = 0.0
    if monetary is not None:
        total = _xml_float(monetary.find("cbc:PayableAmount", _NS))
        if total == 0.0:
            total = _xml_float(monetary.find("cbc:TaxInclusiveAmount", _NS))

    # ── Ítems ──
    items: list[dict] = []

    for line in findall("cac:InvoiceLine"):
        # Descripción
        desc = ""
        item_el = line.find("cac:Item", _NS)
        if item_el is not None:
            desc = _xml_text(item_el.find("cbc:Description", _NS))
            if not desc:
                desc = _xml_text(item_el.find("cac:SellersItemIdentification/cbc:ID", _NS))
        if not desc:
            desc = _xml_text(line.find("cbc:Note", _NS))
        if not desc:
            desc = f"Item {len(items) + 1}"

        # Base (LineExtensionAmount = base sin impuestos)
        base = _xml_float(line.find("cbc:LineExtensionAmount", _NS))

        # IVA: buscar en TaxTotal los subtotales con TaxScheme 01 (IVA)
        valor_impuesto = 0.0
        porcentaje = 0.0

        for tax_total in line.findall("cac:TaxTotal", _NS):
            for sub in tax_total.findall("cac:TaxSubtotal", _NS):
                cat = sub.find("cac:TaxCategory", _NS)
                if cat is None:
                    continue
                scheme = cat.find("cac:TaxScheme", _NS)
                scheme_id = ""
                if scheme is not None:
                    scheme_id = _xml_text(scheme.find("cbc:ID", _NS))

                # Incluir solo IVA (01); excluir retenciones (04=ICA, 05=RetICA, 06=Retefuente)
                if scheme_id in ("01", ""):
                    valor_impuesto += _xml_float(sub.find("cbc:TaxAmount", _NS))
                    if porcentaje == 0.0:
                        porcentaje = _xml_float(cat.find("cbc:Percent", _NS))

        # Saltar líneas vacías (base=0 y sin impuesto — no hay valores a causar)
        if base == 0.0 and valor_impuesto == 0.0:
            continue

        cod_impuesto = _inferir_cod_impuesto(porcentaje)
        items.append({
            "descripcion":    desc,
            "base":           round(base, 2),
            "cod_impuesto":   cod_impuesto,
            "porcentaje":     porcentaje,
            "valor_impuesto": round(valor_impuesto, 2),
            "total_linea":    round(base + valor_impuesto, 2),
        })

    if not items:
        advertencias.append("No se detectaron ítems en el XML DIAN.")

    return {
        "numero_dian":    numero_dian,
        "cufe":           cufe,
        "fecha":          fecha,
        "nit":            nit,
        "razon_social":   razon_social,
        "tipo_proveedor": tipo_proveedor,
        "regimen":        "",
        "ciudad":         ciudad,
        "total":          total,
        "items":          items,
        "advertencias":   advertencias,
    }


# Helpers para formato individual

_SINONIMOS_IND: dict[str, list[str]] = {
    "numero_dian":   ["numero", "num factura", "factura", "cufe", "consecutivo"],
    "fecha":         ["fecha", "fecha emision", "fecha factura"],
    "nit":           ["nit", "nit proveedor", "identificacion", "cedula"],
    "razon_social":  ["razon social", "nombre", "proveedor", "emisor"],
    "tipo_proveedor":["tipo", "tipo proveedor", "tipo persona"],
    "regimen":       ["regimen", "regimen tributario"],
    "total":         ["total", "valor total", "total factura", "gran total"],
    "ciudad":        ["ciudad", "municipio"],
    "descripcion":   ["descripcion", "concepto", "detalle", "producto", "servicio"],
    "base":          ["base", "valor base", "subtotal", "valor neto"],
    "cod_impuesto":  ["cod impuesto", "codigo impuesto", "tipo impuesto"],
    "porcentaje":    ["porcentaje", "tarifa", "tasa"],
    "valor_impuesto":["valor impuesto", "valor iva", "iva", "impuesto valor"],
}


def _detectar_col_ind(columnas: list[str], campo: str) -> str | None:
    sinonimos = _SINONIMOS_IND.get(campo, [])
    for col in columnas:
        col_n = _norm(col)
        for s in sinonimos:
            if s in col_n or col_n in s:
                return col
    return None


def _detectar_hojas(hojas: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(hojas) == 1:
        hoja = list(hojas.values())[0]
        return hoja, hoja
    hoja_items = max(hojas.values(), key=lambda df: len(df))
    hoja_encabezado = list(hojas.values())[0]
    for nombre, df in hojas.items():
        n = nombre.lower()
        if any(x in n for x in ["detalle", "item", "linea", "concepto"]):
            hoja_items = df
        if any(x in n for x in ["encabez", "header", "general", "factura"]):
            hoja_encabezado = df
    return hoja_encabezado, hoja_items


def _parsear_encabezado_kv(df: pd.DataFrame, advertencias: list[str]) -> dict:
    resultado: dict = {}
    if df.shape[1] >= 2:
        for _, row in df.iterrows():
            etiqueta = _norm(str(row.iloc[0]))
            valor = str(row.iloc[1]).strip() if not pd.isna(row.iloc[1]) else ""
            if not etiqueta or etiqueta == "nan":
                continue
            for campo, sinonimos in _SINONIMOS_IND.items():
                if campo in ("descripcion", "base", "cod_impuesto", "porcentaje", "valor_impuesto"):
                    continue
                for s in sinonimos:
                    if s in etiqueta and campo not in resultado and valor:
                        resultado[campo] = valor
                        break
    if "fecha" in resultado:
        resultado["fecha"] = _to_fecha(resultado["fecha"])
    if "total" in resultado:
        resultado["total"] = _to_float(resultado["total"])
    if "nit" in resultado:
        resultado["nit"] = re.sub(r"[^\d\-]", "", resultado["nit"])
    nit = resultado.get("nit", "")
    if nit and len(re.sub(r"\D", "", nit)) <= 10 and not nit.startswith("9"):
        resultado.setdefault("tipo_proveedor", "natural")
    else:
        resultado.setdefault("tipo_proveedor", "juridica")
    return resultado


def _parsear_items_tabla(df: pd.DataFrame, advertencias: list[str]) -> list[dict]:
    items: list[dict] = []
    fila_header = _buscar_fila_encabezados(df)
    if fila_header is None:
        advertencias.append("No se detectaron lineas de items en la factura.")
        return items

    df_items = df.iloc[fila_header + 1:].copy()
    df_items.columns = [str(df.iloc[fila_header, i]) for i in range(df.shape[1])]
    df_items = df_items.reset_index(drop=True)

    col_desc    = _detectar_col_ind(list(df_items.columns), "descripcion")
    col_base    = _detectar_col_ind(list(df_items.columns), "base")
    col_cod_imp = _detectar_col_ind(list(df_items.columns), "cod_impuesto")
    col_pct     = _detectar_col_ind(list(df_items.columns), "porcentaje")
    col_val_imp = _detectar_col_ind(list(df_items.columns), "valor_impuesto")

    if not col_desc and not col_base:
        advertencias.append("No se pudieron identificar columnas de items.")
        return items

    for _, row in df_items.iterrows():
        desc = str(row[col_desc]).strip() if col_desc else ""
        base = _to_float(row[col_base]) if col_base else 0.0
        if not desc or desc.lower() in ("nan", "total", "subtotal", ""):
            continue
        val_imp = _to_float(row[col_val_imp]) if col_val_imp else 0.0
        pct     = _to_float(row[col_pct])     if col_pct     else 0.0
        items.append({
            "descripcion":    desc,
            "base":           base,
            "cod_impuesto":   str(row[col_cod_imp]).strip() if col_cod_imp else "",
            "porcentaje":     pct,
            "valor_impuesto": val_imp,
            "total_linea":    round(base + val_imp, 2),
        })
    return items


def _buscar_fila_encabezados(df: pd.DataFrame) -> int | None:
    campos_item = ["descripcion", "base", "cod_impuesto", "porcentaje", "valor_impuesto"]
    mejor_fila, mejor_puntaje = None, 0
    for i, row in df.iterrows():
        puntaje = 0
        for val in row:
            val_n = _norm(str(val))
            for campo in campos_item:
                for s in _SINONIMOS_IND[campo]:
                    if s in val_n:
                        puntaje += 1
                        break
        if puntaje > mejor_puntaje:
            mejor_puntaje, mejor_fila = puntaje, i
    return mejor_fila if mejor_puntaje >= 2 else None


def _parsear_factura_individual(archivo: BytesIO | str, nombre_archivo: str = "") -> dict:
    advertencias: list[str] = []
    try:
        hojas = pd.read_excel(archivo, sheet_name=None, header=None, dtype=str)
    except Exception as e:
        raise ValueError(f"No se pudo leer '{nombre_archivo}': {e}") from e

    hoja_enc, hoja_items = _detectar_hojas(hojas)
    encabezado = _parsear_encabezado_kv(hoja_enc, advertencias)
    items = _parsear_items_tabla(hoja_items, advertencias)

    if not encabezado.get("nit"):
        advertencias.append("No se detecto NIT del proveedor.")
    if not encabezado.get("numero_dian"):
        advertencias.append("No se detecto numero de factura DIAN.")

    total_fac = encabezado.get("total", 0.0)
    total_calc = sum(i["base"] + i["valor_impuesto"] for i in items)
    if total_fac and abs(total_calc - total_fac) > 1:
        advertencias.append(
            f"Discrepancia en totales: calculado ${total_calc:,.0f} vs factura ${total_fac:,.0f}."
        )

    return {
        "numero_dian":   encabezado.get("numero_dian", nombre_archivo),
        "cufe":          encabezado.get("cufe", ""),
        "fecha":         encabezado.get("fecha", ""),
        "nit":           encabezado.get("nit", ""),
        "razon_social":  encabezado.get("razon_social", ""),
        "tipo_proveedor":encabezado.get("tipo_proveedor", "juridica"),
        "regimen":       encabezado.get("regimen", ""),
        "ciudad":        encabezado.get("ciudad", ""),
        "total":         total_fac,
        "items":         items,
        "advertencias":  advertencias,
    }
