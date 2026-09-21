"""Catálogo tributario maestro, clasificación por empresa y configuración fiscal

Revision ID: 031
Revises: 030
Create Date: 2026-09-21

Cimiento del motor del Formulario 300. Cuatro tablas:

`catalogo_tributario` — el conocimiento tributario compartido: qué tratamiento
    le corresponde a un bien o servicio, con qué norma, desde cuándo y quién lo
    validó. `cuenta_id` NULL = semilla del sistema, visible para todas las
    firmas; con valor = entrada propia de esa firma.

`catalogo_tributario_cambio` — el historial. Una clasificación nunca se
    sobrescribe: cambiar un tratamiento cierra la vigencia de la fila anterior y
    abre una nueva, y acá queda el rastro de quién hizo qué y con qué norma.

`clasificacion_empresa` — la capa de cada empresa sobre el maestro. El catálogo
    PROPONE; el contador de cada empresa acepta, modifica o crea una excepción.
    Sin esta separación, el error de un usuario se replicaría a toda la cartera.

`empresa_config_tributaria` — periodicidad de la declaración y marca de zona
    franca, por empresa y por año fiscal, configuradas por el contador (nunca
    deducidas por el sistema).

La pieza clave de todo esto son las VIGENCIAS. Cuando cambia una norma no se
corrige el pasado: se cierra la vigencia anterior y se abre una nueva. Una
operación se clasifica con lo que regía en LA FECHA DEL DOCUMENTO, no con lo que
rige hoy — por eso un reporte de un periodo ya declarado sigue dando lo mismo
aunque la norma haya cambiado después.

Idempotente; downgrade no-op.
"""
from __future__ import annotations

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Catálogo tributario maestro ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS catalogo_tributario (
            id                SERIAL PRIMARY KEY,
            -- NULL = semilla del sistema (la ven todas las firmas).
            -- Con valor = entrada propia de esa firma.
            cuenta_id         INTEGER REFERENCES cuentas_cliente(id),
            -- Texto tal como lo escribió quien lo cargó, y su forma normalizada
            -- (minúsculas, sin tildes ni espacios de más) que es la que se
            -- compara: en los datos reales el mismo concepto llega escrito de
            -- varias maneras.
            concepto          VARCHAR(500) NOT NULL,
            concepto_norm     VARCHAR(500) NOT NULL,
            categoria         VARCHAR(120),
            -- gravado_general | gravado_5 | exento | excluido | no_gravado | especial
            tratamiento       VARCHAR(30) NOT NULL,
            articulo_et       VARCHAR(80),
            fuente_normativa  VARCHAR(255),
            observaciones     TEXT,
            -- NULL en desde = rige desde siempre; NULL en hasta = sigue vigente.
            vigencia_desde    DATE,
            vigencia_hasta    DATE,
            -- pendiente | sugerida | validada | manual
            estado            VARCHAR(20) NOT NULL DEFAULT 'sugerida',
            validado_por      INTEGER REFERENCES usuarios(id),
            validado_at       TIMESTAMPTZ,
            -- Fila a la que reemplaza cuando cambió la norma: deja explícita la
            -- cadena de versiones de un mismo concepto.
            reemplaza_a       INTEGER REFERENCES catalogo_tributario(id),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_catalogo_trib_concepto
            ON catalogo_tributario (concepto_norm)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_catalogo_trib_cuenta
            ON catalogo_tributario (cuenta_id)
    """)

    # ── Historial de cambios del catálogo ────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS catalogo_tributario_cambio (
            id           SERIAL PRIMARY KEY,
            catalogo_id  INTEGER NOT NULL REFERENCES catalogo_tributario(id),
            usuario_id   INTEGER REFERENCES usuarios(id),
            -- creada | validada | modificada | reemplazada
            accion       VARCHAR(20) NOT NULL,
            detalle      TEXT,
            norma        VARCHAR(255),
            ocurrido_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_catalogo_cambio_catalogo
            ON catalogo_tributario_cambio (catalogo_id, ocurrido_at DESC)
    """)

    # ── Clasificación aplicada por empresa ───────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS clasificacion_empresa (
            id              SERIAL PRIMARY KEY,
            empresa_id      INTEGER NOT NULL REFERENCES empresas(id),
            -- NULL = vale para el concepto sin importar el proveedor.
            -- Con valor = solo para ese proveedor (el mismo texto puede
            -- significar cosas distintas según quién lo factura).
            nit_tercero     VARCHAR(20),
            concepto_norm   VARCHAR(500) NOT NULL,
            concepto        VARCHAR(500) NOT NULL,
            tratamiento     VARCHAR(30) NOT NULL,
            -- catalogo | ia | manual | heredada
            origen          VARCHAR(20) NOT NULL DEFAULT 'manual',
            -- pendiente | sugerida | validada | manual
            estado          VARCHAR(20) NOT NULL DEFAULT 'pendiente',
            -- De qué entrada del maestro salió, si salió de ahí.
            catalogo_id     INTEGER REFERENCES catalogo_tributario(id),
            -- TRUE cuando difiere de lo que dice el maestro: es la excepción que
            -- esta empresa necesita y que no debe tocar el catálogo compartido.
            es_excepcion    BOOLEAN NOT NULL DEFAULT FALSE,
            articulo_et     VARCHAR(80),
            norma           VARCHAR(255),
            vigencia_desde  DATE,
            vigencia_hasta  DATE,
            validado_por    INTEGER REFERENCES usuarios(id),
            validado_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_clasif_empresa_busqueda
            ON clasificacion_empresa (empresa_id, concepto_norm, nit_tercero)
    """)

    # ── Configuración tributaria por empresa y año fiscal ────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS empresa_config_tributaria (
            id                  SERIAL PRIMARY KEY,
            empresa_id          INTEGER NOT NULL REFERENCES empresas(id),
            anio_fiscal         INTEGER NOT NULL,
            -- bimestral | cuatrimestral | anual. La fija el contador: depende de
            -- los ingresos del año anterior y no se deduce automáticamente.
            periodicidad        VARCHAR(20) NOT NULL,
            -- Habilita la POSIBILIDAD de operaciones de zona franca. No implica
            -- que todas lo sean: cada documento conserva su propia clasificación.
            maneja_zona_franca  BOOLEAN NOT NULL DEFAULT FALSE,
            zf_vigencia_desde   DATE,
            zf_vigencia_hasta   DATE,
            configurado_por     INTEGER REFERENCES usuarios(id),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_config_trib_empresa_anio
            ON empresa_config_tributaria (empresa_id, anio_fiscal)
    """)


def downgrade() -> None:
    pass
