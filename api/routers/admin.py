"""
Router: /admin – panel de administración de la Cuenta.

Solo accesible para `org_admin` (y el superadmin `admin`). El admin NO causa ni
crea empresas: solo administra a los usuarios causadores de la cuenta, repartiendo
entre ellos —por número— las causaciones y empresas que permite el plan. Cada
causador crea sus propias empresas hasta el tope que le asigna el admin.
"""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Annotated

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from db.models.auth import CuentaCliente, Empresa, Usuario
from db.models.contabilidad import FacturaCausada
from db.session import get_db
from services import planes_service

router = APIRouter(prefix="/admin", tags=["Admin"])

DB = Annotated[Session, Depends(get_db)]


def require_org_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if current_user.rol not in ("org_admin", "admin"):
        raise HTTPException(status_code=403, detail="Requiere permisos de administrador de la cuenta")
    return current_user


OrgAdmin = Annotated[Usuario, Depends(require_org_admin)]


def _cuenta_de(db: Session, user: Usuario) -> CuentaCliente:
    if not user.cuenta_id:
        raise HTTPException(status_code=400, detail="Tu usuario no está asociado a una cuenta")
    cuenta = db.get(CuentaCliente, user.cuenta_id)
    if cuenta is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return cuenta


def _hash_password(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class UsuarioOut(BaseModel):
    id: int
    email: str
    nombre: str
    activo: bool
    cupo_mes: int | None = None        # tope de causaciones/mes (None = sin tope propio)
    max_empresas: int | None = None    # cuántas empresas puede crear (None = sin tope propio)
    empresas_creadas: int = 0          # cuántas ha creado


class UsuarioCreate(BaseModel):
    email: str = Field(min_length=3)
    nombre: str = Field(min_length=1)
    password: str = Field(min_length=8)
    cupo_mes: int | None = Field(default=None, ge=0)
    max_empresas: int | None = Field(default=None, ge=0)


class UsuarioUpdate(BaseModel):
    # El rol NO se puede cambiar: solo existe UNA cuenta admin por Cuenta.
    activo: bool | None = None
    cupo_mes: int | None = Field(default=None, ge=0)       # presente = fijar (null = sin tope)
    max_empresas: int | None = Field(default=None, ge=0)   # presente = fijar (null = sin tope)


class EmpresaOut(BaseModel):
    id: int
    nombre: str
    nit: str | None = None
    activa: bool
    creada_por: str | None = None      # nombre del causador que la creó


def _validar_reparto(db: Session, cuenta: CuentaCliente, cupo_mes: int | None,
                     max_empresas: int | None, excluir_usuario_id: int | None = None) -> None:
    """No permitir repartir a un usuario más de lo que queda del total del plan."""
    plan = planes_service.get_plan(db, cuenta)
    if plan is None:
        return
    if cupo_mes is not None and plan.max_causaciones_mes is not None:
        otros = planes_service.suma_cupos_asignados(db, cuenta.id, excluir_usuario_id)
        disp = plan.max_causaciones_mes - otros
        if cupo_mes > disp:
            raise HTTPException(
                status_code=400,
                detail=(f"Tu plan permite {plan.max_causaciones_mes} causaciones al mes en total y ya "
                        f"repartiste {otros}. A este usuario puedes asignarle hasta {max(disp, 0)}."),
            )
    if max_empresas is not None and plan.max_empresas is not None:
        otros_e = planes_service.suma_max_empresas_asignadas(db, cuenta.id, excluir_usuario_id)
        disp_e = plan.max_empresas - otros_e
        if max_empresas > disp_e:
            raise HTTPException(
                status_code=400,
                detail=(f"Tu plan permite {plan.max_empresas} empresas en total y ya repartiste "
                        f"{otros_e}. A este usuario puedes asignarle hasta {max(disp_e, 0)}."),
            )


def _usuario_out(db: Session, cuenta_id: int, u: Usuario) -> "UsuarioOut":
    return UsuarioOut(
        id=u.id, email=u.email, nombre=u.nombre, activo=u.activo,
        cupo_mes=planes_service.cupo_usuario(db, cuenta_id, u.id),
        max_empresas=u.max_empresas,
        empresas_creadas=planes_service.empresas_creadas_por_usuario(db, u.id),
    )


# ─── Cuenta / consumo ────────────────────────────────────────────────────────

@router.get("/cuenta")
def get_cuenta(db: DB, admin: OrgAdmin):
    cuenta = _cuenta_de(db, admin)
    _, uinfo = planes_service.puede_crear_usuario(db, cuenta)
    _, einfo = planes_service.puede_crear_empresa(db, cuenta)
    return {
        "id": cuenta.id,
        "nombre": cuenta.nombre,
        "estado": cuenta.estado,
        "consumo": planes_service.consumo_cuenta(db, cuenta),
        "limite_usuarios": uinfo,   # {max, actuales} o {ilimitado: True}
        "limite_empresas": einfo,
    }


# ─── Usuarios (solo causadores; el admin no aparece) ──────────────────────────

@router.get("/usuarios", response_model=list[UsuarioOut])
def list_usuarios(db: DB, admin: OrgAdmin):
    cuenta = _cuenta_de(db, admin)
    usuarios = db.scalars(
        select(Usuario).where(Usuario.cuenta_id == cuenta.id, Usuario.rol == "causador").order_by(Usuario.id)
    ).all()
    return [_usuario_out(db, cuenta.id, u) for u in usuarios]


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def create_usuario(body: UsuarioCreate, db: DB, admin: OrgAdmin):
    cuenta = _cuenta_de(db, admin)
    ok, info = planes_service.puede_crear_usuario(db, cuenta)
    if not ok:
        raise HTTPException(
            status_code=402,
            detail=f"Alcanzaste el máximo de usuarios de tu plan ({info['actuales']}/{info['max']}).",
        )
    email = body.email.lower().strip()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Escribe un correo válido")
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado")

    _validar_reparto(db, cuenta, body.cupo_mes, body.max_empresas, excluir_usuario_id=None)

    u = Usuario(
        email=email,
        password_hash=_hash_password(body.password),
        nombre=body.nombre,
        rol="causador",
        cuenta_id=cuenta.id,
        max_empresas=body.max_empresas,
        email_verificado=True,   # creado por el admin: no requiere verificación por correo
        activo=True,
    )
    db.add(u)
    db.flush()
    if body.cupo_mes is not None:
        planes_service.set_cupo_usuario(db, cuenta.id, u.id, body.cupo_mes)
    db.commit()
    db.refresh(u)
    return _usuario_out(db, cuenta.id, u)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut)
