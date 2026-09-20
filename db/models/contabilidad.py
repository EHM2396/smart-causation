"""
Modelos operacionales de contabilidad:
  - Proveedor         →  terceros registrados
  - FacturaCausada    →  historial de facturas procesadas
  - Consecutivo       →  contador por prefijo de comprobante
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column



from db.base import Base


# ─────────────────────────────────────────────────────────────────────────────
# Proveedores
# ─────────────────────────────────────────────────────────────────────────────

class Proveedor(Base):
    """
    Terceros (proveedores) que emiten facturas electrónicas a la empresa.
    Campos alineados con el formato de importación masiva de Siigo Nube.

    tipo_persona: 'juridica' | 'natural'
    cuenta_pagar: código PUC de la cuenta por pagar (ej. '22050501')
    tipo_identificacion: código DIAN (31=NIT, 13=CC, 22=CE, etc.)
    """
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ── Identificación ─────────────────────────────────────────────────────────
    nit: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    digito_verificacion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codigo_sucursal: Mapped[str | None] = mapped_column(String(10))
    tipo_identificacion: Mapped[int | None] = mapped_column(Integer, nullable=True)  # código DIAN

    # ── Tipo y nombre ──────────────────────────────────────────────────────────
    tipo_persona: Mapped[str | None] = mapped_column(String(20))        # 'juridica' | 'natural'
    razon_social: Mapped[str | None] = mapped_column(String(255))
    nombres_tercero: Mapped[str | None] = mapped_column(String(150))    # personas naturales
    apellidos_tercero: Mapped[str | None] = mapped_column(String(150))  # personas naturales
    nombre_comercial: Mapped[str | None] = mapped_column(String(255))

    # ── Ubicación ──────────────────────────────────────────────────────────────
    direccion: Mapped[str | None] = mapped_column(String(255))
    ciudad: Mapped[str | None] = mapped_column(String(100))             # texto libre (display)
    departamento: Mapped[str | None] = mapped_column(String(100))       # texto libre (display)
    codigo_pais: Mapped[str | None] = mapped_column(String(10), default="Col")
    codigo_departamento: Mapped[str | None] = mapped_column(String(10))
    codigo_ciudad_siigo: Mapped[str | None] = mapped_column(String(10))
    codigo_postal: Mapped[str | None] = mapped_column(String(10))

    # ── Contacto ───────────────────────────────────────────────────────────────
    indicativo_tel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(50))
    extension_tel: Mapped[str | None] = mapped_column(String(10))
    email: Mapped[str | None] = mapped_column(String(255))

    # ── Fiscal / Siigo ─────────────────────────────────────────────────────────
    regimen: Mapped[str | None] = mapped_column(String(50))             # texto libre
    tipo_regimen_iva: Mapped[str | None] = mapped_column(String(20))    # código Siigo (R-99-PN, RC…)
    codigo_responsabilidad: Mapped[str | None] = mapped_column(String(50))  # O-23, ZZ…
    cuenta_pagar: Mapped[str | None] = mapped_column(String(10))        # PUC cuentas por pagar

    # ── Contacto principal ─────────────────────────────────────────────────────
    nombres_contacto: Mapped[str | None] = mapped_column(String(150))
    apellidos_contacto: Mapped[str | None] = mapped_column(String(150))
    indicativo_tel_contacto: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telefono_contacto: Mapped[str | None] = mapped_column(String(50))
    extension_tel_contacto: Mapped[str | None] = mapped_column(String(10))
    email_contacto: Mapped[str | None] = mapped_column(String(255))

    # ── Flags ──────────────────────────────────────────────────────────────────
    es_cliente: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    ia_habilitada: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fuente: Mapped[str | None] = mapped_column(String(20))              # 'xml' | 'pdf' | 'manual'

    # ── Meta ───────────────────────────────────────────────────────────────────
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("nit", "empresa_id", name="uq_proveedores_nit_empresa"),
    )

    def __repr__(self) -> str:
        return f"<Proveedor {self.nit} – {self.razon_social}>"


# ─────────────────────────────────────────────────────────────────────────────
# Facturas causadas (historial de procesamiento)
# ─────────────────────────────────────────────────────────────────────────────

class FacturaCausada(Base):
    """
    Registro de cada factura procesada por el sistema.
    Sirve para evitar re-causaciones y para auditoría.
    """
    __tablename__ = "facturas_causadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True, index=True)  # quién causó (informes)
    numero_dian: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    nit_proveedor: Mapped[str | None] = mapped_column(String(20), index=True)
    razon_social: Mapped[str | None] = mapped_column(String(255))
    fecha_factura: Mapped[date | None] = mapped_column(Date)
    total: Mapped[float | None] = mapped_column(Numeric(18, 4))
    # Suma de las bases de los ítems (sin IVA). Es la cifra que vale para
    # costos/gastos/ingresos: el IVA descontable no es costo. Nula en registros
    # anteriores a este campo (backfill en scripts/backfill_base_gravable.py).
    base_gravable: Mapped[float | None] = mapped_column(Numeric(18, 4))
    consecutivo: Mapped[str | None] = mapped_column(String(20))
    tipo_comprobante: Mapped[str | None] = mapped_column(String(10))
    # Módulo de causación: "compras" | "nc" | "ventas" | "nc_ventas" | "soporte" |
    # "nc_soporte" (mismos valores que DocTipo en el frontend). Se deriva del
    # tipo_documento de la factura + si es venta, al momento de causar. Nulo en
    # registros de antes de este campo (se puede backfillear desde datos_json).
    tipo_causacion: Mapped[str | None] = mapped_column(String(20), index=True)
    fecha_causacion: Mapped[date | None] = mapped_column(Date)
    archivo_origen: Mapped[str | None] = mapped_column(String(500))
    datos_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Borrado individual del historial: SIEMPRE soft-delete (nunca se borra la fila
    # de la base de datos). Un registro "eliminado" desaparece del historial y del
    # lote de exportación, pero se conserva para auditoría y para que la factura
    # siga contando como ya causada (evita duplicarla en SIIGO).
    eliminado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    eliminado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "numero_dian", name="uq_facturas_causadas_empresa_numero"),
    )

    def __repr__(self) -> str:
        return f"<FacturaCausada {self.numero_dian} ({self.consecutivo})>"


class DocumentoDian(Base):
    """
    Documento tal como lo reporta la DIAN, traído con el token de la empresa.

    Es una verdad DISTINTA de FacturaCausada, no un duplicado: acá está lo que
    la DIAN dice que pasó, se haya causado o no. Esa diferencia es justamente
    lo que permite ver qué falta por causar.
    """
    __tablename__ = "documentos_dian"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    # compras | nc | nd | ventas | nc_ventas | nd_ventas | soporte | nc_soporte
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    numero: Mapped[str] = mapped_column(String(80), nullable=False)
    cufe: Mapped[str | None] = mapped_column(String(120))
    fecha_emision: Mapped[date | None] = mapped_column(Date)
    nit_contraparte: Mapped[str | None] = mapped_column(String(20))
    razon_social: Mapped[str | None] = mapped_column(String(255))
    total: Mapped[float | None] = mapped_column(Numeric(18, 4))
    # Suma de las bases de los ítems, sin IVA: el IVA descontable no es costo.
    base_gravable: Mapped[float | None] = mapped_column(Numeric(18, 4))
    # Ítems con su base y su tarifa — los necesita el reporte de impuestos, y
    # volver a bajarlos de la DIAN cuesta minutos.
    items_json: Mapped[str | None] = mapped_column(Text)
    traido_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("empresa_id", "tipo", "numero", name="uq_documentos_dian_empresa_tipo_numero"),
    )

    def __repr__(self) -> str:
        return f"<DocumentoDian {self.tipo} {self.numero}>"


class SincronizacionDian(Base):
    """
    Cada vez que alguien trajo información de la DIAN, y de qué periodo.

    Saber solo "cuándo se actualizó" no alcanza: si la última traída cubrió
    enero–junio y el usuario está mirando agosto, va a ver todo vacío sin
    entender por qué. El rango consultado es lo que explica eso.
    """
    __tablename__ = "sincronizaciones_dian"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    fecha_desde: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_hasta: Mapped[date] = mapped_column(Date, nullable=False)
    documentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errores: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ejecutado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<SincronizacionDian empresa={self.empresa_id} {self.fecha_desde}..{self.fecha_hasta}>"


# ─────────────────────────────────────────────────────────────────────────────
# Consecutivos por prefijo de comprobante
# ─────────────────────────────────────────────────────────────────────────────

class Consecutivo(Base):
    """
    Lleva el último número consecutivo utilizado por cada prefijo/tipo de comprobante.
    Reemplaza la tabla SQLite del mismo nombre.
    """
    __tablename__ = "consecutivos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True, index=True)
    prefijo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ultimo_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("prefijo", "empresa_id", name="uq_consecutivos_prefijo_empresa"),
    )

    def __repr__(self) -> str:
        return f"<Consecutivo {self.prefijo}={self.ultimo_num}>"
