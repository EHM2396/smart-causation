"""
Servicio de terceros: upsert de proveedor a partir de los datos de una factura.
Se invoca desde batch/generar cuando confirmar=True.
"""

from __future__ import annotations

import re
import unicodedata
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dv import calcular_dv, inferir_tipo_identificacion
from core.parser import _limpiar_telefono
from db.models.contabilidad import Proveedor
from db.models.geo import Ciudad, Departamento


def upsert_tercero(db: Session, empresa_id: int, factura: dict) -> Proveedor | None:
    """
    Crea o actualiza el Proveedor (tercero) a partir de los datos parseados
    de una factura de compra.

    Reglas de actualización:
    - Si el proveedor no existe: crea uno con todos los campos disponibles.
    - Si ya existe: actualiza los campos que vengan con valor Y sean diferentes
      al valor almacenado. Si coinciden, no genera escritura. Los campos
      exclusivamente manuales (cuenta_pagar, etc.) no están en el mapeo
      y nunca se sobreescriben.

    Returns:
        La instancia Proveedor creada o actualizada, o None si no hay NIT.
    """
    nit_raw = str(factura.get("nit") or "").strip()
    if not nit_raw:
        return None

    nit = re.sub(r"[^\d\-]", "", nit_raw)
    if not nit:
        return None

    tipo_proveedor = factura.get("tipo_proveedor") or "juridica"

    # Inferir tipo de identificación
    scheme_id = str(factura.get("tipo_identificacion_codigo") or "")
    tipo_identificacion = inferir_tipo_identificacion(scheme_id, tipo_proveedor) if scheme_id else None
    if tipo_identificacion is None:
        tipo_identificacion = 31 if tipo_proveedor == "juridica" else 13

    digito_verificacion = calcular_dv(nit, tipo_identificacion)

    ciudad     = _val(factura.get("ciudad"))
    departamento = _val(factura.get("departamento"))
    pais_codigo  = "Col"

    # Resolver códigos Siigo de departamento y ciudad desde la BD geo
    codigo_departamento, codigo_ciudad_siigo = _resolver_geo(
        db, ciudad, departamento, pais_codigo
    )

    # Separar nombres y apellidos para personas naturales
    nombres_tercero  = _val(factura.get("nombres_tercero"))
    apellidos_tercero = _val(factura.get("apellidos_tercero"))
    if tipo_proveedor == "natural" and not nombres_tercero:
        razon = _val(factura.get("razon_social"))
        if razon:
            nombres_tercero, apellidos_tercero = _split_nombre_natural(razon)

    campos = {
        "razon_social":           _val(factura.get("razon_social")),
        "nombre_comercial":       _val(factura.get("nombre_comercial")),
        "tipo_persona":           tipo_proveedor,
        "tipo_identificacion":    tipo_identificacion,
        "digito_verificacion":    digito_verificacion,
        "ciudad":                 ciudad,
        "departamento":           departamento,
        "codigo_pais":            pais_codigo,
        "codigo_departamento":    codigo_departamento,
        "codigo_ciudad_siigo":    codigo_ciudad_siigo,
        "direccion":              _val(factura.get("direccion")),
        "codigo_postal":          _val(factura.get("codigo_postal")),
        "telefono":               _phone(factura.get("telefono")),
        "email":                  _val(factura.get("email")),
        "nombres_tercero":        nombres_tercero,
        "apellidos_tercero":      apellidos_tercero,
        "tipo_regimen_iva":       _val(factura.get("tipo_regimen_iva")),
        "codigo_responsabilidad": _val(factura.get("codigo_responsabilidad")),
        "fuente":                 _val(factura.get("_fuente")) or "pdf",
    }

    existing = db.scalar(
        select(Proveedor).where(
            Proveedor.nit == nit,
            Proveedor.empresa_id == empresa_id,
        )
    )

    if existing is None:
        prov = Proveedor(
            nit=nit,
            empresa_id=empresa_id,
            activo=True,
            es_cliente=False,
        )
        for field, value in campos.items():
            if value is not None:
                setattr(prov, field, value)
        db.add(prov)
        db.flush()  # visible en la misma sesión para llamadas posteriores del mismo batch
        return prov

    # Reactivar si estaba desactivado (eliminado desde la UI)
    if not existing.activo:
        existing.activo = True

    # Actualizar campos que traigan valor nuevo diferente al almacenado.
    # Campos sin valor en la factura (None) no tocan lo que ya hay.
    for field, value in campos.items():
        if value is not None and getattr(existing, field, None) != value:
            setattr(existing, field, value)

    return existing


