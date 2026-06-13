"""
api/deps.py – Dependencias de autenticación y tenant para FastAPI.

Flujo:
  1. El cliente envía  Authorization: Bearer <supabase_jwt>
  2. Verificamos la firma con SUPABASE_JWT_SECRET
  3. Extraemos el user_id (sub) del JWT
  4. Consultamos la tabla profiles para obtener el tenant (organization_id)
  5. Inyectamos CurrentUser en cada endpoint que lo necesite

Uso en un router:
    from api.deps import CurrentUser, get_current_user
    
    @router.get("/algo")
    def mi_endpoint(user: CurrentUser, db: DB):
        # user.tenant_id filtra los datos
        ...
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db

# ── Configuración ─────────────────────────────────────────────────────────────

def _get_jwt_secret() -> str:
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret:
        try:
            import streamlit as st
            secret = st.secrets.get("SUPABASE_JWT_SECRET", "")
        except Exception:
            pass
    return secret


_ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token inválido o expirado",
    headers={"WWW-Authenticate": "Bearer"},
)

_NO_TENANT_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Usuario sin organización asignada. Completa el onboarding.",
)


# ── Modelo de usuario autenticado ─────────────────────────────────────────────

@dataclass
class CurrentUser:
    user_id: str
    email: str
    tenant_id: str      # organization_id — UUID como str
    rol: str            # 'admin' | 'contador'


# ── Dependencias ───────────────────────────────────────────────────────────────

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """
    Valida el JWT de Supabase y retorna el usuario con su tenant_id.
    Lanza 401 si el token es inválido y 403 si el usuario no tiene organización.
    """
    token = credentials.credentials
    secret = _get_jwt_secret()

    if not secret:
        # Sin secret configurado: modo desarrollo — acepta cualquier token
        # NUNCA dejar así en producción
        import warnings
        warnings.warn("SUPABASE_JWT_SECRET no configurado — auth desactivada", stacklevel=2)
        return CurrentUser(
            user_id="dev-user",
            email="dev@local",
            tenant_id="00000000-0000-0000-0000-000000000000",
            rol="admin",
        )

    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM], audience="authenticated")
        user_id: str = payload.get("sub", "")
        email: str = payload.get("email", "")
        if not user_id:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    # Consultar tenant del usuario en profiles
    row = db.execute(
        text("SELECT organization_id, rol FROM profiles WHERE id = :uid"),
        {"uid": user_id},
    ).fetchone()

    if not row or not row.organization_id:
        raise _NO_TENANT_EXCEPTION

    return CurrentUser(
        user_id=user_id,
        email=email,
        tenant_id=str(row.organization_id),
        rol=row.rol or "contador",
    )


# Tipo anotado para usar como Depends en routers
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
