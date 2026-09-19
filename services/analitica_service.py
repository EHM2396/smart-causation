"""
Analítica de costos, gastos e ingresos a partir de los documentos electrónicos
DIAN ya causados.

La clasificación es por TIPO DE DOCUMENTO, que es lo que la DIAN define:

  Ingresos          ventas      (factura electrónica de venta emitida)
                    nc_ventas   (nota crédito de venta) ....................... resta

  Costos y gastos   compras     (factura electrónica de venta recibida)
                    soporte     (documento soporte en adquisiciones a no
                                 obligados a facturar — CustomizationID 05,
                                 legaliza el costo con personas naturales)
                    nc          (nota crédito de compra) ..................... resta
                    nc_soporte  (nota de ajuste al documento soporte) ........ resta

Dos reglas que hacen que las cifras signifiquen algo:

1. Las notas crédito RESTAN. Sumarlas junto a las facturas da un número que no
   representa nada (era el defecto del "monto total" que se quitó del panel de
   administración).
2. Se usa la BASE GRAVABLE, no el total: el total incluye IVA, y el IVA
   descontable no es un costo sino un saldo a favor. Mientras un registro no
   tenga la base poblada se cae al total, para no dejarlo fuera del informe.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from db.models.auth import Empresa, Usuario
from db.models.contabilidad import FacturaCausada
from services import causacion_service

# Signo con el que cada tipo entra a su naturaleza.
SIGNO: dict[str, int] = {
    "ventas": 1, "nc_ventas": -1,
    "compras": 1, "soporte": 1, "nc": -1, "nc_soporte": -1,
}

# Naturaleza contable de cada tipo de documento.
NATURALEZA: dict[str, str] = {
    "ventas": "ingresos", "nc_ventas": "ingresos",
    "compras": "costos_gastos", "soporte": "costos_gastos",
    "nc": "costos_gastos", "nc_soporte": "costos_gastos",
}

# Nombre de cada documento de cara al usuario.
ETIQUETA: dict[str, str] = {
    "ventas": "Facturas de venta",
    "nc_ventas": "Notas crédito de venta",
    "compras": "Facturas de compra",
    "nc": "Notas crédito de compra",
    "soporte": "Documento soporte",
    "nc_soporte": "Ajustes al documento soporte",
}

# Orden de presentación: primero lo que suma, después lo que resta.
ORDEN: list[str] = ["ventas", "nc_ventas", "compras", "soporte", "nc", "nc_soporte"]


def _valor() -> object:
    """Base gravable si está poblada; si no, el total (que incluye IVA)."""
    return func.coalesce(FacturaCausada.base_gravable, FacturaCausada.total, 0)


def empresas_visibles(db: Session, usuario: Usuario, cuenta_id: int | None) -> list[int]:
    """Qué empresas puede ver este usuario en la analítica.

    El causador ve las suyas (las que creó). El administrador de la cuenta —y el
    superadmin— ven todas las de la cuenta, que es justamente la mirada global
    de lo que causa cada uno de sus usuarios.
    """
    # Solo empresas ACTIVAS: las eliminadas salen de la lista del usuario, así que
    # incluirlas acá haría que el informe hablara de más empresas de las que el
    # filtro deja elegir (el KPI decía 5 y el selector ofrecía 3).
    if usuario.rol in ("org_admin", "admin") and cuenta_id is not None:
        stmt = select(Empresa.id).where(
            Empresa.cuenta_id == cuenta_id, Empresa.activa.is_(True)
        )
    else:
        stmt = select(Empresa.id).where(
            Empresa.owner_id == usuario.id, Empresa.activa.is_(True)
        )
    return list(db.scalars(stmt).all())


def resumen(
    db: Session,
    *,
    empresa_ids: list[int],
    desde: date,
    hasta: date,
    campo_fecha: str | None = None,
) -> dict:
    """Consolidado del periodo: KPIs, desglose por documento, serie mensual,
    por empresa y los terceros de mayor peso.

    `campo_fecha` decide sobre qué fecha corre el rango: 'emision' (cuándo se
    emitió el documento) o 'causacion' (cuándo se registró). No da lo mismo: una
    factura de agosto causada en septiembre aparece en un mes o en el otro según
    lo que se elija.
    """
    vacio = {
        "kpis": {"ingresos": 0.0, "costos_gastos": 0.0, "resultado": 0.0, "documentos": 0},
        "por_tipo": [], "serie_mensual": [], "por_empresa": [], "por_tercero": [],
    }
    if not empresa_ids:
        return vacio

    columna = causacion_service.columna_fecha(campo_fecha)
    base = [
        FacturaCausada.empresa_id.in_(empresa_ids),
        FacturaCausada.eliminado.is_(False),
        columna >= desde,
        columna <= hasta,
    ]
    valor = _valor()

    # ── Por tipo de documento ────────────────────────────────────────────────
    filas = db.execute(
        select(FacturaCausada.tipo_causacion, func.count(FacturaCausada.id), func.sum(valor))
        .where(*base).group_by(FacturaCausada.tipo_causacion)
    ).all()

    montos: dict[str, float] = defaultdict(float)
    conteos: dict[str, int] = defaultdict(int)
    for tipo, n, monto in filas:
        # Los registros anteriores al campo tipo_causacion (NULL) se cuentan como
        # compras: es el módulo con el que nació el sistema.
        t = tipo or "compras"
        montos[t] += float(monto or 0)
        conteos[t] += int(n or 0)

    ingresos = sum(montos[t] * SIGNO[t] for t in montos if NATURALEZA.get(t) == "ingresos")
    costos = sum(montos[t] * SIGNO[t] for t in montos if NATURALEZA.get(t) == "costos_gastos")
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
    # La serie se agrupa por la MISMA fecha con la que se filtró: si no, el rango
    # diría una cosa y las barras del gráfico otra.
    mes = func.to_char(columna, "YYYY-MM")
    filas_mes = db.execute(
        select(mes, FacturaCausada.tipo_causacion, func.sum(valor))
        .where(*base).group_by(mes, FacturaCausada.tipo_causacion).order_by(mes)
    ).all()

    acc: dict[str, dict[str, float]] = defaultdict(lambda: {"ingresos": 0.0, "costos_gastos": 0.0})
    for m, tipo, monto in filas_mes:
        t = tipo or "compras"
        acc[m][NATURALEZA.get(t, "costos_gastos")] += float(monto or 0) * SIGNO.get(t, 1)
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
        select(FacturaCausada.empresa_id, Empresa.nombre, FacturaCausada.tipo_causacion,
               func.count(FacturaCausada.id), func.sum(valor))
        .outerjoin(Empresa, Empresa.id == FacturaCausada.empresa_id)
        .where(*base)
        .group_by(FacturaCausada.empresa_id, Empresa.nombre, FacturaCausada.tipo_causacion)
    ).all()

    emp: dict[int, dict] = {}
    for eid, nombre, tipo, n, monto in filas_emp:
        t = tipo or "compras"
        e = emp.setdefault(eid, {
            "empresa_id": eid, "nombre": nombre or "—",
            "ingresos": 0.0, "costos_gastos": 0.0, "documentos": 0,
        })
        e[NATURALEZA.get(t, "costos_gastos")] += float(monto or 0) * SIGNO.get(t, 1)
        e["documentos"] += int(n or 0)
    por_empresa = sorted(
        ({**e, "ingresos": round(e["ingresos"], 2),
          "costos_gastos": round(e["costos_gastos"], 2),
          "resultado": round(e["ingresos"] - e["costos_gastos"], 2)} for e in emp.values()),
        key=lambda e: e["documentos"], reverse=True,
    )

    # ── Terceros de mayor peso en costos y gastos ────────────────────────────
    # El NULL entra también: son los registros anteriores al campo, que en el
    # resto del informe se cuentan como compras. Si se filtrara solo por los
    # tipos conocidos, este bloque quedaría vacío mientras los KPI muestran
    # costos — la misma cifra contada de dos formas distintas.
    tipos_costo = [t for t, nat in NATURALEZA.items() if nat == "costos_gastos"]
    filas_ter = db.execute(
        select(FacturaCausada.nit_proveedor, FacturaCausada.razon_social,
               func.count(FacturaCausada.id), func.sum(valor))
        .where(*base, or_(FacturaCausada.tipo_causacion.in_(tipos_costo),
                          FacturaCausada.tipo_causacion.is_(None)))
        .group_by(FacturaCausada.nit_proveedor, FacturaCausada.razon_social)
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