def update_usuario(usuario_id: int, body: UsuarioUpdate, db: DB, admin: OrgAdmin):
    cuenta = _cuenta_de(db, admin)
    u = db.get(Usuario, usuario_id)
    if u is None or u.cuenta_id != cuenta.id or u.rol != "causador":
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu cuenta")

    _validar_reparto(
        db, cuenta,
        body.cupo_mes if "cupo_mes" in body.model_fields_set else None,
        body.max_empresas if "max_empresas" in body.model_fields_set else None,
        excluir_usuario_id=u.id,
    )

    if body.activo is not None:
        u.activo = body.activo
    if "max_empresas" in body.model_fields_set:
        u.max_empresas = body.max_empresas
    if "cupo_mes" in body.model_fields_set:
        planes_service.set_cupo_usuario(db, cuenta.id, u.id, body.cupo_mes)

    db.commit()
    db.refresh(u)
    return _usuario_out(db, cuenta.id, u)


# ─── Empresas (solo lectura: el admin ve las que creó cada causador) ──────────

@router.get("/empresas", response_model=list[EmpresaOut])
def list_empresas(db: DB, admin: OrgAdmin):
    cuenta = _cuenta_de(db, admin)
    rows = db.execute(
        select(Empresa, Usuario.nombre)
        .outerjoin(Usuario, Usuario.id == Empresa.owner_id)
        .where(Empresa.cuenta_id == cuenta.id)
        .order_by(Empresa.id)
    ).all()
    return [
        EmpresaOut(id=e.id, nombre=e.nombre, nit=e.nit, activa=e.activa, creada_por=owner)
        for (e, owner) in rows
    ]


# ─── Dashboard e informes ────────────────────────────────────────────────────

