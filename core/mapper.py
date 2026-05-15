"""
Mapper de cuentas contables PUC.

Responsabilidades:
- Cargar codigos_impuestos.xlsx y Cuentas_contables.xlsx desde la raíz del proyecto.
- Dado un item de factura, devolver las cuentas débito/crédito correspondientes.
- Consultar SQLite (db.memory) para aprovechar mapeos aprendidos.
- Determinar la cuenta del proveedor según tipo (jurídica / natural).
"""

from __future__ import annotations

import os
import re
import unicodedata

import pandas as pd

from db import memory as mem

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")

# Rutas de archivos base
_RUTA_IMPUESTOS    = os.path.join(BASE_DIR, "codigos_impuestos.xlsx")
_RUTA_CUENTAS      = os.path.join(BASE_DIR, "Cuentas_contables.xlsx")
_RUTA_TIPOS        = os.path.join(BASE_DIR, "Tipos_comprobante_contable.xlsx")


# ── Carga de archivos base ─────────────────────────────────────────────────────

_df_impuestos: pd.DataFrame | None = None
_df_cuentas:   pd.DataFrame | None = None


def _cargar_impuestos() -> pd.DataFrame:
    global _df_impuestos
    if _df_impuestos is None:
        if not os.path.exists(_RUTA_IMPUESTOS):
            _df_impuestos = pd.DataFrame()
        else:
            hojas = pd.read_excel(_RUTA_IMPUESTOS, sheet_name=None, dtype=str)
            _df_impuestos = pd.concat(hojas.values(), ignore_index=True)
            _df_impuestos.columns = [_norm(c) for c in _df_impuestos.columns]
    return _df_impuestos


def _cargar_cuentas() -> pd.DataFrame:
    global _df_cuentas
    if _df_cuentas is None:
        if not os.path.exists(_RUTA_CUENTAS):
            _df_cuentas = pd.DataFrame()
        else:
            hojas = pd.read_excel(_RUTA_CUENTAS, sheet_name=None, dtype=str)
            _df_cuentas = pd.concat(hojas.values(), ignore_index=True)
            _df_cuentas.columns = [_norm(c) for c in _df_cuentas.columns]
    return _df_cuentas


def archivo_cuentas_disponible() -> bool:
    return os.path.exists(_RUTA_CUENTAS)


def archivo_impuestos_disponible() -> bool:
    return os.path.exists(_RUTA_IMPUESTOS)


def _norm(texto: str) -> str:
    """Minúsculas, sin acentos, sin caracteres especiales."""
    nfkd = unicodedata.normalize("NFKD", str(texto).lower())
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", sin_acentos).strip()


# ── Impuestos ─────────────────────────────────────────────────────────────────

def _col_impuestos(df: pd.DataFrame) -> dict[str, str | None]:
    """Detecta columnas de codigos_impuestos.xlsx con normalización de acentos."""
    norms = {c: _norm(c) for c in df.columns}

    def _find(cond) -> str | None:
        return next((c for c, n in norms.items() if cond(n)), None)

    return {
        "cod":         _find(lambda n: n in ("codigo", "cod") or ("codigo" == n)),
        "tarifa":      _find(lambda n: n == "tarifa" or ("tarifa" in n and "descripcion" not in n)),
        "tipo":        _find(lambda n: "tipo" in n and "impuesto" in n),
        "cta_compras": _find(lambda n: "compras" in n and "dev" not in n and "descripcion" not in n),
    }


def buscar_impuesto(cod_impuesto: str) -> dict | None:
    """
    Busca en codigos_impuestos.xlsx por código numérico SIIGO.
    Retorna dict con: cod, porcentaje, cuenta_debito, cuenta_credito, naturaleza.
    - IVA/Impoconsumo: cuenta_debito = Cta. Compras (IVA descontable)
    - Retenciones:     cuenta_credito = Cta. Compras (retención a pagar)
    """
    df = _cargar_impuestos()
    cod_n = _norm(str(cod_impuesto))
    cols = _col_impuestos(df)

    if not cols["cod"]:
        return None

    fila = df[df[cols["cod"]].apply(lambda v: _norm(str(v))) == cod_n]
    if fila.empty:
        return None

    row = fila.iloc[0]
    tipo = str(row[cols["tipo"]]).strip() if cols["tipo"] else ""
    cta = str(row[cols["cta_compras"]]).strip() if cols["cta_compras"] else ""
    es_ret = any(t in tipo.lower() for t in ("retefuente", "reteica", "reteiva"))

    return {
        "cod":            str(row[cols["cod"]]).strip(),
        "porcentaje":     _to_float(row[cols["tarifa"]]) if cols["tarifa"] else 0.0,
        "cuenta_debito":  cta if not es_ret else "",
        "cuenta_credito": cta if es_ret else "",
        "naturaleza":     tipo,
    }


