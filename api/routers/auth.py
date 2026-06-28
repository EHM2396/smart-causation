"""
Router: /auth – autenticación, registro y flujo de email.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import re

import bcrypt as _bcrypt

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import ALGORITHM, SECRET_KEY, get_current_user
from db.models.auth import Empresa, Plan, TokenEmail, Usuario, UsuarioEmpresa
from db.session import get_db
from services import email_service

router = APIRouter(prefix="/auth", tags=["Auth"])

DB = Annotated[Session, Depends(get_db)]

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 días
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://smart-causation-52ig.vercel.app")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"


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
    email_verificado: bool = True
    tutorial_pendiente: bool = True


class TutorialRequest(BaseModel):
    pendiente: bool


class EmailRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    nueva_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class MsgResponse(BaseModel):
    message: str


class PerfilUpdateRequest(BaseModel):
    nombre: str
    nombre_empresa: str
    nit_empresa: str | None = None


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    nueva_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _hash_password(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()


def _create_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _validar_complejidad_password(password: str) -> str | None:
    if len(password) < 8:
        return "Mínimo 8 caracteres"
    if not re.search(r"[A-Z]", password):
        return "Debe incluir al menos una mayúscula"
    if not re.search(r"\d", password):
        return "Debe incluir al menos un número"
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>/?\\|`~]', password):
        return "Debe incluir al menos un carácter especial"
    return None


def _empresa_del_usuario(db: Session, usuario_id: int) -> Empresa | None:
    return db.scalar(
        select(Empresa)
        .join(UsuarioEmpresa, UsuarioEmpresa.empresa_id == Empresa.id)
        .where(UsuarioEmpresa.usuario_id == usuario_id, Empresa.activa.is_(True))
        .limit(1)
    )


def _crear_token_email(db: Session, usuario_id: int, tipo: str, minutos: int) -> str:
    token = secrets.token_urlsafe(32)
    db.add(TokenEmail(
        usuario_id=usuario_id,
        token=token,
        tipo=tipo,
        expira_at=datetime.now(timezone.utc) + timedelta(minutes=minutos),
    ))
    db.flush()
    return token


def _consumir_token(db: Session, token: str, tipo: str) -> TokenEmail:
    row = db.scalar(
        select(TokenEmail).where(TokenEmail.token == token, TokenEmail.tipo == tipo)
    )
    if not row:
        raise HTTPException(status_code=400, detail="Token inválido")
    if row.usado:
        raise HTTPException(status_code=400, detail="El token ya fue utilizado")
    if row.expira_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="El token ha expirado")
    row.usado = True
    db.flush()
    return row


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
        email_verificado=usuario.email_verificado,
        tutorial_pendiente=usuario.tutorial_pendiente,
    )


@router.post("/registro", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def registro(body: RegistroRequest, background_tasks: BackgroundTasks, db: DB):
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
        email_verificado=not EMAIL_ENABLED,
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

    if EMAIL_ENABLED:
        token_verif = _crear_token_email(db, usuario.id, "verificacion", minutos=1440)
    db.commit()
    db.refresh(usuario)
    db.refresh(empresa)

    if EMAIL_ENABLED:
        enlace = f"{FRONTEND_URL}/verify-email?token={token_verif}"
        html = email_service.plantilla_verificacion(usuario.nombre, enlace)
        background_tasks.add_task(email_service.send_email, to=email, subject="Verifica tu cuenta — Smart Causación", body_html=html)

    return TokenResponse(
        access_token=_create_token(usuario.id),
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol,
        empresa_id=empresa.id,
        empresa_nombre=empresa.nombre,
        email_verificado=not EMAIL_ENABLED,
        tutorial_pendiente=True,
    )


@router.post("/forgot-password", response_model=MsgResponse)
def forgot_password(body: EmailRequest, background_tasks: BackgroundTasks, db: DB):
    if not EMAIL_ENABLED:
        return MsgResponse(message="El restablecimiento de contraseña por correo no está disponible en este momento. Contacta al administrador.")

    usuario = db.scalar(select(Usuario).where(Usuario.email == body.email.lower().strip()))
    if not usuario or not usuario.activo:
        return MsgResponse(message="Si el correo está registrado recibirás un enlace en breve.")

    token_reset = _crear_token_email(db, usuario.id, "reset", minutos=30)
    db.commit()

    enlace = f"{FRONTEND_URL}/reset-password?token={token_reset}"
    html = email_service.plantilla_recuperacion(usuario.nombre, enlace)
    background_tasks.add_task(email_service.send_email, to=usuario.email, subject="Restablece tu contraseña — Smart Causación", body_html=html)

    return MsgResponse(message="Si el correo está registrado recibirás un enlace en breve.")


@router.post("/reset-password", response_model=MsgResponse)
def reset_password(body: ResetPasswordRequest, db: DB):
    if len(body.nueva_password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    row = _consumir_token(db, body.token, "reset")
    usuario = db.get(Usuario, row.usuario_id)
    if not usuario:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")

    usuario.password_hash = _hash_password(body.nueva_password)
    db.commit()
    return MsgResponse(message="Contraseña actualizada correctamente.")


@router.post("/verify-email", response_model=MsgResponse)
def verify_email(body: VerifyEmailRequest, db: DB):
    row = _consumir_token(db, body.token, "verificacion")
    usuario = db.get(Usuario, row.usuario_id)
    if not usuario:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")

    usuario.email_verificado = True
    db.commit()
    return MsgResponse(message="Correo verificado correctamente. Ya puedes usar la plataforma.")


@router.post("/resend-verification", response_model=MsgResponse)
def resend_verification(body: EmailRequest, background_tasks: BackgroundTasks, db: DB):
    usuario = db.scalar(select(Usuario).where(Usuario.email == body.email.lower().strip()))
    if not usuario or not usuario.activo:
        return MsgResponse(message="Si el correo está registrado recibirás un nuevo enlace.")
    if usuario.email_verificado:
        return MsgResponse(message="Tu correo ya está verificado.")

    token_verif = _crear_token_email(db, usuario.id, "verificacion", minutos=1440)
    db.commit()

    enlace = f"{FRONTEND_URL}/verify-email?token={token_verif}"
    html = email_service.plantilla_verificacion(usuario.nombre, enlace)
    background_tasks.add_task(email_service.send_email, to=usuario.email, subject="Verifica tu cuenta — Smart Causación", body_html=html)

    return MsgResponse(message="Si el correo está registrado recibirás un nuevo enlace.")


@router.get("/me", response_model=dict)
def me(current_user: Annotated[Usuario, Depends(get_current_user)], db: DB):
    empresa = _empresa_del_usuario(db, current_user.id)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "nombre": current_user.nombre,
        "rol": current_user.rol,
        "email_verificado": current_user.email_verificado,
        "tutorial_pendiente": current_user.tutorial_pendiente,
        "empresa_id": empresa.id if empresa else None,
        "empresa_nombre": empresa.nombre if empresa else None,
        "empresa_nit": empresa.nit if empresa else None,
    }


@router.put("/tutorial", response_model=MsgResponse)
def actualizar_tutorial(
    body: TutorialRequest,
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: DB,
):
    current_user.tutorial_pendiente = body.pendiente
    db.commit()
    return MsgResponse(message="ok")


@router.put("/perfil", response_model=MsgResponse)
def actualizar_perfil(
    body: PerfilUpdateRequest,
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: DB,
):
    nombre = body.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")

    current_user.nombre = nombre

    empresa = _empresa_del_usuario(db, current_user.id)
    if empresa:
        nombre_empresa = body.nombre_empresa.strip()
        if not nombre_empresa:
            raise HTTPException(status_code=400, detail="El nombre de empresa no puede estar vacío")
        empresa.nombre = nombre_empresa
        empresa.nit = body.nit_empresa.strip() if body.nit_empresa else None

    db.commit()
    return MsgResponse(message="Perfil actualizado correctamente.")


@router.put("/cambiar-password", response_model=MsgResponse)
def cambiar_password(
    body: CambiarPasswordRequest,
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: DB,
):
    if not _verify_password(body.password_actual, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")

    error = _validar_complejidad_password(body.nueva_password)
    if error:
        raise HTTPException(status_code=400, detail=error)

    current_user.password_hash = _hash_password(body.nueva_password)
    db.commit()
    return MsgResponse(message="Contraseña actualizada correctamente.")