# ─── helpers ──────────────────────────────────────────────────────────────────

def _norm_geo(s: str | None) -> str:
    """Normaliza un nombre geográfico: sin acentos, sin puntuación, minúsculas."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))  # quitar acentos
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# Alias de ciudades colombianas: nombre OFICIAL/largo (como suele venir en el
# CityName de la factura DIAN) → nombre corto sembrado en la tabla de ciudades.
# Ya normalizados (sin acentos/puntuación) para comparar directo.
_ALIAS_CIUDAD: dict[str, str] = {
    "santiago de cali": "cali",
    "san jose de cucuta": "cucuta",
    "san juan de pasto": "pasto",
    "santa fe de bogota": "bogota",
    "san sebastian de mariquita": "mariquita",
}


def _norm_depto(s: str | None) -> str:
    """Como _norm_geo pero quitando adornos comunes de departamento
    (D.C., 'distrito capital', 'departamento de'…) para que 'Bogotá, D.C.',
    'Bogotá D.C.' y 'Bogotá' colapsen al mismo valor."""
    n = _norm_geo(s)
    n = re.sub(r"\b(distrito capital|departamento del|departamento de|dpto del|dpto de|dpto|d c|dc)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


# Caché en memoria de la geografía (datos estáticos sembrados por scripts/seed_geo).
_GEO_CACHE: dict | None = None


def _build_geo_cache(db: Session) -> dict:
    # Las tablas geo guardan departamentos/ciudades de más de 150 países (para los
    # selectores de país en el formulario de terceros), no solo Colombia: 3106
    # departamentos y 4588 ciudades en total, de los cuales solo 33 y 1120 son
    # colombianos. Este resolver SIEMPRE es para proveedores colombianos
    # (upsert_tercero fija pais_codigo="Col"), así que se acota la búsqueda a
    # Colombia. Sin este filtro, un nombre de ciudad colombiana que coincide con
    # el de otra ciudad en el mundo (p. ej. "Independencia", "La Paz", "Santa
    # Rosa" — ~7% de las ciudades colombianas colisionan con otro país) vuelve
    # ambigua la búsqueda y el código de ciudad queda vacío de forma intermitente.
    deptos = db.scalars(select(Departamento).where(Departamento.pais_codigo == "Col")).all()
    ciudades = db.scalars(select(Ciudad).where(Ciudad.pais_codigo == "Col")).all()
    depto_by_norm: dict[str, str] = {}
    for d in deptos:
        key = _norm_depto(d.nombre)
        if key:
            depto_by_norm.setdefault(key, d.codigo)
    ciudad_by_depto: dict[tuple[str, str], str] = {}
    ciudad_by_norm: dict[str, list[tuple[str, str]]] = {}
    ciudades_por_depto: dict[str, list[str]] = {}
    for c in ciudades:
        ck = _norm_geo(c.nombre)
        if not ck:
            continue
        ciudad_by_depto[(c.departamento_codigo, ck)] = c.codigo
        ciudad_by_norm.setdefault(ck, []).append((c.codigo, c.departamento_codigo))
        ciudades_por_depto.setdefault(c.departamento_codigo, []).append(c.codigo)
    # Departamentos con UN solo municipio posible (p. ej. Bogotá D.C. → 11001): si
    # el nombre de ciudad del XML no calza (algunas facturas ponen literalmente
    # "Bogotá, D.C." como ciudad, que no matchea "Bogotá"), no hay ambigüedad
    # posible y se puede asignar directo.
    ciudad_unica_por_depto = {d: cs[0] for d, cs in ciudades_por_depto.items() if len(cs) == 1}
    return {
        "depto": depto_by_norm,
        "ciudad_depto": ciudad_by_depto,
        "ciudad": ciudad_by_norm,
        "ciudad_unica_por_depto": ciudad_unica_por_depto,
    }


def _get_geo_cache(db: Session) -> dict:
    global _GEO_CACHE
    if _GEO_CACHE is None:
        cache = _build_geo_cache(db)
        if cache["depto"]:  # solo cachear si la geo está sembrada
            _GEO_CACHE = cache
        return cache
    return _GEO_CACHE


def _resolver_geo(
    db: Session,
    ciudad: str | None,
    departamento: str | None,
    pais_codigo: str = "Col",
) -> tuple[str | None, str | None]:
    """Devuelve (codigo_departamento, codigo_ciudad_siigo) buscando por nombre,
    tolerante a acentos, puntuación y variantes ('BOGOTÁ' / 'Bogotá, D.C.')."""
    cache = _get_geo_cache(db)
    codigo_depto: str | None = None
    codigo_ciudad: str | None = None

    ndepto = _norm_depto(departamento)
    if ndepto:
        codigo_depto = cache["depto"].get(ndepto)

    nciudad = _norm_geo(ciudad)
    nciudad = _ALIAS_CIUDAD.get(nciudad, nciudad)
    if nciudad:
        if codigo_depto:
            codigo_ciudad = cache["ciudad_depto"].get((codigo_depto, nciudad))
        if codigo_ciudad is None:
            # Fallback: ciudad por nombre en todo el país; si es única, se usa.
            # La ciudad encontrada MANDA sobre el departamento: su código de
            # municipio ya codifica el departamento, así que se alinea siempre
            # (evita combinaciones inconsistentes como depto 17 + municipio 76001
            # = Cali, que SIIGO rechaza).
            matches = cache["ciudad"].get(nciudad, [])
            if len(matches) == 1:
                codigo_ciudad, depto_de_ciudad = matches[0]
                codigo_depto = depto_de_ciudad

    # Último recurso: el departamento se identificó pero el nombre de ciudad no
    # calzó con ninguno (p. ej. "Bogotá, D.C." como CIUDAD, no solo como
    # departamento). Si ese departamento tiene un único municipio posible, no hay
    # ambigüedad: se asigna directo en vez de dejar el campo vacío.
    if codigo_ciudad is None and codigo_depto:
        codigo_ciudad = cache["ciudad_unica_por_depto"].get(codigo_depto)

    return codigo_depto, codigo_ciudad


def _split_nombre_natural(nombre_completo: str) -> tuple[str | None, str | None]:
    """
    Divide nombre completo en (nombres, apellidos) siguiendo la convención DIAN:
    Primer nombre [Segundo nombre] Primer apellido [Segundo apellido].

    - 2 palabras: 1 nombre, 1 apellido
    - 3 palabras: 1 nombre, 2 apellidos  (patrón más común en Colombia)
    - 4+ palabras: 2 nombres, resto son apellidos
    """
    words = nombre_completo.strip().split()
    n = len(words)
    if n == 0:
        return None, None
    if n == 1:
        return words[0], None
    if n == 2:
        return words[0], words[1]
    if n == 3:
        return words[0], " ".join(words[1:])
    # 4 o más: primeras 2 = nombres, resto = apellidos
    return " ".join(words[:2]), " ".join(words[2:])


def _val(v) -> str | None:
    """Retorna None si el valor es vacío, de lo contrario el string limpio."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _phone(v) -> str | None:
    """Normaliza el teléfono (quita pipes, indicativos y código de país) y retorna
    None si el valor parece un email o está vacío."""
    s = _val(v)
    if s is None or "@" in s:
        return None
    return (_limpiar_telefono(s) or s)[:50]