def listar_impuestos() -> list[dict]:
    """Retorna todos los códigos de impuesto disponibles."""
    df = _cargar_impuestos()
    cols = _col_impuestos(df)

    if not cols["cod"]:
        return []

    result = []
    for _, row in df.iterrows():
        cod = str(row[cols["cod"]]).strip()
        if not cod or cod.lower() == "nan":
            continue
        tipo = str(row[cols["tipo"]]).strip() if cols["tipo"] else ""
        cta = str(row[cols["cta_compras"]]).strip() if cols["cta_compras"] else ""
        es_ret = any(t in tipo.lower() for t in ("retefuente", "reteica", "reteiva"))
        result.append({
            "cod":            cod,
            "porcentaje":     _to_float(row[cols["tarifa"]]) if cols["tarifa"] else 0.0,
            "cuenta_debito":  cta if not es_ret else "",
            "cuenta_credito": cta if es_ret else "",
            "naturaleza":     tipo,
        })
    return result


# ── Plan de cuentas ───────────────────────────────────────────────────────────

def buscar_cuentas_sugeridas(descripcion: str, max_sugerencias: int = 3) -> list[dict]:
    """
    Busca en el plan de cuentas (Cuentas_contables.xlsx) cuentas que coincidan
    con palabras de la descripción.
    Retorna lista de {codigo, nombre, nivel}.
    """
    df = _cargar_cuentas()
    col_cod  = _detectar_col(df.columns, ["codigo", "cuenta", "puc", "code", "c digo"])
    col_nom  = _detectar_col(df.columns, ["nombre", "descripcion", "detalle", "name"])

    if not col_cod or not col_nom:
        return []

    palabras = [p for p in _norm(descripcion).split() if len(p) > 3]
    sugerencias = []

    for _, row in df.iterrows():
        nombre_n = _norm(str(row[col_nom]))
        score = sum(1 for p in palabras if p in nombre_n)
        if score > 0:
            sugerencias.append({
                "codigo": str(row[col_cod]).strip(),
                "nombre": str(row[col_nom]).strip(),
                "score":  score,
            })

    sugerencias.sort(key=lambda x: -x["score"])
    return sugerencias[:max_sugerencias]


def listar_cuentas_gasto() -> list[dict]:
    """
    Retorna cuentas de gastos y costos (clases 5, 6, 7) del PUC.
    Filtros: exactamente 8 dígitos, sin la palabra 'fiscal' en el nombre.
    """
    df = _cargar_cuentas()
    col_cod = _detectar_col(df.columns, ["codigo", "cuenta", "puc", "code"])
    col_nom = _detectar_col(df.columns, ["nombre", "descripcion", "detalle", "name"])

    if not col_cod:
        return []

    result = []
    for _, row in df.iterrows():
        cod = str(row[col_cod]).strip()
        nom = str(row[col_nom]).strip() if col_nom else ""
        if (
            len(cod) == 8
            and cod.isdigit()
            and cod[0] in ("5", "6", "7")
            and "fiscal" not in nom.lower()
        ):
            result.append({"codigo": cod, "nombre": nom})
    return result


def listar_metodos_pago() -> list[dict]:
    """
    Retorna cuentas de activos y pasivos del PUC usadas como método de pago
    (clases 1 y 2). Filtros: exactamente 8 dígitos, sin 'fiscal' en el nombre.
    """
    df = _cargar_cuentas()
    col_cod = _detectar_col(df.columns, ["codigo", "cuenta", "puc", "code"])
    col_nom = _detectar_col(df.columns, ["nombre", "descripcion", "detalle", "name"])

    if not col_cod:
        return []

    result = []
    for _, row in df.iterrows():
        cod = str(row[col_cod]).strip()
        nom = str(row[col_nom]).strip() if col_nom else ""
        if (
            len(cod) == 8
            and cod.isdigit()
            and cod[0] in ("1", "2")
            and "fiscal" not in nom.lower()
        ):
            result.append({"codigo": cod, "nombre": nom})
    return result


# ── Mapeo de cuenta de gasto para un ítem ────────────────────────────────────

