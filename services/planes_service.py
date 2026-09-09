"""
Lógica de planes y cupos por Cuenta (multiempresa).

Reglas clave (ver docs/Plan Multiempresa...):
  - El plan vive en la Cuenta (`CuentaCliente`), no en el usuario.
  - Cupo de causaciones = por mes calendario. `max_causaciones_mes = NULL` → ilimitado.
  - Cupo efectivo del mes = plan.max_causaciones_mes + Σ causaciones_adicionales del periodo.
  - Una factura causada (compra o NC) cuenta como 1.
  - Sin Cuenta (ej. superadmin) → sin límite.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.auth import CausacionAdicional, CuentaCliente, CupoCausacion, Empresa, Plan, Usuario
from db.models.contabilidad import FacturaCausada


def periodo_actual() -> str:
    """Periodo del mes calendario en curso, formato 'YYYY-MM'."""
    return date.today().strftime("%Y-%m")


def _rango_mes(periodo: str) -> tuple[date, date]:
    y, m = (int(x) for x in periodo.split("-"))
    inicio = date(y, m, 1)
    fin = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return inicio, fin


def get_cuenta_de_empresa(db: Session, empresa) -> CuentaCliente | None:
    cuenta_id = getattr(empresa, "cuenta_id", None)
    if not cuenta_id:
        return None
    return db.get(CuentaCliente, cuenta_id)


def get_plan(db: Session, cuenta: CuentaCliente | None) -> Plan | None:
    if cuenta is None or cuenta.plan_id is None:
        return None
    return db.get(Plan, cuenta.plan_id)


def cupo_efectivo_mes(db: Session, cuenta: CuentaCliente | None, periodo: str | None = None) -> int | None:
    """Cupo de causaciones del mes. Devuelve None si es ILIMITADO (o sin plan)."""
    plan = get_plan(db, cuenta)
    if plan is None or plan.max_causaciones_mes is None:
        return None  # ilimitado
    periodo = periodo or periodo_actual()
    extra = db.scalar(
        select(func.coalesce(func.sum(CausacionAdicional.cantidad), 0)).where(
            CausacionAdicional.cuenta_id == cuenta.id,
            CausacionAdicional.periodo == periodo,
        )
    ) or 0
    return int(plan.max_causaciones_mes) + int(extra)


def causaciones_usadas_mes(db: Session, cuenta: CuentaCliente | None, periodo: str | None = None) -> int:
    """Facturas causadas este mes en las empresas de la Cuenta."""
    if cuenta is None:
        return 0
    periodo = periodo or periodo_actual()
    emp_ids = db.scalars(select(Empresa.id).where(Empresa.cuenta_id == cuenta.id)).all()
    if not emp_ids:
        return 0
    inicio, fin = _rango_mes(periodo)
    return db.scalar(
        select(func.count(FacturaCausada.id)).where(
            FacturaCausada.empresa_id.in_(emp_ids),
            FacturaCausada.fecha_causacion >= inicio,
            FacturaCausada.fecha_causacion < fin,
        )
    ) or 0


def causaciones_totales(db: Session, cuenta: CuentaCliente | None) -> int:
    """Total de causaciones (todas, sin importar el mes) de la Cuenta. Para planes de prueba."""
    if cuenta is None:
        return 0
    emp_ids = db.scalars(select(Empresa.id).where(Empresa.cuenta_id == cuenta.id)).all()
    if not emp_ids:
        return 0
    return db.scalar(
        select(func.count(FacturaCausada.id)).where(FacturaCausada.empresa_id.in_(emp_ids))
    ) or 0


def trial_vencida(cuenta: CuentaCliente | None) -> bool:
    return bool(cuenta and cuenta.es_prueba and cuenta.prueba_expira and date.today() > cuenta.prueba_expira)


def puede_causar(db: Session, cuenta: CuentaCliente | None, n: int = 1) -> tuple[bool, dict]:
    """¿La Cuenta puede causar `n` documentos más? Considera prueba vencida y el tipo de cupo."""
    if cuenta is None:
        return True, {"ilimitado": True}
    if trial_vencida(cuenta):
        return False, {"motivo": "prueba_vencida"}
    plan = get_plan(db, cuenta)
    # Plan de prueba (Free): cupo TOTAL, no mensual.
    if plan is not None and plan.max_causaciones_total is not None:
        usadas = causaciones_totales(db, cuenta)
        tope = plan.max_causaciones_total
        return (usadas + n <= tope), {"prueba": True, "cupo": tope, "usadas": usadas, "restantes": max(tope - usadas, 0)}
    # Planes normales: cupo mensual.
    cupo = cupo_efectivo_mes(db, cuenta)
    if cupo is None:
        return True, {"ilimitado": True}
    usadas = causaciones_usadas_mes(db, cuenta)
    return (usadas + n <= cupo), {"ilimitado": False, "cupo": cupo, "usadas": usadas, "restantes": max(cupo - usadas, 0)}


# ─── Cupo por usuario (asignado por el admin) ────────────────────────────────

def cupo_usuario(db: Session, cuenta_id: int, usuario_id: int) -> int | None:
    """Tope mensual de causaciones que el admin asignó a un usuario. None = sin tope propio."""
    return db.scalar(
        select(CupoCausacion.max_mes).where(
            CupoCausacion.cuenta_id == cuenta_id,
            CupoCausacion.usuario_id == usuario_id,
            CupoCausacion.empresa_id.is_(None),
        )
    )


def causaciones_usadas_usuario_mes(db: Session, cuenta: CuentaCliente, usuario_id: int, periodo: str | None = None) -> int:
    """Facturas causadas este mes POR ese usuario dentro de la Cuenta."""
    periodo = periodo or periodo_actual()
    emp_ids = db.scalars(select(Empresa.id).where(Empresa.cuenta_id == cuenta.id)).all()
    if not emp_ids:
        return 0
    inicio, fin = _rango_mes(periodo)
    return db.scalar(
        select(func.count(FacturaCausada.id)).where(
            FacturaCausada.empresa_id.in_(emp_ids),
            FacturaCausada.usuario_id == usuario_id,
            FacturaCausada.fecha_causacion >= inicio,
            FacturaCausada.fecha_causacion < fin,
        )
    ) or 0


def puede_causar_usuario(db: Session, cuenta: CuentaCliente, usuario_id: int, n: int = 1) -> tuple[bool, dict]:
    """¿Ese usuario puede causar `n` más este mes según SU cupo asignado?"""
    cupo = cupo_usuario(db, cuenta.id, usuario_id)
    if cupo is None:
        return True, {"sin_limite_usuario": True}
    usadas = causaciones_usadas_usuario_mes(db, cuenta, usuario_id)
    return (usadas + n <= cupo), {"cupo": cupo, "usadas": usadas, "restantes": max(cupo - usadas, 0)}


def set_cupo_usuario(db: Session, cuenta_id: int, usuario_id: int, max_mes: int | None) -> None:
    """Fija (o quita si max_mes is None) el cupo mensual de un usuario. No hace commit."""
    from sqlalchemy import delete
    db.execute(delete(CupoCausacion).where(
        CupoCausacion.cuenta_id == cuenta_id,
        CupoCausacion.usuario_id == usuario_id,
        CupoCausacion.empresa_id.is_(None),
    ))
    if max_mes is not None:
        db.add(CupoCausacion(cuenta_id=cuenta_id, usuario_id=usuario_id, max_mes=max_mes))


def suma_cupos_asignados(db: Session, cuenta_id: int, excluir_usuario_id: int | None = None) -> int:
    """Suma de las causaciones/mes ya repartidas a los causadores de la cuenta."""
    q = select(func.coalesce(func.sum(CupoCausacion.max_mes), 0)).where(
        CupoCausacion.cuenta_id == cuenta_id,
        CupoCausacion.usuario_id.is_not(None),
        CupoCausacion.empresa_id.is_(None),
    )
    if excluir_usuario_id is not None:
        q = q.where(CupoCausacion.usuario_id != excluir_usuario_id)
    return int(db.scalar(q) or 0)


def suma_max_empresas_asignadas(db: Session, cuenta_id: int, excluir_usuario_id: int | None = None) -> int:
    """Suma de las empresas ya repartidas (max_empresas) a los causadores de la cuenta."""
    q = select(func.coalesce(func.sum(Usuario.max_empresas), 0)).where(
        Usuario.cuenta_id == cuenta_id,
        Usuario.rol == "causador",
        Usuario.max_empresas.is_not(None),
    )
    if excluir_usuario_id is not None:
        q = q.where(Usuario.id != excluir_usuario_id)
    return int(db.scalar(q) or 0)


def puede_crear_usuario(db: Session, cuenta: CuentaCliente | None) -> tuple[bool, dict]:
    plan = get_plan(db, cuenta)
    if plan is None or plan.max_usuarios is None:
        return True, {"ilimitado": True}
    # Solo cuentan los CAUSADORES; el admin de la cuenta no ocupa cupo del plan.
    actuales = db.scalar(
        select(func.count(Usuario.id)).where(
            Usuario.cuenta_id == cuenta.id, Usuario.rol == "causador", Usuario.activo.is_(True)
        )
    ) or 0
    return actuales < plan.max_usuarios, {"max": plan.max_usuarios, "actuales": int(actuales)}


def empresas_creadas_por_usuario(db: Session, usuario_id: int) -> int:
    """Cuántas empresas activas creó (posee) ese usuario."""
    return db.scalar(
        select(func.count(Empresa.id)).where(Empresa.owner_id == usuario_id, Empresa.activa.is_(True))
    ) or 0


def puede_crear_empresa_usuario(db: Session, cuenta: CuentaCliente | None, usuario: Usuario) -> tuple[bool, dict]:
    """¿Este causador puede crear otra empresa? Respeta el tope del plan (cuenta) y
    el tope personal que le asignó el admin (`usuario.max_empresas`)."""
    ok_plan, info_plan = puede_crear_empresa(db, cuenta)
    if not ok_plan:
        return False, {"motivo": "plan", **info_plan}
    if usuario.max_empresas is None:
        return True, {"ilimitado_usuario": True}
    creadas = empresas_creadas_por_usuario(db, usuario.id)
    return creadas < usuario.max_empresas, {"motivo": "usuario", "max": usuario.max_empresas, "actuales": creadas}


def puede_crear_empresa(db: Session, cuenta: CuentaCliente | None) -> tuple[bool, dict]:
    plan = get_plan(db, cuenta)
    if plan is None or plan.max_empresas is None:
        return True, {"ilimitado": True}
    actuales = db.scalar(
        select(func.count(Empresa.id)).where(Empresa.cuenta_id == cuenta.id, Empresa.activa.is_(True))
    ) or 0
    return actuales < plan.max_empresas, {"max": plan.max_empresas, "actuales": int(actuales)}


def consumo_cuenta(db: Session, cuenta: CuentaCliente | None) -> dict:
    """Resumen de consumo de una Cuenta (panel admin / perfil / banner de prueba)."""
    plan = get_plan(db, cuenta)
    base = {"plan": plan.nombre if plan else None, "prueba": False, "periodo": periodo_actual()}

    # Cuenta de prueba (Free): cupo TOTAL + días restantes.
    if cuenta is not None and cuenta.es_prueba and plan is not None and plan.max_causaciones_total is not None:
        usadas = causaciones_totales(db, cuenta)
        tope = plan.max_causaciones_total
        dias = (cuenta.prueba_expira - date.today()).days if cuenta.prueba_expira else None
        return {
            **base, "prueba": True, "ilimitado": False,
            "cupo_mes": tope, "usadas_mes": usadas,        # compat con la UI existente
            "restantes": max(tope - usadas, 0),
            "dias_restantes": dias,
            "vencida": trial_vencida(cuenta),
            "prueba_expira": cuenta.prueba_expira.isoformat() if cuenta.prueba_expira else None,
        }

    cupo = cupo_efectivo_mes(db, cuenta)
    usadas = causaciones_usadas_mes(db, cuenta)
    return {
        **base, "ilimitado": cupo is None,
        "cupo_mes": cupo, "usadas_mes": usadas,
        "restantes": None if cupo is None else max(cupo - usadas, 0),
    }


def consumo(db: Session, empresa) -> dict:
    """Consumo del mes a partir de la empresa activa (deriva su Cuenta)."""
    return consumo_cuenta(db, get_cuenta_de_empresa(db, empresa))
