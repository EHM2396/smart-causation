"""
Modelos de referencia geográfica y catálogos DIAN/Siigo:
  - TipoIdentificacion          → códigos DIAN de tipo de documento
  - Pais                        → países para importación Siigo
  - Departamento                → departamentos/estados
  - Ciudad                      → municipios/ciudades
  - SiigoTipoPersona            → Empresa / Es persona
  - SiigoRegimenIva             → 0 - No responsable / 2 - Responsable
  - SiigoResponsabilidadFiscal  → O-13, O-15, O-23, O-47, R-99-PN
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TipoIdentificacion(Base):
    """Catálogo de tipos de identificación DIAN (código 11, 13, 31, etc.)."""
    __tablename__ = "tipos_identificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<TipoIdentificacion {self.codigo} – {self.descripcion}>"


class Pais(Base):
    """País en el formato de Siigo (código de 2-3 letras)."""
    __tablename__ = "paises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)

    def __repr__(self) -> str:
        return f"<Pais {self.codigo} – {self.nombre}>"


class Departamento(Base):
    """Departamento/estado en el formato de Siigo."""
    __tablename__ = "departamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    pais_codigo: Mapped[str | None] = mapped_column(String(10))

    __table_args__ = (
        UniqueConstraint("codigo", "pais_codigo", name="uq_departamentos_codigo_pais"),
    )

    def __repr__(self) -> str:
        return f"<Departamento {self.codigo} – {self.nombre}>"


class Ciudad(Base):
    """Municipio/ciudad en el formato de Siigo."""
    __tablename__ = "ciudades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    departamento_codigo: Mapped[str | None] = mapped_column(String(10))
    pais_codigo: Mapped[str | None] = mapped_column(String(10))

    __table_args__ = (
        UniqueConstraint("codigo", "pais_codigo", name="uq_ciudades_codigo_pais"),
    )

    def __repr__(self) -> str:
        return f"<Ciudad {self.codigo} – {self.nombre}>"


class SiigoTipoPersona(Base):
    """Catálogo: tipos de persona válidos en importación Siigo ('Empresa' / 'Es persona')."""
    __tablename__ = "siigo_tipos_persona"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(150), nullable=False)
    valor_interno: Mapped[str | None] = mapped_column(String(20))

    def __repr__(self) -> str:
        return f"<SiigoTipoPersona {self.codigo}>"


class SiigoRegimenIva(Base):
    """Catálogo: regímenes IVA válidos en Siigo ('0' - No responsable / '2' - Responsable)."""
    __tablename__ = "siigo_regimenes_iva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(5), unique=True, nullable=False)
    etiqueta: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<SiigoRegimenIva {self.codigo}>"


class SiigoResponsabilidadFiscal(Base):
    """Catálogo: responsabilidades fiscales válidas en Siigo (O-13, O-15, O-23, O-47, R-99-PN)."""
    __tablename__ = "siigo_responsabilidades_fiscales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)

    def __repr__(self) -> str:
        return f"<SiigoResponsabilidadFiscal {self.codigo}>"
