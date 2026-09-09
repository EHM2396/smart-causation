"""
Modelos de autenticación y multi-tenancy:
  - Plan          →  planes de suscripción (base, pro, enterprise)
  - Usuario       →  usuarios del sistema con rol (admin | user)
  - Empresa       →  empresas / tenants
  - UsuarioEmpresa → relación M:N usuario ↔ empresa
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text

from db.base import Base


class Plan(Base):
    __tablename__ = "planes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    max_empresas: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    max_usuarios: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    # Cupo de causaciones por mes calendario. NULL = ilimitado (Enterprise / Tester).
    max_causaciones_mes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cupo TOTAL de causaciones (para planes de prueba: 100 en total, no mensual). NULL = no aplica.
    max_causaciones_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Días de vigencia de la prueba (Free = 14). NULL = no es plan de prueba.
    dias_prueba: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # visible=False → plan oculto (ej. "Tester" para usuarios internos); no se muestra en la landing.
    visible: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Plan {self.nombre}>"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # admin | org_admin | causador (user)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("planes.id"), nullable=True)  # legado; el plan real vive en la Cuenta
    cuenta_id: Mapped[int | None] = mapped_column(ForeignKey("cuentas_cliente.id"), nullable=True, index=True)
    # Máximo de empresas que ESTE causador puede crear (lo asigna el admin de la
    # cuenta). NULL = sin tope propio (solo aplica el tope del plan).
    max_empresas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False)
    tutorial_pendiente: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
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
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    cuenta_id: Mapped[int | None] = mapped_column(ForeignKey("cuentas_cliente.id"), nullable=True, index=True)
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


class CuentaCliente(Base):
    """
    Cuenta (tenant) de un cliente: agrupa usuarios y empresas bajo un plan.
    Se llama "Cuenta" de cara al usuario; la tabla es `cuentas_cliente` para no
    confundir con las cuentas contables del PUC (`cuentas_contables`).
    """
    __tablename__ = "cuentas_cliente"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("planes.id"), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activa", server_default="activa")  # activa | suspendida | cancelada
    # Cuenta de prueba (Free): tiene tope total de causaciones y una fecha de vencimiento.
    es_prueba: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    prueba_expira: Mapped[date | None] = mapped_column(Date, nullable=True)  # última fecha con acceso
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CuentaCliente {self.id} {self.nombre} plan={self.plan_id} prueba={self.es_prueba}>"


class CausacionAdicional(Base):
    """
    Causaciones adicionales compradas (top-up), principalmente para el plan Básico.
    El cupo efectivo del mes = plan.max_causaciones_mes + Σ cantidad del periodo.
    """
    __tablename__ = "causaciones_adicionales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas_cliente.id"), nullable=False, index=True)
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)   # 'YYYY-MM'
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str] = mapped_column(String(20), nullable=False, default="compra")  # compra | ajuste
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<CausacionAdicional cuenta={self.cuenta_id} {self.periodo} +{self.cantidad}>"


class CupoCausacion(Base):
    """
    Cupo de causaciones asignado por el admin a un usuario (o empresa) dentro de la
    Cuenta. Es un tope adicional al del plan: el usuario no puede causar más de
    `max_mes` en el mes. `usuario_id` seteado = cupo por usuario; `empresa_id`
    seteado = cupo por empresa. Sin fila → sin límite propio (solo el del plan).
    """
    __tablename__ = "cupos_causacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(ForeignKey("cuentas_cliente.id"), nullable=False, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    max_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CupoCausacion cuenta={self.cuenta_id} u={self.usuario_id} e={self.empresa_id} max={self.max_mes}>"


class TokenEmail(Base):
    """
    Tokens de un solo uso para verificación de email y reset de contraseña.
    tipo: 'verificacion' | 'reset'
    Expiran automáticamente; se marcan como usados al consumirse.
    """
    __tablename__ = "tokens_email"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)   # 'verificacion' | 'reset'
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<TokenEmail u={self.usuario_id} tipo={self.tipo} usado={self.usado}>"