def mapear_cuenta_gasto(nit: str, descripcion: str) -> tuple[str | None, list[dict], str]:
    """
    Intenta determinar la cuenta PUC de gasto para un ítem de factura.

    Retorna:
        (cuenta_auto, sugerencias, fuente)
        - cuenta_auto: código PUC si se encontró con certeza (DB aprendida), else None.
        - sugerencias: lista de {codigo, nombre} del plan de cuentas.
        - fuente: "aprendido" | "sugerido" | "manual"
    """
    # 1. Buscar en memoria aprendida
    cuenta_db = mem.buscar_mapeo_puc(nit, descripcion)
    if cuenta_db:
        return cuenta_db, [], "aprendido"

    # 2. Sugerir desde plan de cuentas (PostgreSQL)
    try:
        from db.session import SessionLocal
        from services import cuentas_service as _cs
        with SessionLocal() as _db:
            sugerencias = _cs.buscar_cuentas_sugeridas(_db, descripcion)
    except Exception:
        sugerencias = []
    if sugerencias:
        return None, sugerencias, "sugerido"

    return None, [], "manual"


# ── Cuenta del proveedor ──────────────────────────────────────────────────────

def cuenta_proveedor(nit: str, tipo_proveedor: str) -> str:
    """
    Retorna la cuenta contable del proveedor.
    Primero busca en la BD de proveedores aprendidos; si no, usa la regla PUC estándar.
    """
    prov = mem.get_proveedor(nit)
    if prov and prov.get("cuenta_pagar"):
        return prov["cuenta_pagar"]

    # Regla PUC Colombia estándar
    if tipo_proveedor == "natural":
        return "220510"
    return "220505"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detectar_col(columnas: list[str], pistas: list[str]) -> str | None:
    for col in columnas:
        for p in pistas:
            if p in col:
                return col
    return None


def _to_float(valor) -> float:
    if pd.isna(valor):
        return 0.0
    limpio = re.sub(r"[^\d.,\-]", "", str(valor)).replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def invalidar_cache() -> None:
    """Fuerza la recarga de los archivos base xlsx en el próximo acceso."""
    global _df_impuestos, _df_cuentas
    _df_impuestos = None
    _df_cuentas = None


def ruta_impuestos() -> str:
    return os.path.abspath(_RUTA_IMPUESTOS)


def ruta_cuentas() -> str:
    return os.path.abspath(_RUTA_CUENTAS)


def ruta_tipos() -> str:
    return os.path.abspath(_RUTA_TIPOS)


def archivo_tipos_disponible() -> bool:
    return os.path.exists(_RUTA_TIPOS)


# ── Tipos de comprobante contable ─────────────────────────────────────────────

def listar_tipos_comprobante() -> list[dict]:
    """Lee Tipos_comprobante_contable.xlsx. Detecta la fila de encabezados automáticamente."""
    if not os.path.exists(_RUTA_TIPOS):
        return []
    try:
        # Leer sin encabezado para localizar la fila del header
        # El header real tiene "Código del comprobante" Y "Título comprobante" en la misma fila
        df_raw = pd.read_excel(_RUTA_TIPOS, header=None, dtype=str)
        header_row = None
        for i, row in df_raw.iterrows():
            norms = [_norm(str(v)) for v in row if str(v).strip() not in ("nan", "")]
            tiene_codigo = any("codigo" in n and "comprobante" in n for n in norms)
            tiene_titulo = any("titulo" in n for n in norms)
            if tiene_codigo and tiene_titulo:
                header_row = i
                break

        if header_row is None:
            return []

        df = pd.read_excel(_RUTA_TIPOS, header=header_row, dtype=str)
        col_cod = next(
            (c for c in df.columns if "codigo" in _norm(c) and "comprobante" in _norm(c)),
            None,
        )
        col_tit = next(
            (c for c in df.columns if "titulo" in _norm(c)),
            None,
        )
        if not col_cod or not col_tit:
            return []

        result = []
        for _, row in df.iterrows():
            cod = str(row[col_cod]).strip()
            tit = str(row[col_tit]).strip()
            if cod and cod.lower() not in ("nan", "") and _norm(cod) != _norm(col_cod):
                result.append({"codigo": cod, "titulo": tit if tit.lower() != "nan" else ""})
        return result
    except Exception:
        return []


def agregar_tipo_comprobante(codigo: str, titulo: str) -> bool:
    """Agrega un nuevo tipo de comprobante al final del archivo xlsx.

    No modifica registros existentes. Retorna False si el código ya existe.
    """
    if not os.path.exists(_RUTA_TIPOS):
        return False
    try:
        existentes = listar_tipos_comprobante()
        if any(t["codigo"] == str(codigo).strip() for t in existentes):
            return False
        from openpyxl import load_workbook  # local import to avoid hard dependency at module level

        ruta = os.path.abspath(_RUTA_TIPOS)
        wb = load_workbook(ruta)
        ws = wb.active
        ws.append([str(codigo).strip(), str(titulo).strip(), "Editar"])
        wb.save(ruta)
        return True
    except Exception:
        return False
