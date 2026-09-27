"""
El consolidado que ve el contador para clasificar operaciones a tarifa 0%.

La regla de presentación, confirmada por Andrés: "resumen primero, detalle bajo
demanda". El eje es el PROVEEDOR (el NIT predice el tratamiento mejor que el
texto de la descripción — un mismo proveedor de maquinaria factura acarreos
gravados aunque diga "transporte"), y dentro de cada proveedor se muestra el
concepto predominante por valor acumulado, con los secundarios de tratamiento
distinto siempre separados.

Lo que este archivo NUNCA hace: agrupar dos conceptos que puedan tener
tratamiento distinto bajo una sola cifra. Eso perdería información que el
Formulario 300 necesita, y es justamente lo que la especificación prohíbe.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.auth import Empresa, Usuario
from db.models.contabilidad import DocumentoDian
from services.analitica_service import SIGNO
from services.catalogo_tributario_service import (
    Clasificacion, buscar_en_catalogo, clasificar, normalizar_concepto,
    registrar_cambio, nueva_version,
)
from db.models.tributario import CatalogoTributario, ClasificacionEmpresa

# Documentos que corresponden a cada lado del Formulario 300. La pantalla de
# clasificación se separa en dos flujos porque en ventas EXENTO y EXCLUIDO
# nunca se agrupan, y en compras sí se agrupan en la presentación principal —
# mezclar ambos tipos de documento en una sola lista impedía aplicar esa
# regla de forma consistente.
TIPOS_VENTAS = ("ventas", "nc_ventas", "nd_ventas")
TIPOS_COMPRAS = ("compras", "nc", "nd", "soporte", "nc_soporte")


@dataclass
class ConceptoResumen:
    concepto: str
    concepto_norm: str
    nit_proveedor: str
    base_acumulada: float
    documentos: int
    clasificacion: Clasificacion
    # % del total del proveedor que representa este concepto — es lo que decide
    # cuál es el "predominante" y cuáles quedan de segundo plano en la pantalla.
    participacion: float = 0.0
    # Código/referencia del producto (si el XML lo trae). Se manda de vuelta al
    # validar, para que la memoria quede guardada a este nivel de detalle.
    referencia: str | None = None


@dataclass
class ProveedorResumen:
    nit: str
    razon_social: str
    base_total: float
    documentos: int
    predominante: ConceptoResumen
    secundarios: list[ConceptoResumen] = field(default_factory=list)
    # Tipos de documento DIAN que aportaron ítems a este proveedor en el
    # periodo — se usa en la pantalla para mostrar etiquetas que ayuden a
    # identificar si el proveedor vino de una factura, una nota o un soporte.
    tipos_documento: list[str] = field(default_factory=list)

    @property
    def pendientes(self) -> int:
        """Cuántos conceptos de este proveedor todavía no tienen una
        clasificación validada — es la cifra que le dice al contador cuánto
        trabajo le queda con este proveedor."""
        todos = [self.predominante, *self.secundarios]
        return sum(1 for c in todos if c.clasificacion.requiere_revision)


def resumen_por_proveedor(
    db: Session,
    *,
    empresa_ids: list[int],
    desde: date,
    hasta: date,
    tarifa: float = 0.0,
    todas_tarifas: bool = False,
    origen: str = "compras",
    cuenta_id: int | None = None,
) -> list[ProveedorResumen]:
    """Proveedores con operaciones a la `tarifa` dada, con sus conceptos
    clasificados y ordenados por peso económico.

    `origen` separa Ventas de Compras — son dos flujos de clasificación
    distintos (en ventas exento y excluido nunca se agrupan; en compras sí,
    en la presentación principal) y nunca se mezclan en una misma pantalla.

    `todas_tarifas` ignora el filtro de `tarifa` y trae conceptos de
    cualquier tarifa. Hace falta para la Fase 2 (IVA descontable): esa
    clasificación aplica sobre todo a los ítems GRAVADOS (5%/19%), que el
    filtro de tarifa=0% de siempre nunca mostraba — la pantalla de
    clasificación de tratamiento (exento/excluido/no gravado) seguía
    necesitando solo el 0%, así que ese filtro se mantiene por defecto.

    Se usa la fecha de EMISIÓN de cada documento para resolver el tratamiento
    vigente en ese momento — no la de hoy. Un documento de marzo se clasifica
    con la norma de marzo, aunque hoy rija una distinta.
    """
    if not empresa_ids:
        return []

    tipos = TIPOS_VENTAS if origen == "ventas" else TIPOS_COMPRAS

    docs = db.execute(
        select(DocumentoDian).where(
            DocumentoDian.empresa_id.in_(empresa_ids),
            DocumentoDian.tipo.in_(tipos),
            DocumentoDian.fecha_emision >= desde,
            DocumentoDian.fecha_emision <= hasta,
        )
    ).scalars().all()

    # (nit, concepto_norm) → acumulador. El nit es el eje; el concepto separa
    # dentro de él sin fusionar nada.
    acumulado: dict[tuple[str, str], dict] = {}
    # nit → tipos de documento DIAN que aportaron ítems al proveedor (solo los
    # que pasaron el filtro de tarifa — un soporte con tarifa 19% y sin ítems
    # al 0% no debe aparecer como etiqueta si no aporta nada a la vista).
    tipos_por_nit: dict[str, set[str]] = {}

    for doc in docs:
        if not doc.items_json:
            continue
        try:
            items = json.loads(doc.items_json)
        except ValueError:
            continue

        nit = (doc.nit_contraparte or "").strip()
        if not nit:
            continue
        fecha_doc = doc.fecha_emision or hasta

        for it in items:
            pct = it.get("porcentaje")
            try:
                pct = float(pct) if pct is not None else None
            except (TypeError, ValueError):
                pct = None
            if not todas_tarifas and (pct is None or round(pct, 2) != round(tarifa, 2)):
                continue
            if todas_tarifas and pct is None:
                continue  # sin tarifa conocida no se puede clasificar razonablemente

            concepto = str(it.get("descripcion") or "").strip()
            if not concepto:
                continue
            norm = normalizar_concepto(concepto)
            if not norm:
                continue

            # Registrar el tipo de documento solo cuando el ítem pasa el filtro.
            tipos_por_nit.setdefault(nit, set()).add(doc.tipo)

            base = float(it.get("base") or 0)
            referencia = str(it.get("referencia") or "").strip() or None
            clave = (nit, norm)
            acc = acumulado.setdefault(clave, {
                "concepto": concepto, "concepto_norm": norm, "nit": nit,
                "razon_social": doc.razon_social or "", "base": 0.0, "documentos": 0,
                "fecha_referencia": fecha_doc, "referencia": referencia, "pct": pct,
            })
            acc["base"] += base
            acc["documentos"] += 1
            # Se clasifica con la fecha del documento más ANTIGUO del grupo: si
            # una norma cambió a mitad de periodo, es la fecha más conservadora
            # la que decide qué tratamiento mostrar como sugerencia por defecto.
            if fecha_doc < acc["fecha_referencia"]:
                acc["fecha_referencia"] = fecha_doc
            if not acc["razon_social"] and doc.razon_social:
                acc["razon_social"] = doc.razon_social
            if not acc.get("referencia") and referencia:
                acc["referencia"] = referencia

    if not acumulado:
        return []

    conceptos_por_nit: dict[str, list[ConceptoResumen]] = {}
    razon_social_por_nit: dict[str, str] = {}

    for (nit, _norm), acc in acumulado.items():
        clas = clasificar(
            db, empresa_id=empresa_ids[0] if len(empresa_ids) == 1 else _empresa_de(db, empresa_ids, nit),
            concepto=acc["concepto"], fecha=acc["fecha_referencia"],
            nit_tercero=nit, referencia=acc.get("referencia"), pct=acc.get("pct"),
            cuenta_id=cuenta_id,
        )
        cr = ConceptoResumen(
            concepto=acc["concepto"], concepto_norm=acc["concepto_norm"], nit_proveedor=nit,
            base_acumulada=round(acc["base"], 2), documentos=acc["documentos"], clasificacion=clas,
            referencia=acc.get("referencia"),
        )
        conceptos_por_nit.setdefault(nit, []).append(cr)
        razon_social_por_nit[nit] = acc["razon_social"]

    _orden_tipos = {t: i for i, t in enumerate(TIPOS_VENTAS + TIPOS_COMPRAS)}

    proveedores: list[ProveedorResumen] = []
    for nit, conceptos in conceptos_por_nit.items():
        base_total = sum(c.base_acumulada for c in conceptos)
        for c in conceptos:
            c.participacion = round((c.base_acumulada / base_total) * 100, 1) if base_total else 0.0
        conceptos.sort(key=lambda c: c.base_acumulada, reverse=True)

        proveedores.append(ProveedorResumen(
            nit=nit,
            razon_social=razon_social_por_nit.get(nit) or "—",
            base_total=round(base_total, 2),
            documentos=sum(c.documentos for c in conceptos),
            predominante=conceptos[0],
            secundarios=conceptos[1:],
            tipos_documento=sorted(tipos_por_nit.get(nit, set()), key=lambda t: _orden_tipos.get(t, 99)),
        ))

    proveedores.sort(key=lambda p: p.base_total, reverse=True)
    return proveedores


def _empresa_de(db: Session, empresa_ids: list[int], nit: str) -> int:
    """Cuando se consolidan varias empresas a la vez, cada concepto se clasifica
    con la primera empresa de la lista que tenga ese proveedor — es una
    aproximación razonable para la vista consolidada; el detalle por empresa usa
    siempre su propio empresa_id."""
    fila = db.scalar(
        select(DocumentoDian.empresa_id)
        .where(DocumentoDian.empresa_id.in_(empresa_ids), DocumentoDian.nit_contraparte == nit)
        .limit(1)
    )
    return fila or empresa_ids[0]


# ── Reporte consolidado por categoría (Fase 4) ───────────────────────────────

# Categorías que puede tomar un concepto en el reporte. "pendiente" agrupa
# los ítems al 0% que todavía no tienen clasificación validada ni sugerida.
_CATS_REPORTE = ("gravado_general", "gravado_5", "exento", "excluido", "no_gravado", "pendiente")

# Etiquetas para el reporte (Excel/PDF/pantalla).
CATS_LABEL = {
    "gravado_general": "Gravado (tarifa general)",
    "gravado_5": "Gravado (5%)",
    "exento": "Exento",
    "excluido": "Excluido",
    "no_gravado": "No gravado",
    "pendiente": "Pendiente de clasificar",
}


def _reporte_vacio(desde: date | None = None, hasta: date | None = None) -> dict:
    return {
        "periodo": {
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
        },
        "ventas": {cat: {"base": 0.0, "iva": 0.0} for cat in _CATS_REPORTE},
        "compras": {cat: {"base": 0.0, "iva_facturado": 0.0, "iva_descontable": 0.0} for cat in _CATS_REPORTE},
        "devoluciones": {
            "ventas": {"base": 0.0, "iva": 0.0},
            "compras": {"base": 0.0, "iva_facturado": 0.0, "iva_descontable": 0.0},
        },
        "totales": {"iva_generado": 0.0, "iva_descontable": 0.0, "balance_analitico_iva": 0.0},
        "conceptos_pendientes": 0,
    }


def reporte_resumen(
    db: Session,
    *,
    empresa_ids: list[int],
    desde: date,
    hasta: date,
    cuenta_id: int | None = None,
) -> dict:
    """Resumen consolidado de operaciones por categoría tributaria, listo para
    construir el reporte del Formulario 300.

    Separa ventas y compras. Dentro de cada lado:
    - Ítems con tarifa ≠ 0% se resuelven directamente por tarifa (gravado_5 /
      gravado_general) sin necesitar clasificación manual.
    - Ítems con tarifa 0% usan la clasificación guardada en la empresa
      (exento / excluido / no_gravado). Los que todavía no tienen tratamiento
      van al bucket "pendiente".

    Para compras, el IVA descontable se toma de la clasificación: los ítems
    gravados (5%/19%) se marcan como descontable automáticamente; los exentos
    y excluidos, como no descontable.
    """
    if not empresa_ids:
        return _reporte_vacio(desde, hasta)

    docs = db.execute(
        select(DocumentoDian).where(
            DocumentoDian.empresa_id.in_(empresa_ids),
            DocumentoDian.tipo.in_(TIPOS_VENTAS + TIPOS_COMPRAS),
            DocumentoDian.fecha_emision >= desde,
            DocumentoDian.fecha_emision <= hasta,
        )
    ).scalars().all()

    v = {cat: {"base": 0.0, "iva": 0.0} for cat in _CATS_REPORTE}
    c = {cat: {"base": 0.0, "iva_facturado": 0.0, "iva_descontable": 0.0} for cat in _CATS_REPORTE}
    # Devoluciones (NC) separadas para mostrar bruto - devolucion = neto
    dev_v = {"base": 0.0, "iva": 0.0}
    dev_c = {"base": 0.0, "iva_facturado": 0.0, "iva_descontable": 0.0}

    # Ítems al 0%: se agrupan por (es_venta, nit, concepto_norm) para
    # llamar a clasificar() UNA vez por par — evita N consultas por ítem.
    pending: dict[tuple, dict] = {}

    for doc in docs:
        if not doc.items_json:
            continue
        try:
            items = json.loads(doc.items_json)
        except ValueError:
            continue

        signo = SIGNO.get(doc.tipo, 1)
        es_venta = doc.tipo in TIPOS_VENTAS
        es_nc = signo < 0  # NC/ajuste — devolucion
        nit = (doc.nit_contraparte or "").strip()
        fecha_doc = doc.fecha_emision or hasta

        for it in items:
            pct_raw = it.get("porcentaje")
            try:
                pct = float(pct_raw) if pct_raw is not None else None
            except (TypeError, ValueError):
                pct = None
            if pct is None:
                continue

            base = signo * float(it.get("base") or 0)
            iva = signo * float(it.get("valor_impuesto") or 0)
            pct_r = round(pct, 2)

            if pct_r != 0.0:
                cat = "gravado_5" if pct_r == 5.0 else "gravado_general"
                if es_venta:
                    v[cat]["base"] += base
                    v[cat]["iva"] += iva
                    if es_nc:
                        dev_v["base"] += abs(base)
                        dev_v["iva"] += abs(iva)
                else:
                    c[cat]["base"] += base
                    c[cat]["iva_facturado"] += iva
                    c[cat]["iva_descontable"] += iva  # gravado → descontable por defecto
                    if es_nc:
                        dev_c["base"] += abs(base)
                        dev_c["iva_facturado"] += abs(iva)
                        dev_c["iva_descontable"] += abs(iva)
            else:
                if not nit:
                    continue
                concepto = str(it.get("descripcion") or "").strip()
                if not concepto:
                    continue
                norm = normalizar_concepto(concepto)
                if not norm:
                    continue
                referencia = str(it.get("referencia") or "").strip() or None
                clave = (es_venta, nit, norm)
                acc = pending.setdefault(clave, {
                    "es_venta": es_venta, "nit": nit, "concepto": concepto,
                    "referencia": referencia, "fecha": fecha_doc, "pct": pct,
                    "base": 0.0, "iva": 0.0, "nc_base": 0.0, "nc_iva": 0.0,
                })
                acc["base"] += base
                acc["iva"] += iva
                if es_nc:
                    acc["nc_base"] += abs(base)
                    acc["nc_iva"] += abs(iva)
                if fecha_doc < acc["fecha"]:
                    acc["fecha"] = fecha_doc
                if not acc.get("referencia") and referencia:
                    acc["referencia"] = referencia

    conceptos_pendientes = 0
    for (es_venta, nit, _norm), acc in pending.items():
        empresa_id = empresa_ids[0] if len(empresa_ids) == 1 else _empresa_de(db, empresa_ids, nit)
        clas = clasificar(
            db, empresa_id=empresa_id, concepto=acc["concepto"],
            fecha=acc["fecha"], nit_tercero=nit,
            referencia=acc.get("referencia"), pct=acc.get("pct"),
            cuenta_id=cuenta_id,
        )
        t = clas.tratamiento
        cat = t if t in _CATS_REPORTE else "pendiente"
        if cat == "pendiente":
            conceptos_pendientes += 1

        if es_venta:
            v[cat]["base"] += acc["base"]
            v[cat]["iva"] += acc["iva"]
            dev_v["base"] += acc["nc_base"]
            dev_v["iva"] += acc["nc_iva"]
        else:
            c[cat]["base"] += acc["base"]
            c[cat]["iva_facturado"] += acc["iva"]
            if clas.iva_descontable == "descontable":
                c[cat]["iva_descontable"] += acc["iva"]
            dev_c["base"] += acc["nc_base"]
            dev_c["iva_facturado"] += acc["nc_iva"]

    for cat in _CATS_REPORTE:
        for k in v[cat]:
            v[cat][k] = round(v[cat][k], 2)
        for k in c[cat]:
            c[cat][k] = round(c[cat][k], 2)

    iva_generado = sum(v[cat]["iva"] for cat in _CATS_REPORTE)
    iva_descontable_total = sum(c[cat]["iva_descontable"] for cat in _CATS_REPORTE)

    return {
        "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        "ventas": v,
        "compras": c,
        "devoluciones": {
            "ventas": {k: round(val, 2) for k, val in dev_v.items()},
            "compras": {k: round(val, 2) for k, val in dev_c.items()},
        },
        "totales": {
            "iva_generado": round(iva_generado, 2),
            "iva_descontable": round(iva_descontable_total, 2),
            "balance_analitico_iva": round(iva_generado - iva_descontable_total, 2),
        },
        "conceptos_pendientes": conceptos_pendientes,
    }


# ── Tributos adicionales (INC, IBUA, ICUI, INPP, bolsas, etc.) ───────────────

def tributos_adicionales_resumen(
    db: Session,
    *,
    empresa_ids: list[int],
    desde: date,
    hasta: date,
    cuenta_id: int,
) -> dict:
    """Consolida todos los tributos distintos al IVA que aparecen en los XML
    del periodo.  Separa compras de ventas; agrupa por código DIAN; mantiene
    el desglose por proveedor para el drilldown.

    Ningún tributo se pierde: los códigos no reconocidos quedan como
    ``conocido=False`` y se marcan como 'Tributo no parametrizado (XXXX)'."""
    from core.parser import clasificar_tributo_dian

    _vacio = {
        "periodo": {
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
        },
        "compras": [],
        "ventas": [],
        "total_compras": 0.0,
        "total_ventas": 0.0,
        "hay_no_parametrizados": False,
    }
    if not empresa_ids:
        return _vacio

    docs = db.execute(
        select(DocumentoDian).where(
            DocumentoDian.empresa_id.in_(empresa_ids),
            DocumentoDian.fecha_emision >= desde,
            DocumentoDian.fecha_emision <= hasta,
        )
    ).scalars().all()

    # acc[lado][cod_dian] = {nombre, grupo, conocido, valor_total, por_nit: {...}}
    acc: dict[str, dict[str, dict]] = {"ventas": {}, "compras": {}}

    for doc in docs:
        es_venta = doc.tipo in TIPOS_VENTAS
        lado = "ventas" if es_venta else "compras"
        signo = SIGNO.get(doc.tipo, 1)

        try:
            items = json.loads(doc.items_json or "[]")
        except (ValueError, TypeError):
            continue

        for it in items:
            for trib in (it.get("otros_tributos") or []):
                cod = str(trib.get("cod_dian") or "??").strip()
                valor = float(trib.get("valor") or 0) * signo

                if cod not in acc[lado]:
                    nombre, grupo, conocido = clasificar_tributo_dian(cod)
                    if not conocido:
                        nombre = f"Tributo no parametrizado ({cod})"
                    acc[lado][cod] = {
                        "cod_dian": cod,
                        "nombre": nombre,
                        "grupo": grupo,
                        "conocido": conocido,
                        "valor_total": 0.0,
                        "por_nit": {},
                    }

                acc[lado][cod]["valor_total"] += valor

                nit = doc.nit_contraparte or "SIN NIT"
                if nit not in acc[lado][cod]["por_nit"]:
                    acc[lado][cod]["por_nit"][nit] = {
                        "nit": nit,
                        "razon_social": doc.razon_social or "",
                        "valor": 0.0,
                        "documentos": 0,
                    }
                acc[lado][cod]["por_nit"][nit]["valor"] += valor
                acc[lado][cod]["por_nit"][nit]["documentos"] += 1

    def _serializar(lado_dict: dict) -> list[dict]:
        out = []
        for entry in sorted(lado_dict.values(), key=lambda e: e["valor_total"], reverse=True):
            por_prov = sorted(entry["por_nit"].values(), key=lambda p: p["valor"], reverse=True)
            out.append({
                "cod_dian": entry["cod_dian"],
                "nombre": entry["nombre"],
                "grupo": entry["grupo"],
                "conocido": entry["conocido"],
                "valor_total": round(entry["valor_total"], 2),
                "por_proveedor": [
                    {**p, "valor": round(p["valor"], 2)}
                    for p in por_prov
                ],
            })
        return out

    compras = _serializar(acc["compras"])
    ventas = _serializar(acc["ventas"])

    return {
        "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        "compras": compras,
        "ventas": ventas,
        "total_compras": round(sum(e["valor_total"] for e in compras), 2),
        "total_ventas": round(sum(e["valor_total"] for e in ventas), 2),
        "hay_no_parametrizados": any(not e["conocido"] for e in compras + ventas),
    }


# ── Balance de IVA (Fase 3) ──────────────────────────────────────────────────

def _balance_vacio() -> dict:
    return {
        "iva_generado": 0.0, "iva_facturado_compras": 0.0, "iva_descontable": 0.0,
        "balance_analitico_iva": 0.0, "documentos_ventas": 0, "documentos_compras": 0,
    }


def balance_iva(
    db: Session, *, empresa_ids: list[int], desde: date, hasta: date, cuenta_id: int | None = None,
) -> dict:
    """IVA generado (ventas) contra IVA descontable (compras), para el periodo.

    Se llama "BALANCE ANALÍTICO DE IVA" a propósito, en todo el sistema —
    nunca "saldo a pagar" ni "saldo a favor": el resultado fiscal definitivo
    del Formulario 300 depende de otros conceptos de la liquidación que este
    número no cubre (ver Fase 5 y 6 del plan: AIU, importaciones, zonas
    francas, reconciliación con las casillas del formulario).

    El IVA generado se toma tal cual viene facturado (no hay nada que
    clasificar en una venta). El IVA descontable, en cambio, usa la MISMA
    clasificación de la pantalla de compras (Fase 2): solo cuenta el IVA de
    los conceptos que están —confirmados o sugeridos— como "descontable". Un
    concepto sin clasificar todavía no suma acá, tal como pide Andrés: no
    asumir automáticamente que todo IVA de una compra es descontable.
    """
    if not empresa_ids:
        return _balance_vacio()

    docs = db.execute(
        select(DocumentoDian).where(
            DocumentoDian.empresa_id.in_(empresa_ids),
            DocumentoDian.tipo.in_(TIPOS_VENTAS + TIPOS_COMPRAS),
            DocumentoDian.fecha_emision >= desde,
            DocumentoDian.fecha_emision <= hasta,
        )
    ).scalars().all()

    iva_generado = 0.0
    documentos_ventas = documentos_compras = 0

    # Los ítems de compra se agrupan por (nit, concepto) para resolver la
    # clasificación UNA vez por concepto — el mismo concepto puede repetirse
    # en decenas de documentos, y no hace falta preguntarle al mismo tratamiento
    # una vez por cada línea.
    acumulado_compras: dict[tuple[str, str], dict] = {}

    for doc in docs:
        if not doc.items_json:
            continue
        try:
            items = json.loads(doc.items_json)
        except ValueError:
            continue

        signo = SIGNO.get(doc.tipo, 1)

        if doc.tipo in TIPOS_VENTAS:
            documentos_ventas += 1
            for it in items:
                iva_generado += signo * float(it.get("valor_impuesto") or 0)
            continue

        documentos_compras += 1
        nit = (doc.nit_contraparte or "").strip()
        if not nit:
            continue
        fecha_doc = doc.fecha_emision or hasta

        for it in items:
            concepto = str(it.get("descripcion") or "").strip()
            if not concepto:
                continue
            norm = normalizar_concepto(concepto)
            if not norm:
                continue

            pct = it.get("porcentaje")
            try:
                pct = float(pct) if pct is not None else None
            except (TypeError, ValueError):
                pct = None
            referencia = str(it.get("referencia") or "").strip() or None

            clave = (nit, norm)
            acc = acumulado_compras.setdefault(clave, {
                "concepto": concepto, "nit": nit, "fecha_referencia": fecha_doc,
                "referencia": referencia, "pct": pct, "iva": 0.0,
            })
            acc["iva"] += signo * float(it.get("valor_impuesto") or 0)
            if fecha_doc < acc["fecha_referencia"]:
                acc["fecha_referencia"] = fecha_doc
            if not acc.get("referencia") and referencia:
                acc["referencia"] = referencia
            if acc.get("pct") is None:
                acc["pct"] = pct

    iva_facturado_compras = sum(acc["iva"] for acc in acumulado_compras.values())

    iva_descontable = 0.0
    for (nit, _norm), acc in acumulado_compras.items():
        clas = clasificar(
            db, empresa_id=empresa_ids[0] if len(empresa_ids) == 1 else _empresa_de(db, empresa_ids, nit),
            concepto=acc["concepto"], fecha=acc["fecha_referencia"],
            nit_tercero=nit, referencia=acc.get("referencia"), pct=acc.get("pct"),
            cuenta_id=cuenta_id,
        )
        if clas.iva_descontable == "descontable":
            iva_descontable += acc["iva"]

    return {
        "iva_generado": round(iva_generado, 2),
        "iva_facturado_compras": round(iva_facturado_compras, 2),
        "iva_descontable": round(iva_descontable, 2),
        "balance_analitico_iva": round(iva_generado - iva_descontable, 2),
        "documentos_ventas": documentos_ventas,
        "documentos_compras": documentos_compras,
    }


# ── Validar una clasificación ────────────────────────────────────────────────

def validar_clasificacion(
    db: Session,
    *,
    empresa: Empresa,
    usuario: Usuario,
    concepto: str,
    tratamiento: str,
    nit_tercero: str | None = None,
    referencia: str | None = None,
    tipo_item: str | None = None,
    iva_descontable: str | None = None,
    articulo_et: str | None = None,
    norma: str | None = None,
) -> ClasificacionEmpresa:
    """El contador confirma (o corrige) el tratamiento de un concepto para esta
    empresa, y de paso puede confirmar si es bien o servicio (`tipo_item`) o
    si el IVA facturado cuenta como descontable (`iva_descontable`) —
    opcionales, son ejes independientes, pero se guardan en la misma fila
    porque se clasifican al mismo nivel: proveedor + referencia + concepto.

    `iva_descontable` NUNCA se propaga al catálogo de la firma, ni siquiera
    sin `nit_tercero`: a diferencia del tratamiento de IVA (una regla
    normativa, válida para cualquier empresa que compre lo mismo), si un IVA
    es descontable depende de la situación propia de CADA empresa — no es
    algo que otra empresa de la cuenta deba heredar como sugerencia.

    Si la validación NO está atada a un proveedor puntual (`nit_tercero=None`),
    también enriquece el catálogo de la firma: es una regla general del
    concepto, y las demás empresas de la misma cuenta la ven después como
    sugerencia. Si SÍ está atada a un proveedor, queda como una excepción propia
    de esa relación comercial y no se comparte — generalizarla podría
    equivocarse con otro proveedor que factura el mismo texto por algo distinto.

    La `referencia` (código de producto) se guarda junto con el tratamiento:
    es lo que afina la memoria cuando el mismo proveedor vende bienes y
    servicios distintos con descripciones parecidas.
    """
    norm = normalizar_concepto(concepto)
    ref = (referencia or "").strip() or None
    ahora = datetime.now(timezone.utc)
    hoy = ahora.date()

    sugerencia = buscar_en_catalogo(db, concepto=concepto, fecha=hoy, cuenta_id=empresa.cuenta_id)
    es_excepcion = sugerencia is not None and sugerencia.tratamiento != tratamiento

    fila = ClasificacionEmpresa(
        empresa_id=empresa.id, nit_tercero=nit_tercero, referencia=ref,
        concepto_norm=norm, concepto=concepto, tratamiento=tratamiento,
        tipo_item=tipo_item, iva_descontable=iva_descontable,
        origen="manual", estado="validada",
        catalogo_id=sugerencia.id if sugerencia else None,
        es_excepcion=es_excepcion,
        articulo_et=articulo_et, norma=norma,
        validado_por=usuario.id, validado_at=ahora,
    )
    db.add(fila)
    db.flush()

    if nit_tercero is None and empresa.cuenta_id is not None:
        _propagar_al_catalogo_de_la_firma(
            db, cuenta_id=empresa.cuenta_id, empresa_nombre=empresa.nombre,
            concepto=concepto, norm=norm, tratamiento=tratamiento,
            usuario=usuario, articulo_et=articulo_et, norma_texto=norma, hoy=hoy,
        )

    db.commit()
    db.refresh(fila)
    return fila


def _propagar_al_catalogo_de_la_firma(
    db: Session, *, cuenta_id: int, empresa_nombre: str, concepto: str, norm: str,
    tratamiento: str, usuario: Usuario, articulo_et: str | None, norma_texto: str | None, hoy: date,
) -> None:
    vigente = db.scalar(
        select(CatalogoTributario).where(
            CatalogoTributario.concepto_norm == norm,
            CatalogoTributario.cuenta_id == cuenta_id,
            CatalogoTributario.vigencia_hasta.is_(None),
        )
    )
    if vigente is None:
        nueva = CatalogoTributario(
            cuenta_id=cuenta_id, concepto=concepto, concepto_norm=norm,
            tratamiento=tratamiento, articulo_et=articulo_et, fuente_normativa=norma_texto,
            estado="validada", validado_por=usuario.id, validado_at=datetime.now(timezone.utc),
        )
        db.add(nueva)
        db.flush()
        registrar_cambio(
            db, catalogo=nueva, usuario_id=usuario.id, accion="creada",
            detalle=f"Validado por {usuario.nombre} al clasificar {empresa_nombre}", norma=norma_texto,
        )
    elif vigente.tratamiento != tratamiento:
        nueva_version(
            db, anterior=vigente, tratamiento=tratamiento, rige_desde=hoy,
            usuario_id=usuario.id, articulo_et=articulo_et, norma=norma_texto,
            observaciones=f"Cambiado al validar {empresa_nombre}",
        )
    else:
        registrar_cambio(
            db, catalogo=vigente, usuario_id=usuario.id, accion="validada",
            detalle=f"Reconfirmado al clasificar {empresa_nombre}", norma=norma_texto,
        )
