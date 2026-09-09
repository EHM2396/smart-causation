"""
Router: /empresas – cada causador gestiona (y crea) sus propias empresas.

El causador puede crear empresas hasta el tope que le asignó el admin
(`usuario.max_empresas`) y sin superar el tope total del plan de la cuenta.
"""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from db.models.auth import CuentaCliente, Empresa, Usuario, UsuarioEmpresa
from db.session import get_db
from services import planes_service

router = APIRouter(prefix="/empresas", tags=["Empresas"])

DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


def _norm_nit(s: str | None) -> str:
    return re.sub(r"[^0-9]", "", s or "")


def _nit_duplicado(db: Session, cuenta_id: int, nit: str, excluir_id: int | None = None) -> bool:
    """¿Ya existe otra empresa ACTIVA con ese NIT en la MISMA cuenta? (otras cuentas no cuentan)."""
    objetivo = _norm_nit(nit)
    if not objetivo:
        return False
    rows = db.execute(
        select(Empresa.id, Empresa.nit).where(Empresa.cuenta_id == cuenta_id, Empresa.activa.is_(True))
    ).all()
    for (eid, en) in rows:
        if excluir_id is not None and eid == excluir_id:
            continue
        if _norm_nit(en) == objetivo:
            return True
    return False


class EmpresaOut(BaseModel):
    id: int
    nombre: str
    nit: str | None = None
    activa: bool


class EmpresaCreate(BaseModel):
    nombre: str = Field(min_length=1)
    nit: str = Field(min_length=1)   # obligatorio


class EmpresaUpdate(BaseModel):
    nombre: str = Field(min_length=1)
    nit: str = Field(min_length=1)   # obligatorio


@router.get("")
def mis_empresas(db: DB, current_user: CurrentUser):
    """Empresas del usuario + si puede crear más y cuántas le quedan."""
    cuenta = db.get(CuentaCliente, current_user.cuenta_id) if current_user.cuenta_id else None
    emps = db.scalars(
        select(Empresa)
        .where(Empresa.owner_id == current_user.id, Empresa.activa.is_(True))
        .order_by(Empresa.nombre)
    ).all()
    puede, info = planes_service.puede_crear_empresa_usuario(db, cuenta, current_user)
    return {
        "empresas": [EmpresaOut(id=e.id, nombre=e.nombre, nit=e.nit, activa=e.activa).model_dump() for e in emps],
        "puede_crear": puede,
        "limite": info,
    }


@router.post("", response_model=EmpresaOut, status_code=201)
def crear_empresa(body: EmpresaCreate, db: DB, current_user: CurrentUser):
    if not current_user.cuenta_id:
        raise HTTPException(status_code=400, detail="Tu usuario no está asociado a una cuenta")
    if not body.nit.strip():
        raise HTTPException(status_code=400, detail="El NIT de la empresa es obligatorio")
    cuenta = db.get(CuentaCliente, current_user.cuenta_id)

    if _nit_duplicado(db, cuenta.id, body.nit):
        raise HTTPException(status_code=409, detail="Ya tienes una empresa registrada con ese NIT en tu cuenta.")

    puede, info = planes_service.puede_crear_empresa_usuario(db, cuenta, current_user)
    if not puede:
        if info.get("motivo") == "usuario":
            detail = (f"Alcanzaste el máximo de empresas que te asignaron "
                      f"({info['actuales']}/{info['max']}). Pídele más a tu administrador.")
        else:
            detail = "Se alcanzó el máximo de empresas del plan. Contacta a tu administrador."
        raise HTTPException(status_code=402, detail=detail)

    emp = Empresa(
        nombre=body.nombre.strip(),
        nit=body.nit.strip(),
        owner_id=current_user.id,
        cuenta_id=cuenta.id,
        activa=True,
    )
    db.add(emp)
    db.flush()
    db.add(UsuarioEmpresa(usuario_id=current_user.id, empresa_id=emp.id, rol="owner"))
    db.commit()
    db.refresh(emp)
    return EmpresaOut(id=emp.id, nombre=emp.nombre, nit=emp.nit, activa=emp.activa)


@router.patch("/{empresa_id}", response_model=EmpresaOut)
def editar_empresa(empresa_id: int, body: EmpresaUpdate, db: DB, current_user: CurrentUser):
    """El causador edita una empresa que él creó (nombre y NIT)."""
    emp = db.get(Empresa, empresa_id)
    if emp is None or emp.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if not body.nit.strip():
        raise HTTPException(status_code=400, detail="El NIT de la empresa es obligatorio")
    if _nit_duplicado(db, emp.cuenta_id, body.nit, excluir_id=emp.id):
        raise HTTPException(status_code=409, detail="Ya tienes otra empresa con ese NIT en tu cuenta.")
    emp.nombre = body.nombre.strip()
    emp.nit = body.nit.strip()
    db.commit()
    db.refresh(emp)
    return EmpresaOut(id=emp.id, nombre=emp.nombre, nit=emp.nit, activa=emp.activa)


@router.delete("/{empresa_id}")
def eliminar_empresa(empresa_id: int, db: DB, current_user: CurrentUser):
    """Elimina (desactiva) una empresa del causador. Es soft-delete: la empresa sale
    de su lista y libera un cupo, pero se conserva el histórico de causaciones que la
    referencia (no se borran datos de la base)."""
    emp = db.get(Empresa, empresa_id)
    if emp is None or emp.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    emp.activa = False
    db.commit()
    return {"ok": True}
