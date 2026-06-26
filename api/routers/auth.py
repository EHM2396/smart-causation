"""
Router: /auth – autenticación y registro de usuarios.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt as _bcrypt

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import ALGORITHM, SECRET_KEY, get_current_user
from db.models.auth import Empresa, Plan, Usuario, UsuarioEmpresa
from db.session import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])

DB = Annotated[Session, Depends(get_db)]

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 días


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class RegistroRequest(BaseModel):
    email: str
    password: str
    nombre: str
    nombre_empresa: str
    nit_empresa: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario_id: int
    nombre: str
    email: str
    rol: str
    empresa_id: int
    empresa_nombre: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _hash_password(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()


def _create_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _empresa_del_usuario(db: Session, usuario_id: int) -> Empresa | None:
    return db.scalar(
        select(Empresa)
        .join(UsuarioEmpresa, UsuarioEmpresa.empresa_id == Empresa.id)
        .where(UsuarioEmpresa.usuario_id == usuario_id, Empresa.activa.is_(True))
        .limit(1)
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DB):
    usuario = db.scalar(select(Usuario).where(Usuario.email == body.email.lower().strip()))
    if not usuario or not _verify_password(body.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email o contraseña incorrectos")
    if not usuario.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    empresa = _empresa_del_usuario(db, usuario.id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin empresa asignada")

    return TokenResponse(
        access_token=_create_token(usuario.id),
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        empresa_id=empresa.id,
        empresa_nombre=empresa.nombre,
    )


@router.post("/registro", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def registro(body: RegistroRequest, db: DB):
    email = body.email.lower().strip()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(status_code=409, detail="El email ya está registrado")

    plan = db.scalar(select(Plan).where(Plan.nombre == "base", Plan.activo.is_(True)))

    usuario = Usuario(
        email=email,
        password_hash=_hash_password(body.password),
        nombre=body.nombre,
        rol="user",
        plan_id=plan.id if plan else None,
    )
    db.add(usuario)
    db.flush()

    empresa = Empresa(
        nombre=body.nombre_empresa,
        nit=body.nit_empresa,
        owner_id=usuario.id,
    )
    db.add(empresa)
    db.flush()

    db.add(UsuarioEmpresa(usuario_id=usuario.id, empresa_id=empresa.id, rol="owner"))
    db.commit()
    db.refresh(usuario)
    db.refresh(empresa)

    return TokenResponse(
        access_token=_create_token(usuario.id),
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        empresa_id=empresa.id,
        empresa_nombre=empresa.nombre,
    )


@router.get("/me", response_model=dict)
def me(current_user: Annotated[Usuario, Depends(get_current_user)], db: DB):
    empresa = _empresa_del_usuario(db, current_user.id)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "nombre": current_user.nombre,
        "rol": current_user.rol,
        "empresa_id": empresa.id if empresa else None,
        "empresa_nombre": empresa.nombre if empresa else None,
    }
