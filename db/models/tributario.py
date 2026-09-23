"""
Modelos del motor tributario (Formulario 300):
  - CatalogoTributario        →  qué tratamiento le corresponde a un bien/servicio
  - CatalogoTributarioCambio  →  historial de ese conocimiento
  - ClasificacionEmpresa      →  lo que cada empresa acepta, cambia o excepciona
  - EmpresaConfigTributaria   →  periodicidad y zona franca por año fiscal

La idea que sostiene todo: **el catálogo PROPONE, la empresa DISPONE**. Un
tratamiento validado por el contador de una empresa se reutiliza como sugerencia
en las demás, pero nunca se aplica solo — así el conocimiento se comparte sin que
el error de un usuario se propague a toda la cartera.

La otra idea: **nada se sobrescribe**. Cuando cambia una norma se cierra la
vigencia anterior y se abre una nueva. Una operación se clasifica con lo que
regía en la FECHA DEL DOCUMENTO, no con lo que rige hoy.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# ── Vocabulario compartido ───────────────────────────────────────────────────

# Tratamiento de IVA de una operación. Son los que el Formulario 300 distingue;
# "especial" cubre lo que necesita renglón aparte (exportación, zona franca, AIU)
# y se detalla en el documento, no acá.
TRATAMIENTOS = (
    "gravado_general",   # tarifa general
    "gravado_5",         # tarifa reducida
    "exento",            # 0% CON derecho a descuento (Art. 477-481)
    "excluido",          # fuera del impuesto, SIN derecho a descuento (Art. 424)
    "no_gravado",        # fuera del ámbito del impuesto
    "especial",          # requiere tratamiento aparte
)

# De dónde viene una clasificación, y cuánto peso tiene.
# Una tarifa del XML es un DATO; el tratamiento es una interpretación posterior.
ESTADOS = (
    "pendiente",   # no hay información suficiente para determinarlo
    "sugerida",    # la propuso el catálogo o la IA — nunca es definitiva
    "validada",    # un contador la revisó y aprobó expresamente
    "manual",      # la escribió directamente un usuario
)

ORIGENES = ("catalogo", "ia", "manual", "heredada")

PERIODICIDADES = ("bimestral", "cuatrimestral", "anual")

# Bien o servicio, sugerido automáticamente por descripción (ver
# catalogo_tributario_service.sugerir_tipo_item) y confirmable por el
# contador. No es obligatorio: sin seguridad suficiente queda sin definir.
TIPOS_ITEM = ("bien", "servicio")


# ── Catálogo maestro ─────────────────────────────────────────────────────────

class CatalogoTributario(Base):
    """El conocimiento tributario: qué tratamiento le corresponde a un bien o
    servicio, con qué norma y desde cuándo.

    `cuenta_id` NULL = semilla del sistema, visible para todas las firmas.
    Con valor = entrada propia de esa firma.
    """
    __tablename__ = "catalogo_tributario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cuenta_id: Mapped[int | None] = mapped_column(ForeignKey("cuentas_cliente.id"), nullable=True, index=True)

    # El texto como lo escribió quien lo cargó, y su forma normalizada, que es
    # la que se compara: en los datos reales el mismo concepto llega escrito de
    # varias maneras ("transporte  vibro" y "transporte vibro" son el mismo).
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)
    concepto_norm: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    categoria: Mapped[str | None] = mapped_column(String(120))

    tratamiento: Mapped[str] = mapped_column(String(30), nullable=False)
    articulo_et: Mapped[str | None] = mapped_column(String(80))
    fuente_normativa: Mapped[str | None] = mapped_column(String(255))
    observaciones: Mapped[str | None] = mapped_column(Text)

    # NULL en desde = rige desde siempre. NULL en hasta = sigue vigente.
    vigencia_desde: Mapped[date | None] = mapped_column(Date)
    vigencia_hasta: Mapped[date | None] = mapped_column(Date)

    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="sugerida", server_default="sugerida")
    validado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    validado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # A qué fila reemplaza cuando cambió la norma: deja explícita la cadena de
    # versiones de un mismo concepto, sin borrar la anterior.
    reemplaza_a: Mapped[int | None] = mapped_column(ForeignKey("catalogo_tributario.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CatalogoTributario {self.concepto_norm} → {self.tratamiento} ({self.estado})>"


class CatalogoTributarioCambio(Base):
    """Historial del catálogo: quién hizo qué, cuándo y con qué norma.

    Existe porque una clasificación tributaria nunca se corrige en silencio: si
    alguien pregunta por qué un concepto cambió de tratamiento, la respuesta
    tiene que estar acá.
    """
    __tablename__ = "catalogo_tributario_cambio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalogo_id: Mapped[int] = mapped_column(ForeignKey("catalogo_tributario.id"), nullable=False, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    accion: Mapped[str] = mapped_column(String(20), nullable=False)  # creada|validada|modificada|reemplazada
    detalle: Mapped[str | None] = mapped_column(Text)
    norma: Mapped[str | None] = mapped_column(String(255))
    ocurrido_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<CatalogoTributarioCambio {self.accion} cat={self.catalogo_id}>"


# ── Clasificación por empresa ────────────────────────────────────────────────

class ClasificacionEmpresa(Base):
    """Lo que UNA empresa decidió para un concepto.

    El catálogo maestro propone; acá queda lo que el contador de esta empresa
    aceptó, cambió o excepcionó. Están separados a propósito: si fueran la misma
    tabla, la corrección de un usuario se aplicaría sola a toda la cartera.
    """
    __tablename__ = "clasificacion_empresa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)

    # NULL = vale para el concepto sin importar quién lo factura.
    # Con valor = solo para ese proveedor. El mismo texto puede significar cosas
    # distintas según el emisor: "transporte" de una empresa de maquinaria no es
    # el mismo hecho económico que el de una de transporte público.
    nit_tercero: Mapped[str | None] = mapped_column(String(20))
    # Código/referencia del producto tal como lo trae el XML
    # (SellersItemIdentification). Afina la memoria: proveedor + descripción
    # sola no alcanza cuando el mismo proveedor vende bienes y servicios
    # distintos con textos parecidos. NULL cuando el XML no la trae — la
    # búsqueda cae al fallback proveedor + descripción de siempre.
    referencia: Mapped[str | None] = mapped_column(String(120))
    concepto_norm: Mapped[str] = mapped_column(String(500), nullable=False)
    concepto: Mapped[str] = mapped_column(String(500), nullable=False)

    tratamiento: Mapped[str] = mapped_column(String(30), nullable=False)
    origen: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", server_default="manual")
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente", server_default="pendiente")

    # bien | servicio. Sugerido por descripción, confirmable en un clic. NULL
    # = sin seguridad suficiente todavía — no bloquea nada, se muestra como
    # pendiente y se sugiere de nuevo la próxima vez.
    tipo_item: Mapped[str | None] = mapped_column(String(20))

    catalogo_id: Mapped[int | None] = mapped_column(ForeignKey("catalogo_tributario.id"), nullable=True)
    # TRUE cuando difiere de lo que dice el maestro. Se marca para que se vea
    # que esta empresa tomó un camino propio, y por qué.
    es_excepcion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    articulo_et: Mapped[str | None] = mapped_column(String(80))
    norma: Mapped[str | None] = mapped_column(String(255))

    vigencia_desde: Mapped[date | None] = mapped_column(Date)
    vigencia_hasta: Mapped[date | None] = mapped_column(Date)

    validado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    validado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ClasificacionEmpresa e={self.empresa_id} {self.concepto_norm} → {self.tratamiento}>"


# ── Configuración tributaria de la empresa ───────────────────────────────────

class EmpresaConfigTributaria(Base):
    """Periodicidad de la declaración y zona franca, por empresa y año fiscal.

    La fija el contador, no el sistema: la periodicidad depende de los ingresos
    del año anterior y puede cambiar de un año a otro sin que eso altere lo ya
    declarado.
    """
    __tablename__ = "empresa_config_tributaria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    anio_fiscal: Mapped[int] = mapped_column(Integer, nullable=False)
    periodicidad: Mapped[str] = mapped_column(String(20), nullable=False)

    # Habilita la POSIBILIDAD de operaciones de zona franca. No implica que
    # todas lo sean: cada documento conserva su propia clasificación.
    maneja_zona_franca: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    zf_vigencia_desde: Mapped[date | None] = mapped_column(Date)
    zf_vigencia_hasta: Mapped[date | None] = mapped_column(Date)

    configurado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<EmpresaConfigTributaria e={self.empresa_id} {self.anio_fiscal} {self.periodicidad}>"
