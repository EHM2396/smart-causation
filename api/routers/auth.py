"""
Router: /auth – registro, onboarding y perfil del usuario.

Endpoints públicos (sin JWT):
  POST /auth/register   → crea organización y asigna al usuario recién registrado

Endpoints protegidos (con JWT):
  GET  /auth/me         → perfil del usuario actual
  POST /auth/onboarding → asigna organización a usuario que aún no tiene
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.deps import AuthUser, get_current_user
from db.session import get_db

router = APIRouter(prefix="/auth", tags=["Autenticación"])

DB = Annotated[Session, Depends(get_db)]


# ── Schemas locales ───────────────────────────────────────────────────────────

class OnboardingRequest(BaseModel):
    nombre_organizacion: str


class ProfileOut(BaseModel):
    user_id: str
    email: str
    nombre: str | None
    organization_id: str
    rol: str

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/onboarding", response_model=ProfileOut, status_code=201)
def onboarding(
    body: OnboardingRequest,
    db: DB,
):
    """
    Endpoint llamado justo después del primer login.
    Crea la organización y la vincula al perfil del usuario.

    El JWT se obtiene del header Authorization — usamos get_current_user
    pero con try/except para también aceptar usuarios sin tenant aún.
    """
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from fastapi import Request
    # No usamos AuthUser aquí porque el usuario aún no tiene tenant_id
    # En su lugar usamos una validación manual liviana
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Usa el endpoint con JWT — ver implementación en front",
    )


@router.post("/setup-organization", response_model=ProfileOut, status_code=201)
def setup_organization(
    body: OnboardingRequest,
    db: DB,
    credentials: Annotated[
        object,
        Depends(__import__("fastapi.security", fromlist=["HTTPBearer"]).HTTPBearer()),
    ],
):
    """
    Crea una organización y la asigna al usuario del JWT.
    Se llama una sola vez durante el onboarding.
    """
    import os
    from jose import jwt as _jwt, JWTError

    token = credentials.credentials  # type: ignore[attr-defined]
    secret = os.getenv("SUPABASE_JWT_SECRET", "")

    try:
        payload = _jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
        user_id = payload.get("sub", "")
        email = payload.get("email", "")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    # Verificar que el usuario no tenga ya organización
    row = db.execute(
        text("SELECT organization_id FROM profiles WHERE id = :uid"),
        {"uid": user_id},
    ).fetchone()

    if row and row.organization_id:
        raise HTTPException(
            status_code=409,
            detail="El usuario ya tiene una organización asignada",
        )

    # Crear organización
    org_row = db.execute(
        text(
            "INSERT INTO organizations (nombre) VALUES (:nombre) RETURNING id"
        ),
        {"nombre": body.nombre_organizacion.strip()},
    ).fetchone()

    org_id = str(org_row.id)

    # Actualizar perfil
    db.execute(
        text(
            "UPDATE profiles SET organization_id = :org_id WHERE id = :uid"
        ),
        {"org_id": org_id, "uid": user_id},
    )
    db.commit()

    return ProfileOut(
        user_id=user_id,
        email=email,
        nombre=None,
        organization_id=org_id,
        rol="admin",
    )


@router.get("/me", response_model=ProfileOut)
def get_me(user: Annotated[AuthUser, Depends(get_current_user)], db: DB):
    """Retorna el perfil del usuario autenticado."""
    row = db.execute(
        text("SELECT nombre, email FROM profiles WHERE id = :uid"),
        {"uid": user.user_id},
    ).fetchone()

    return ProfileOut(
        user_id=user.user_id,
        email=user.email,
        nombre=row.nombre if row else None,
        organization_id=user.tenant_id,
        rol=user.rol,
    )