def _parse_rango(desde: str | None, hasta: str | None) -> tuple[date, date]:
    """Rango de fechas del informe. Por defecto: el mes en curso."""
    hoy = date.today()
    try:
        d = date.fromisoformat(desde) if desde else date(hoy.year, hoy.month, 1)
    except ValueError:
        d = date(hoy.year, hoy.month, 1)
    try:
        h = date.fromisoformat(hasta) if hasta else hoy
    except ValueError:
        h = hoy
    if h < d:
        d, h = h, d
    return d, h


def _empresas_de_cuenta(db: Session, cuenta_id: int) -> list[int]:
    return list(db.scalars(select(Empresa.id).where(Empresa.cuenta_id == cuenta_id)).all())


@router.get("/dashboard")
def dashboard(db: DB, admin: OrgAdmin, desde: str | None = None, hasta: str | None = None):
    """Métricas de causación en un rango: totales, por usuario y por empresa."""
    cuenta = _cuenta_de(db, admin)
    d, h = _parse_rango(desde, hasta)
    emp_ids = _empresas_de_cuenta(db, cuenta.id)

    if not emp_ids:
        return {
            "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
            "total_causaciones": 0, "monto_total": 0.0,
            "por_usuario": [], "por_empresa": [],
            "consumo_mes": planes_service.consumo_cuenta(db, cuenta),
        }

    base = [
        FacturaCausada.empresa_id.in_(emp_ids),
        FacturaCausada.fecha_causacion >= d,
        FacturaCausada.fecha_causacion <= h,
    ]
    total = db.scalar(select(func.count(FacturaCausada.id)).where(*base)) or 0
    monto = db.scalar(select(func.coalesce(func.sum(FacturaCausada.total), 0)).where(*base)) or 0

    por_usuario = db.execute(
        select(FacturaCausada.usuario_id, Usuario.nombre,
               func.count(FacturaCausada.id), func.coalesce(func.sum(FacturaCausada.total), 0))
        .outerjoin(Usuario, Usuario.id == FacturaCausada.usuario_id)
        .where(*base)
        .group_by(FacturaCausada.usuario_id, Usuario.nombre)
        .order_by(func.count(FacturaCausada.id).desc())
    ).all()
    por_empresa = db.execute(
        select(FacturaCausada.empresa_id, Empresa.nombre,
               func.count(FacturaCausada.id), func.coalesce(func.sum(FacturaCausada.total), 0))
        .outerjoin(Empresa, Empresa.id == FacturaCausada.empresa_id)
        .where(*base)
        .group_by(FacturaCausada.empresa_id, Empresa.nombre)
        .order_by(func.count(FacturaCausada.id).desc())
    ).all()

    return {
        "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
        "total_causaciones": int(total),
        "monto_total": float(monto),
        "por_usuario": [
            {"usuario_id": uid, "nombre": nom or "Sin asignar", "causaciones": int(c), "monto": float(m)}
            for (uid, nom, c, m) in por_usuario
        ],
        "por_empresa": [
            {"empresa_id": eid, "nombre": nom or "—", "causaciones": int(c), "monto": float(m)}
            for (eid, nom, c, m) in por_empresa
        ],
        "consumo_mes": planes_service.consumo_cuenta(db, cuenta),
    }


