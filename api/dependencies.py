"""
Dependencias FastAPI para autenticación y multi-tenancy.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.auth import Empresa, Usuario, UsuarioEmpresa
from db.session import get_db

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme-use-env-var-in-production")
ALGORITHM = "HS256"


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Usuario:
    """Extrae y valida el JWT del header Authorization: Bearer <token>."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization or not authorization.startswith("Bearer "):
        raise exc
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise exc
    except JWTError:
        raise exc

    usuario = db.get(Usuario, int(user_id))
    if not usuario or not usuario.activo:
        raise exc
    return usuario


def get_empresa_activa(
    x_empresa_id: Annotated[str | None, Header()] = None,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Empresa:
    """
    Resuelve la empresa activa para el request.
    Usa X-Empresa-Id header; si no se provee, usa la primera empresa del usuario.
    """
    stmt = (
        select(Empresa)
        .join(UsuarioEmpresa, UsuarioEmpresa.empresa_id == Empresa.id)
        .where(
            UsuarioEmpresa.usuario_id == current_user.id,
            Empresa.activa.is_(True),
        )
    )
    if x_empresa_id:
        try:
            stmt = stmt.where(Empresa.id == int(x_empresa_id))
        except ValueError:
            pass

    empresa = db.scalar(stmt)
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta empresa o no tienes empresas asignadas",
        )
    return empresa
