"""
Parser de archivos de facturas electronicas.

Soporta cuatro formatos:
  1. Token DIAN (tabular xlsx): un archivo con MULTIPLES facturas, una fila por item.
  2. Individual (xlsx): un xlsx por factura (formato clave-valor + tabla de detalle).
  3. ZIP DIAN: un ZIP con un XML UBL 2.1 y un PDF, formato de factura electronica DIAN.
  4. PDF DIAN: la representacion grafica de la factura electronica; contiene el XML
     UBL 2.1 embebido como adjunto (formato PDF/A-3 exigido por el estandar DIAN).

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
    s = re.sub(r"[^\d.,\-]", "", str(valor))
    if not s:
        return 0.0
    # Formato colombiano: puntos como miles y coma como decimal (ej. "4.621,85")
    if "," in s and re.search(r"\d\.\d{3}", s):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
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


def _limpiar_telefono(raw: str) -> str:
    """Limpia teléfonos extraídos de PDF que vienen con pipes, ej. '602|3008473688|'.
    Prefiere el número celular colombiano (10 dígitos, empieza con 3); si no, el más largo."""
    if "|" not in raw:
        return raw.strip()
    partes = [re.sub(r"\D", "", p) for p in raw.split("|") if p.strip()]
    for p in partes:
        if len(p) == 10 and p.startswith("3"):
            return p
    validas = [p for p in partes if p]
    return max(validas, key=len) if validas else raw.strip()


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
    nombre_lower = nombre_archivo.lower()
    if nombre_lower.endswith(".zip"):
        return _parsear_zip_dian(archivo, nombre_archivo)
    if nombre_lower.endswith(".pdf"):
        return _parsear_pdf_dian(archivo, nombre_archivo)

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


def _parsear_pdf_dian(archivo: BytesIO, nombre_archivo: str) -> list[dict]:
    """
    Extrae el XML UBL 2.1 embebido en el PDF de factura electronica DIAN
    (formato PDF/A-3) y lo parsea con el parser XML existente.

    Soporta tres formas de adjunto que usa la DIAN:
      1. /Root → /Names → /EmbeddedFiles (name tree plano o con /Kids)
      2. /Root → /AF (Associated Files, PDF/A-3b)
      3. Anotaciones FileAttachment en páginas
    """
    try:
        import pypdf
        from pypdf.generic import IndirectObject
    except ImportError:
        raise ValueError(
            f"'{nombre_archivo}': pypdf no esta instalado. "
            "Ejecute: pip install pypdf"
        )

    try:
        reader = pypdf.PdfReader(archivo)
    except Exception as e:
        raise ValueError(f"'{nombre_archivo}': No se pudo abrir el PDF: {e}") from e

    def resolve(obj):
        return obj.get_object() if isinstance(obj, IndirectObject) else obj

    def collect_name_tree(node) -> list:
        """Recorre un PDF name tree (plano o con /Kids) y retorna lista [nombre, ref, ...]."""
        items = []
        node = resolve(node)
        names = node.get("/Names")
        if names is not None:
            items.extend(names)
        kids = node.get("/Kids")
        if kids is not None:
            for kid in kids:
                items.extend(collect_name_tree(kid))
        return items

    def xml_de_filespec(filespec) -> bytes | None:
        """Extrae bytes XML de un FileSpec si contiene un XML."""
        try:
            filespec = resolve(filespec)
            ef = filespec.get("/EF")
            if ef is None:
                return None
            ef = resolve(ef)
            f_stream = ef.get("/F") or ef.get("/UF")
            if f_stream is None:
                return None
            data: bytes = resolve(f_stream).get_data()
            # Nombre del adjunto (puede ser clave /F en el filespec, no en /EF)
            fname = str(filespec.get("/F", "") or filespec.get("/UF", "")).lower()
            if fname.endswith(".xml") or data.lstrip()[:5] == b"<?xml":
                return data
        except Exception:
            pass
        return None

    catalog = resolve(reader.trailer["/Root"])

    # Método 1: /Root → /Names → /EmbeddedFiles (name tree — la más común en DIAN)
    try:
        names_dict_obj = catalog.get("/Names")
        if names_dict_obj is not None:
            names_dict = resolve(names_dict_obj)
            ef_obj = names_dict.get("/EmbeddedFiles")
            if ef_obj is not None:
                name_list = collect_name_tree(ef_obj)
                for i in range(0, len(name_list) - 1, 2):
                    fname = str(name_list[i])
                    filespec = resolve(name_list[i + 1])
                    ef = filespec.get("/EF")
                    if ef is None:
                        continue
                    ef = resolve(ef)
                    f_stream = ef.get("/F") or ef.get("/UF")
                    if f_stream is None:
                        continue
                    data: bytes = resolve(f_stream).get_data()
                    if fname.lower().endswith(".xml") or data.lstrip()[:5] == b"<?xml":
                        return [_parsear_xml_dian(data, fname or nombre_archivo)]
    except Exception:
        pass

    # Método 2: /Root → /AF (Associated Files, PDF/A-3b)
    try:
        af_obj = catalog.get("/AF")
        if af_obj is not None:
            af_list = resolve(af_obj)
            if not isinstance(af_list, list):
                af_list = [af_list]
            for item in af_list:
                data = xml_de_filespec(item)
                if data is not None:
                    return [_parsear_xml_dian(data, nombre_archivo)]
    except Exception:
        pass

    # Método 3: anotaciones FileAttachment en páginas
    try:
        for page in reader.pages:
            annots = page.get("/Annots")
            if annots is None:
                continue
            for annot_ref in annots:
                annot = resolve(annot_ref)
                if annot.get("/Subtype") != "/FileAttachment":
                    continue
                fs = annot.get("/FS")
                if fs is None:
                    continue
                data = xml_de_filespec(fs)
                if data is not None:
                    return [_parsear_xml_dian(data, nombre_archivo)]
    except Exception:
        pass

    # Método 4: PDF visual (Representación Gráfica) — extraer tabla con pdfplumber
    if hasattr(archivo, "seek"):
        archivo.seek(0)
    return _parsear_pdf_plumber(archivo, nombre_archivo)


def _dedup_desc_plumber(desc: str) -> str:
    """Elimina la duplicación de descripción causada por el doble-columna del PDF DIAN."""
    if not desc:
        return desc
    lines = [l.strip() for l in desc.split("\n") if l.strip()]
    if not lines:
        return desc
    # Caso simple: dos líneas idénticas
    if len(lines) == 2 and lines[0].upper() == lines[1].upper():
        return lines[0]
    # Caso general: unir y buscar la repetición por normalización sin espacios
    full = " ".join(lines)
    words = full.split()
    n = len(words)
    if n < 4:
        return full
    for split in range(max(1, n // 4), min(n, 3 * n // 4) + 1):
        first_norm = "".join(words[:split]).upper()
        rest_norm = "".join(words[split:]).upper()
        min_match = max(4, len(first_norm) * 3 // 4)
        if rest_norm.startswith(first_norm[:min_match]):
            return " ".join(words[:split])
    return full


def _parsear_pdf_plumber(archivo: BytesIO, nombre_archivo: str) -> list[dict]:
    """
    Fallback para PDFs de Representación Gráfica DIAN (sin XML embebido).
    Usa pdfplumber para extraer la tabla de ítems y el texto del encabezado.
    Funciona con PDFs generados por la Solución Gratuita DIAN y formatos similares.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ValueError(
            f"'{nombre_archivo}': El PDF no contiene XML embebido y pdfplumber no está instalado. "
            "Ejecute: pip install pdfplumber"
        )

    try:
        with pdfplumber.open(archivo) as pdf:
            page1_text = pdf.pages[0].extract_text() or ""
            page1_tables = pdf.pages[0].extract_tables() or []
            page2_tables = pdf.pages[1].extract_tables() if len(pdf.pages) > 1 else []
    except Exception as e:
        raise ValueError(f"'{nombre_archivo}': No se pudo leer el PDF: {e}") from e

    # Verificar que sea un PDF de factura electrónica DIAN
    if "factura electr" not in page1_text.lower() and "cufe" not in page1_text.lower():
        raise ValueError(
            f"'{nombre_archivo}': Este PDF no parece ser una factura electrónica DIAN. "
            "Sube el archivo ZIP de la DIAN que contiene el XML."
        )

    # ── Encabezado ──
    def rval(pattern: str, text: str) -> str:
        m = re.search(pattern, text, re.I | re.MULTILINE)
        return m.group(1).strip() if m else ""

    cufe = rval(r"\b([0-9a-fA-F]{64,})\b", page1_text).lower()
    numero_dian = rval(r"N[uú]mero de Factura:\s*(\S+)", page1_text)
    fecha = _to_fecha(rval(r"Fecha de Emisi[oó]n:\s*(\S+)", page1_text))

    # Separar sección del emisor (antes de "Adquiriente")
    emisor_text = re.split(r"Datos del Adquiriente", page1_text, maxsplit=1, flags=re.I)[0]
    razon_social = rval(r"Raz[oó]n Social:\s*(.+?)(?:\n|$)", emisor_text)
    nombre_comercial = rval(r"Nombre Comercial:\s*(.+?)(?:\n|$)", emisor_text)
    nit = re.sub(r"[^\d\-]", "", rval(r"Nit del Emisor:\s*(\S+)", emisor_text))
    ciudad = rval(r"Municipio / Ciudad:\s*(\S+)", emisor_text)
    departamento = rval(r"Departamento:\s*(.+?)(?:\s{2,}|\n|$)", emisor_text)
    direccion = rval(r"Direcci[oó]n:\s*(.+?)(?:\s{2,}|\n|$)", emisor_text)
    telefono = _limpiar_telefono(rval(r"Tel[eé]fono\s*[/\s]*M[oó]vil:\s*(.+?)(?:\s{2,}|\n|$)", emisor_text))
    email = rval(r"Correo:\s*(\S+)", emisor_text)

    tipo_contribuyente_raw = rval(r"Tipo de Contribuyente:\s*(.+?)(?:\s{2,}|\n|$)", emisor_text)
    tipo_proveedor = "natural" if "natural" in tipo_contribuyente_raw.lower() else "juridica"

    # Régimen fiscal: "R-99-PN; ZZ-No aplica" → separar responsabilidad fiscal y régimen IVA
    # Siigo distingue dos campos:
    #   - Código Responsabilidad fiscal (col R): O-13, O-15, O-23, O-47, R-99-PN
    #   - Tipo de régimen IVA (col Q): 0=No responsable, 2=Responsable
    # ZZ significa "no aplica" = no responsable de IVA → tipo_regimen_iva = "0"
    # R-XX-XX y O-XX son códigos de responsabilidad fiscal
    regimen_fiscal_raw = rval(r"R[eé]gimen Fiscal:\s*(.+?)(?:\n|$)", emisor_text)
    tipo_regimen_iva = ""
    codigo_responsabilidad_pdf = ""
    if regimen_fiscal_raw:
        # Responsabilidad fiscal: O-XX o R-XX-XX (ej. R-99-PN, O-13, O-23)
        m_resp = re.search(r"\b(O-\d{2,3}|R-\d{2}-\w+)\b", regimen_fiscal_raw, re.I)
        if m_resp:
            codigo_responsabilidad_pdf = m_resp.group(1).upper()
        # Régimen IVA: RC/GC = responsable (2); RS/NC/RNC/ZZ/no aplica = no responsable (0)
        m_reg = re.search(r"\b(ZZ|RC|RS|GC|NC|RNC)\b", regimen_fiscal_raw, re.I)
        if m_reg:
            tipo_regimen_iva = "2" if m_reg.group(1).upper() in ("RC", "GC") else "0"
        elif re.search(r"no\s+aplica", regimen_fiscal_raw, re.I):
            tipo_regimen_iva = "0"

    # "Responsabilidad tributaria: 01 - IVA" o "ZZ - No aplica" sobreescribe si existe
    responsabilidad_raw = rval(r"Responsabilidad tributaria:\s*(.+?)(?:\n|$)", emisor_text)
    if responsabilidad_raw:
        # Responsabilidad fiscal explícita (O-XX o R-XX-XX)
        m_resp2 = re.search(r"\b(O-\d{2,3}|R-\d{2}-\w+)\b", responsabilidad_raw, re.I)
        if m_resp2:
            codigo_responsabilidad_pdf = m_resp2.group(1).upper()
        # "no aplica" o ZZ = no responsable de IVA
        if re.search(r"no\s+aplica|\bZZ\b", responsabilidad_raw, re.I):
            tipo_regimen_iva = "0"
        # "01 - IVA" o "\d+ - IVA" = responsable de IVA (código DIAN de obligación tributaria)
        elif re.search(r"\bIVA\b", responsabilidad_raw, re.I):
            tipo_regimen_iva = "2"

    # ── Forma y medio de pago (solo XML/PDF, no Excel) ──
    forma_pago_raw = rval(r"Forma\s+de\s+Pago[:\s]+(.+?)(?:\s{2,}|\n|$)", page1_text)
    if not forma_pago_raw:
        forma_pago_raw = rval(r"Condici[oó]n\s+de\s+Pago[:\s]+(.+?)(?:\s{2,}|\n|$)", page1_text)
    forma_pago = forma_pago_raw.upper() if forma_pago_raw else ""

    medio_pago_raw = rval(r"Medio\s+de\s+Pago[:\s]+(.+?)(?:\s{2,}|\n|$)", page1_text)
    _PDF_MEDIO: dict[str, str] = {
        "efectivo":    "efectivo",
        "transfe":     "transferencia",
        "debito ban":  "debito_bancario",
        "debito":      "debito_bancario",
        "tarjeta deb": "tarjeta_debito",
        "tarjeta cre": "tarjeta_credito",
        "credito":     "tarjeta_credito",
        "cheque cert": "cheque_certificado",
        "cheque":      "cheque",
    }
    medio_pago = ""
    if medio_pago_raw:
        norm_mp = medio_pago_raw.lower().strip()
        for k, v in _PDF_MEDIO.items():
            if k in norm_mp:
                medio_pago = v
                break
        if not medio_pago:
            medio_pago = norm_mp

    # ── Tabla de ítems ──
    items: list[dict] = []
    items_table = next(
        (t for t in page1_tables
         if any(any(c and "Nro" in str(c) for c in row) for row in t[:3])),
        None,
    )

    if items_table:
        for row in items_table:
            if not row or not row[0] or not re.match(r"^\d+$", str(row[0]).strip()):
                continue

            desc = _dedup_desc_plumber(str(row[2] or "").strip())
            if not desc:
                desc = f"Ítem {row[0]}"

            # col[12] = Precio unitario de venta = base total de la línea (sin IVA)
            base = _to_float(str(row[12] or "0").replace("$", ""))
            if base == 0.0:
                precio = _to_float(str(row[5] or "0").replace("$", ""))
                cantidad = _to_float(str(row[4] or "1"))
                base = round(precio * cantidad, 2)

            iva_amount = _to_float(str(row[8] or "0").replace("$", ""))
            iva_pct = _to_float(str(row[9] or "0"))

            items.append({
                "descripcion": desc,
                "base": base,
                "cod_impuesto": _inferir_cod_impuesto(iva_pct),
                "porcentaje": iva_pct,
                "valor_impuesto": round(iva_amount, 2),
                "total_linea": round(base + iva_amount, 2),
            })

    if not items:
        raise ValueError(
            f"'{nombre_archivo}': No se encontró la tabla de ítems en el PDF. "
            "Este formato de PDF no es compatible — sube el archivo ZIP de la DIAN."
        )

    # ── Total ──
    # Buscar en todas las páginas con múltiples etiquetas reconocidas
    _TOTAL_LABELS = {"total factura", "total a pagar", "valor total", "gran total",
                     "total neto", "valor a pagar", "total comprobante", "total general"}
    total = 0.0
    all_tables = list(page1_tables) + list(page2_tables)
    for table in all_tables:
        for row in table:
            if not row:
                continue
            label = str(row[0] or "").lower().strip()
            if any(lbl in label for lbl in _TOTAL_LABELS):
                # Intentar la última celda no vacía como valor
                for cell in reversed(row[1:]):
                    val_str = str(cell or "").strip()
                    if val_str:
                        cand = _to_float(re.sub(r"[^\d.,]", "", val_str))
                        if cand > total:
                            total = cand
                        break

    # Fallback: calcular desde la suma de ítems si aún es 0
    if total == 0.0 and items:
        total = round(sum(i["total_linea"] for i in items), 2)

    return [{
        "numero_dian":              numero_dian,
        "cufe":                     cufe,
        "fecha":                    fecha,
        "nit":                      nit,
        "razon_social":             razon_social,
        "nombre_comercial":         nombre_comercial,
        "tipo_proveedor":           tipo_proveedor,
        "regimen":                  "",
        "tipo_regimen_iva":         tipo_regimen_iva,
        "codigo_responsabilidad":   codigo_responsabilidad_pdf,
        "ciudad":                   ciudad,
        "departamento":             departamento,
        "direccion":                direccion,
        "telefono":                 telefono,
        "email":                    email,
        "_fuente":                  "pdf",
        "medio_pago":               medio_pago,
        "forma_pago":               forma_pago,
        "total":                    total,
        "items":                    items,
        "advertencias":             [
            "Extraído del PDF (representación gráfica). "
            "Verifique los montos contra la factura original antes de causar."
        ],
    }]


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
    nombre_comercial = ""
    tipo_proveedor = "juridica"
    tipo_identificacion_codigo = ""
    ciudad = ""
    departamento = ""
    direccion = ""
    codigo_postal = ""
    telefono = ""
    email = ""
    nombres_tercero = ""
    apellidos_tercero = ""

    supplier = find("cac:AccountingSupplierParty/cac:Party")
    if supplier is not None:
        # NIT y tipo identificación
        tax_scheme = supplier.find("cac:PartyTaxScheme", _NS)
        if tax_scheme is not None:
            nit_el = tax_scheme.find("cbc:CompanyID", _NS)
            if nit_el is not None and nit_el.text:
                nit = re.sub(r"[^\d\-]", "", nit_el.text.strip())
                scheme_id = (nit_el.get("schemeID") or "").strip()
                tipo_identificacion_codigo = scheme_id
                if scheme_id in ("13", "22"):
                    tipo_proveedor = "natural"
                elif scheme_id == "31":
                    tipo_proveedor = "juridica"

        # Razón social
        legal = supplier.find("cac:PartyLegalEntity", _NS)
        if legal is not None:
            razon_social = _xml_text(legal.find("cbc:RegistrationName", _NS))
        # Nombre comercial (PartyName puede ser diferente de RegistrationName)
        pname = supplier.find("cac:PartyName", _NS)
        if pname is not None:
            candidate = _xml_text(pname.find("cbc:Name", _NS))
            if not razon_social:
                razon_social = candidate
            elif candidate and candidate.upper() != razon_social.upper():
                nombre_comercial = candidate

        # Dirección completa
        addr = supplier.find("cac:PhysicalLocation/cac:Address", _NS)
        if addr is None:
            addr = supplier.find("cac:PostalAddress", _NS)
        if addr is not None:
            ciudad = _xml_text(addr.find("cbc:CityName", _NS))
            departamento = _xml_text(addr.find("cbc:CountrySubentity", _NS))
            codigo_postal = _xml_text(addr.find("cbc:PostalZone", _NS))
            addr_line = addr.find("cac:AddressLine", _NS)
            if addr_line is not None:
                direccion = _xml_text(addr_line.find("cbc:Line", _NS))

        # Contacto
        contact = supplier.find("cac:Contact", _NS)
        if contact is not None:
            telefono = _xml_text(contact.find("cbc:Telephone", _NS))
            email = _xml_text(contact.find("cbc:ElectronicMail", _NS))

        # Nombres/apellidos para personas naturales
        person = supplier.find("cac:Person", _NS)
        if person is not None:
            nombres_tercero = _xml_text(person.find("cbc:FirstName", _NS))
            apellidos_tercero = _xml_text(person.find("cbc:FamilyName", _NS))

    # ── Medios y forma de pago (para sugerencias de cuenta de pago) ──
    _PM_CODE: dict[str, str] = {
        "10": "efectivo",
        "20": "cheque",
        "21": "cheque_certificado",
        "31": "transferencia",
        "42": "debito_bancario",
        "47": "tarjeta_debito",
        "48": "tarjeta_credito",
        "49": "tarjeta_credito",
    }
    medio_pago = ""
    forma_pago = ""

    payment_means = find("cac:PaymentMeans")
    if payment_means is not None:
        code_el = payment_means.find("cbc:PaymentMeansCode", _NS)
        if code_el is not None and code_el.text:
            medio_pago = _PM_CODE.get(code_el.text.strip(), code_el.text.strip())

    payment_terms = find("cac:PaymentTerms")
    if payment_terms is not None:
        note_el = payment_terms.find("cbc:Note", _NS)
        if note_el is not None and note_el.text:
            forma_pago = note_el.text.strip()

    # Inferir forma de pago por fecha de vencimiento si no está explícita
    if not forma_pago:
        issue_date = _xml_text(find("cbc:IssueDate"))
        due_date = _xml_text(find("cbc:DueDate"))
        if issue_date and due_date:
            forma_pago = "CONTADO" if issue_date == due_date else "CRÉDITO"

    # ── Comprador (buyer) — solo para validación compra vs venta ──
    nit_comprador = ""
    customer = find("cac:AccountingCustomerParty/cac:Party")
    if customer is not None:
        tax_scheme_c = customer.find("cac:PartyTaxScheme", _NS)
        if tax_scheme_c is not None:
            nit_c_el = tax_scheme_c.find("cbc:CompanyID", _NS)
            if nit_c_el is not None and nit_c_el.text:
                nit_comprador = re.sub(r"[^\d\-]", "", nit_c_el.text.strip())

    # ── Total ──
    monetary = find("cac:LegalMonetaryTotal")
    total = 0.0
    if monetary is not None:
        total = _xml_float(monetary.find("cbc:PayableAmount", _NS))
        if total == 0.0:
            total = _xml_float(monetary.find("cbc:TaxInclusiveAmount", _NS))
        if total == 0.0:
            total = _xml_float(monetary.find("cbc:LineExtensionAmount", _NS))

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

    # Fallback: si el total no se pudo leer del XML, calcularlo desde los ítems
    if total == 0.0 and items:
        total = round(sum(i["total_linea"] for i in items), 2)

    return {
        "numero_dian":              numero_dian,
        "cufe":                     cufe,
        "fecha":                    fecha,
        "nit":                      nit,
        "nit_comprador":            nit_comprador,
        "razon_social":             razon_social,
        "nombre_comercial":         nombre_comercial,
        "tipo_proveedor":           tipo_proveedor,
        "tipo_identificacion_codigo": tipo_identificacion_codigo,
        "regimen":                  "",
        "tipo_regimen_iva":         "",
        "codigo_responsabilidad":   "",
        "ciudad":                   ciudad,
        "departamento":             departamento,
        "direccion":                direccion,
        "codigo_postal":            codigo_postal,
        "telefono":                 telefono,
        "email":                    email,
        "nombres_tercero":          nombres_tercero,
        "apellidos_tercero":        apellidos_tercero,
        "_fuente":                  "xml",
        "medio_pago":               medio_pago,
        "forma_pago":               forma_pago,
        "total":                    total,
        "items":                    items,
        "advertencias":             advertencias,
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