@router.get("/usuario/{usuario_id}/detalle")
def usuario_detalle(usuario_id: int, db: DB, admin: OrgAdmin, desde: str | None = None, hasta: str | None = None):
    """Detalle de causaciones de UN causador en el rango: por empresa + listado."""
    cuenta = _cuenta_de(db, admin)
    u = db.get(Usuario, usuario_id)
    if u is None or u.cuenta_id != cuenta.id:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en tu cuenta")
    d, h = _parse_rango(desde, hasta)
    emp_ids = _empresas_de_cuenta(db, cuenta.id)
    if not emp_ids:
        return {"usuario": {"id": u.id, "nombre": u.nombre, "email": u.email},
                "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
                "total": 0, "monto": 0.0, "por_empresa": [], "detalle": []}

    base = [
        FacturaCausada.empresa_id.in_(emp_ids),
        FacturaCausada.usuario_id == usuario_id,
        FacturaCausada.fecha_causacion >= d,
        FacturaCausada.fecha_causacion <= h,
    ]
    total = db.scalar(select(func.count(FacturaCausada.id)).where(*base)) or 0
    monto = db.scalar(select(func.coalesce(func.sum(FacturaCausada.total), 0)).where(*base)) or 0
    por_empresa = db.execute(
        select(Empresa.nombre, func.count(FacturaCausada.id), func.coalesce(func.sum(FacturaCausada.total), 0))
        .outerjoin(Empresa, Empresa.id == FacturaCausada.empresa_id)
        .where(*base).group_by(Empresa.nombre).order_by(func.count(FacturaCausada.id).desc())
    ).all()
    detalle = db.execute(
        select(FacturaCausada.fecha_causacion, Empresa.nombre, FacturaCausada.numero_dian,
               FacturaCausada.razon_social, FacturaCausada.total)
        .outerjoin(Empresa, Empresa.id == FacturaCausada.empresa_id)
        .where(*base).order_by(FacturaCausada.fecha_causacion.desc()).limit(100)
    ).all()

    return {
        "usuario": {"id": u.id, "nombre": u.nombre, "email": u.email},
        "periodo": {"desde": d.isoformat(), "hasta": h.isoformat()},
        "total": int(total), "monto": float(monto),
        "por_empresa": [{"nombre": nom or "—", "causaciones": int(c), "monto": float(m)} for (nom, c, m) in por_empresa],
        "detalle": [
            {"fecha": f.isoformat() if f else "", "empresa": emp or "—", "numero": num or "",
             "proveedor": prov or "", "total": float(t or 0)}
            for (f, emp, num, prov, t) in detalle
        ],
    }


@router.get("/informe.xlsx")
def informe_xlsx(db: DB, admin: OrgAdmin, desde: str | None = None, hasta: str | None = None):
    """Descarga el detalle de causaciones del rango en Excel."""
    import xlsxwriter

    cuenta = _cuenta_de(db, admin)
    d, h = _parse_rango(desde, hasta)
    emp_ids = _empresas_de_cuenta(db, cuenta.id)

    filas = []
    if emp_ids:
        filas = db.execute(
            select(
                FacturaCausada.fecha_causacion, Empresa.nombre, Usuario.nombre,
                FacturaCausada.numero_dian, FacturaCausada.razon_social,
                FacturaCausada.tipo_comprobante, FacturaCausada.consecutivo, FacturaCausada.total,
            )
            .outerjoin(Empresa, Empresa.id == FacturaCausada.empresa_id)
            .outerjoin(Usuario, Usuario.id == FacturaCausada.usuario_id)
            .where(
                FacturaCausada.empresa_id.in_(emp_ids),
                FacturaCausada.fecha_causacion >= d,
                FacturaCausada.fecha_causacion <= h,
            )
            .order_by(FacturaCausada.fecha_causacion.desc())
        ).all()

    buffer = BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True})
    ws = wb.add_worksheet("Causaciones")
    fmt_h = wb.add_format({"bold": True, "bg_color": "#1F4E79", "font_color": "#FFFFFF", "border": 1})
    fmt_money = wb.add_format({"num_format": "#,##0.00"})
    cols = ["Fecha", "Empresa", "Usuario", "N° Factura", "Proveedor", "Comprobante", "Consecutivo", "Total"]
    for i, c in enumerate(cols):
        ws.write(0, i, c, fmt_h)
    for r, (fecha, emp, usr, num, prov, tipo, cons, tot) in enumerate(filas, start=1):
        ws.write(r, 0, fecha.isoformat() if fecha else "")
        ws.write(r, 1, emp or "")
        ws.write(r, 2, usr or "Sin asignar")
        ws.write(r, 3, num or "")
        ws.write(r, 4, prov or "")
        ws.write(r, 5, tipo or "")
        ws.write(r, 6, cons or "")
        ws.write_number(r, 7, float(tot or 0), fmt_money)
    for i, w in enumerate([12, 24, 20, 16, 28, 14, 12, 16]):
        ws.set_column(i, i, w)
    ws.freeze_panes(1, 0)
    wb.close()
    buffer.seek(0)

    nombre = f"informe_causaciones_{d.isoformat()}_a_{h.isoformat()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
