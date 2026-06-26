"""
Modelos de autenticación y multi-tenancy:
  - Plan          →  planes de suscripción (base, pro, enterprise)
  - Usuario       →  usuarios del sistema con rol (admin | user)
  - Empresa       →  empresas / tenants
  - UsuarioEmpresa → relación M:N usuario ↔ empresa
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Plan(Base):
    __tablename__ = "planes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    max_empresas: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_usuarios: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Plan {self.nombre}>"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # admin | user
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("planes.id"), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Usuario {self.email} ({self.rol})>"


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    nit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Empresa {self.nombre}>"


class UsuarioEmpresa(Base):
    __tablename__ = "usuario_empresa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")  # owner | member

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("usuario_id", "empresa_id", name="uq_usuario_empresa"),
    )

    def __repr__(self) -> str:
        return f"<UsuarioEmpresa u={self.usuario_id} e={self.empresa_id} rol={self.rol}>"
