"""
Servicio de terceros: upsert de proveedor a partir de los datos de una factura.
Se invoca desde batch/generar cuando confirmar=True.
"""

from __future__ import annotations

import re
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.dv import calcular_dv, inferir_tipo_identificacion
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

def _resolver_geo(
    db: Session,
    ciudad: str | None,
    departamento: str | None,
    pais_codigo: str = "Col",
) -> tuple[str | None, str | None]:
    """Devuelve (codigo_departamento, codigo_ciudad_siigo) buscando por nombre."""
    codigo_depto = None
    codigo_ciudad = None

    if departamento:
        depto = db.scalar(
            select(Departamento).where(
                func.lower(Departamento.nombre) == departamento.strip().lower(),
                Departamento.pais_codigo == pais_codigo,
            )
        )
        if depto:
            codigo_depto = depto.codigo

    if ciudad and codigo_depto:
        ciu = db.scalar(
            select(Ciudad).where(
                func.lower(Ciudad.nombre) == ciudad.strip().lower(),
                Ciudad.departamento_codigo == codigo_depto,
                Ciudad.pais_codigo == pais_codigo,
            )
        )
        if ciu:
            codigo_ciudad = ciu.codigo

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
    """Retorna None si el valor parece un email o está vacío."""
    s = _val(v)
    if s is None or "@" in s:
        return None
    return s[:50]
