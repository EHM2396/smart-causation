"""
Analítica de costos, gastos e ingresos a partir de los documentos electrónicos
que la DIAN reporta para la empresa.

La fuente son los documentos traídos con el token (`documentos_dian`), NO lo que
se alcanzó a causar. Antes salía de `facturas_causadas` y eso mostraba una
realidad parcial: tres notas crédito que existían en la DIAN pero que nadie había
causado no aparecían, y los ingresos salían inflados. Un informe tiene que
reflejar lo que pasó, no lo que se registró.

La clasificación es por TIPO DE DOCUMENTO, que es lo que la DIAN define:

  Ingresos          ventas      factura electrónica de venta emitida
                    nc_ventas   nota crédito de venta ........................ resta
                    nd_ventas   nota débito de venta ......................... suma

  Costos y gastos   compras     factura electrónica de venta recibida
                    soporte     documento soporte en adquisiciones a no
                                obligados a facturar — legaliza el costo con
                                personas naturales
                    nc          nota crédito de compra ....................... resta
                    nd          nota débito de compra ........................ suma
                    nc_soporte  nota de ajuste al documento soporte .......... resta

Dos reglas hacen que las cifras signifiquen algo:

1. Las notas crédito RESTAN y las débito SUMAN. Sumarlas todas por igual da un
   número que no representa nada.
2. Se usa la BASE GRAVABLE, no el total: el total incluye IVA, y el IVA
   descontable no es un costo sino un saldo a favor. Si un documento no tiene
   base calculada se cae al total, para no dejarlo fuera del informe.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.auth import Empresa, Usuario
from db.models.contabilidad import DocumentoDian

# Signo con el que cada tipo entra a su naturaleza.
SIGNO: dict[str, int] = {
    "ventas": 1, "nc_ventas": -1, "nd_ventas": 1,
    "compras": 1, "soporte": 1, "nc": -1, "nc_soporte": -1, "nd": 1,
}

# Naturaleza contable de cada tipo de documento.
NATURALEZA: dict[str, str] = {
    "ventas": "ingresos", "nc_ventas": "ingresos", "nd_ventas": "ingresos",
    "compras": "costos_gastos", "soporte": "costos_gastos",
    "nc": "costos_gastos", "nc_soporte": "costos_gastos", "nd": "costos_gastos",
}

# Nombre de cada documento de cara al usuario.
ETIQUETA: dict[str, str] = {
    "ventas": "Facturas de venta",
    "nc_ventas": "Notas crédito de venta",
    "nd_ventas": "Notas débito de venta",
    "compras": "Facturas de compra",
    "nc": "Notas crédito de compra",
    "nd": "Notas débito de compra",
    "soporte": "Documento soporte",
    "nc_soporte": "Ajustes al documento soporte",
}

# Orden de presentación: cada factura seguida de lo que la ajusta.
ORDEN: list[str] = [
    "ventas", "nc_ventas", "nd_ventas",
    "compras", "nc", "nd", "soporte", "nc_soporte",
]


def _valor():
    """Base gravable si está calculada; si no, el total (que incluye IVA)."""
    return func.coalesce(DocumentoDian.base_gravable, DocumentoDian.total, 0)


def empresas_visibles(db: Session, usuario: Usuario, cuenta_id: int | None) -> list[int]:
    """Qué empresas puede ver este usuario en la analítica.

    El causador ve las suyas (las que creó). El administrador de la cuenta —y el
    superadmin— ven todas las de la cuenta.

    Solo empresas ACTIVAS: las eliminadas salen de la lista del usuario, así que
    incluirlas haría que el informe hablara de más empresas de las que el filtro
    deja elegir.
    """
    if usuario.rol in ("org_admin", "admin") and cuenta_id is not None:
        stmt = select(Empresa.id).where(
            Empresa.cuenta_id == cuenta_id, Empresa.activa.is_(True)
        )
    else:
        stmt = select(Empresa.id).where(
            Empresa.owner_id == usuario.id, Empresa.activa.is_(True)
        )
    return list(db.scalars(stmt).all())


def resumen(db: Session, *, empresa_ids: list[int], desde: date, hasta: date) -> dict:
    """Consolidado del periodo por FECHA DE EMISIÓN: KPIs, desglose por
    documento, serie mensual, por empresa y los terceros de mayor peso.

    Se filtra por fecha de emisión y no hay alternativa: estos documentos vienen
    de la DIAN, donde la fecha de causación ni siquiera existe.
    """
    vacio = {
        "kpis": {"ingresos": 0.0, "costos_gastos": 0.0, "resultado": 0.0, "documentos": 0},
        "por_tipo": [], "serie_mensual": [], "por_empresa": [], "por_tercero": [],
    }
    if not empresa_ids:
        return vacio

    base = [
        DocumentoDian.empresa_id.in_(empresa_ids),
        DocumentoDian.fecha_emision >= desde,
        DocumentoDian.fecha_emision <= hasta,
    ]
    valor = _valor()

    # ── Por tipo de documento ────────────────────────────────────────────────
    filas = db.execute(
        select(DocumentoDian.tipo, func.count(DocumentoDian.id), func.sum(valor))
        .where(*base).group_by(DocumentoDian.tipo)
    ).all()

    montos: dict[str, float] = defaultdict(float)
    conteos: dict[str, int] = defaultdict(int)
    for tipo, n, monto in filas:
        montos[tipo] += float(monto or 0)
        conteos[tipo] += int(n or 0)

    ingresos = sum(montos[t] * SIGNO.get(t, 1) for t in montos if NATURALEZA.get(t) == "ingresos")
    costos = sum(montos[t] * SIGNO.get(t, 1) for t in montos if NATURALEZA.get(t) == "costos_gastos")
    documentos = sum(conteos.values())

    por_tipo = [
        {
            "tipo": t,
            "label": ETIQUETA[t],
            "naturaleza": NATURALEZA[t],
            "signo": SIGNO[t],
            "documentos": conteos[t],
            "monto": round(montos[t], 2),
        }
        for t in ORDEN if conteos.get(t)
    ]

    # ── Serie mensual ────────────────────────────────────────────────────────
    mes = func.to_char(DocumentoDian.fecha_emision, "YYYY-MM")
    filas_mes = db.execute(
        select(mes, DocumentoDian.tipo, func.sum(valor))
        .where(*base).group_by(mes, DocumentoDian.tipo).order_by(mes)
    ).all()

    acc: dict[str, dict[str, float]] = defaultdict(lambda: {"ingresos": 0.0, "costos_gastos": 0.0})
    for m, tipo, monto in filas_mes:
        acc[m][NATURALEZA.get(tipo, "costos_gastos")] += float(monto or 0) * SIGNO.get(tipo, 1)
    serie_mensual = [
        {
            "mes": m,
            "ingresos": round(v["ingresos"], 2),
            "costos_gastos": round(v["costos_gastos"], 2),
            "resultado": round(v["ingresos"] - v["costos_gastos"], 2),
        }
        for m, v in sorted(acc.items())
    ]

    # ── Por empresa ──────────────────────────────────────────────────────────
    filas_emp = db.execute(
        select(DocumentoDian.empresa_id, Empresa.nombre, DocumentoDian.tipo,
               func.count(DocumentoDian.id), func.sum(valor))
        .outerjoin(Empresa, Empresa.id == DocumentoDian.empresa_id)
        .where(*base)
        .group_by(DocumentoDian.empresa_id, Empresa.nombre, DocumentoDian.tipo)
    ).all()

    emp: dict[int, dict] = {}
    for eid, nombre, tipo, n, monto in filas_emp:
        e = emp.setdefault(eid, {
            "empresa_id": eid, "nombre": nombre or "—",
            "ingresos": 0.0, "costos_gastos": 0.0, "documentos": 0,
        })
        e[NATURALEZA.get(tipo, "costos_gastos")] += float(monto or 0) * SIGNO.get(tipo, 1)
        e["documentos"] += int(n or 0)
    por_empresa = sorted(
        ({**e, "ingresos": round(e["ingresos"], 2),
          "costos_gastos": round(e["costos_gastos"], 2),
          "resultado": round(e["ingresos"] - e["costos_gastos"], 2)} for e in emp.values()),
        key=lambda e: e["documentos"], reverse=True,
    )

    # ── Terceros de mayor peso en costos y gastos ────────────────────────────
    tipos_costo = [t for t, nat in NATURALEZA.items() if nat == "costos_gastos"]
    filas_ter = db.execute(
        select(DocumentoDian.nit_contraparte, DocumentoDian.razon_social,
               func.count(DocumentoDian.id), func.sum(valor))
        .where(*base, DocumentoDian.tipo.in_(tipos_costo))
        .group_by(DocumentoDian.nit_contraparte, DocumentoDian.razon_social)
        .order_by(func.sum(valor).desc()).limit(10)
    ).all()
    por_tercero = [
        {"nit": nit or "", "nombre": rs or "—", "documentos": int(n or 0), "monto": round(float(m or 0), 2)}
        for nit, rs, n, m in filas_ter
    ]

    return {
        "kpis": {
            "ingresos": round(ingresos, 2),
            "costos_gastos": round(costos, 2),
            "resultado": round(ingresos - costos, 2),
            "documentos": documentos,
        },
        "por_tipo": por_tipo,
        "serie_mensual": serie_mensual,
        "por_empresa": por_empresa,
        "por_tercero": por_tercero,
    }
