"""Baseline: crea las tablas operacionales originales (pre-Alembic)

Revision ID: 000
Revises:
Create Date: 2026-09-03

Contexto / por qué existe esta migración
----------------------------------------
Históricamente el esquema base se creaba con ``Base.metadata.create_all()`` al
arrancar la app (Streamlit legado + ``api/main.py``), y Alembic se incorporó
después, empezando en la revisión 001. Por eso NINGUNA migración creaba las
tablas base y la 001 simplemente asumía que ``proveedores`` ya existía
(``ALTER TABLE proveedores ADD COLUMN ...``).

En una base de datos NUEVA (volumen de Postgres vacío) eso rompe con:

    (psycopg2.errors.UndefinedTable) relation "proveedores" does not exist
    [SQL: ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS ia_habilitada BOOLEAN]

Esta migración es el "baseline" que faltaba: crea las 9 tablas operacionales
originales con su esquema PRE-multiempresa. Las migraciones siguientes
(001..016) las van transformando exactamente como lo hicieron en producción
(agregan empresa_id/usuario_id, columnas Siigo, constraints por empresa, etc.).

Todo usa ``IF NOT EXISTS`` para que en bases existentes (producción) sea
totalmente inofensiva: como ya están en la revisión 016, Alembic ni siquiera
ejecuta esta migración; y aun si se ejecutara, no crearía nada duplicado.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── proveedores (terceros) ────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id           SERIAL PRIMARY KEY,
            nit          VARCHAR(20)  NOT NULL,
            tipo_persona VARCHAR(20),
            razon_social VARCHAR(255),
            direccion    VARCHAR(255),
            ciudad       VARCHAR(100),
            regimen      VARCHAR(50),
            cuenta_pagar VARCHAR(10),
            activo       BOOLEAN DEFAULT TRUE,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    # Índice único simple sobre nit (la 011 lo convierte en compuesto nit+empresa)
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_proveedores_nit ON proveedores(nit)"
    ))

    # ── facturas_causadas (historial) ─────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS facturas_causadas (
            id               SERIAL PRIMARY KEY,
            numero_dian      VARCHAR(80) NOT NULL,
            nit_proveedor    VARCHAR(20),
            razon_social     VARCHAR(255),
            fecha_factura    DATE,
            total            NUMERIC(18, 4),
            consecutivo      VARCHAR(20),
            tipo_comprobante VARCHAR(10),
            fecha_causacion  DATE,
            archivo_origen   VARCHAR(500),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    # Único global sobre numero_dian (la 009 lo pasa a compuesto empresa+numero).
    # La 009 hace drop_index SIN "IF EXISTS", por eso debe existir sí o sí.
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_facturas_causadas_numero_dian "
        "ON facturas_causadas(numero_dian)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_facturas_causadas_nit_proveedor "
        "ON facturas_causadas(nit_proveedor)"
    ))

    # ── consecutivos ──────────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS consecutivos (
            id         SERIAL PRIMARY KEY,
            prefijo    VARCHAR(20) NOT NULL,
            ultimo_num INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    # Único global sobre prefijo (la 010 lo pasa a compuesto prefijo+empresa).
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_consecutivos_prefijo ON consecutivos(prefijo)"
    ))

    # ── cuentas_contables (PUC) ───────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cuentas_contables (
            id         SERIAL PRIMARY KEY,
            codigo     VARCHAR(20)  NOT NULL,
            nombre     VARCHAR(255) NOT NULL,
            clase      SMALLINT,
            nivel      SMALLINT,
            fiscal     BOOLEAN DEFAULT FALSE,
            activo     BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_cuentas_contables_codigo "
        "ON cuentas_contables(codigo)"
    ))

    # ── codigos_impuestos ─────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS codigos_impuestos (
            id              SERIAL PRIMARY KEY,
            codigo          VARCHAR(20) NOT NULL,
            nombre          VARCHAR(255),
            tipo_impuesto   VARCHAR(50),
            tarifa          NUMERIC(8, 4),
            cta_ventas      VARCHAR(20),
            cta_compras     VARCHAR(20),
            cta_dev_ventas  VARCHAR(20),
            cta_dev_compras VARCHAR(20),
            activo          BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_codigos_impuestos_codigo "
        "ON codigos_impuestos(codigo)"
    ))

    # ── tipos_comprobante ─────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS tipos_comprobante (
            id         SERIAL PRIMARY KEY,
            codigo     VARCHAR(20)  NOT NULL,
            titulo     VARCHAR(255) NOT NULL,
            activo     BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_tipos_comprobante_codigo "
        "ON tipos_comprobante(codigo)"
    ))

    # ── mapeos_puc (aprendizaje) ──────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS mapeos_puc (
            id          SERIAL PRIMARY KEY,
            nit         VARCHAR(20),
            keyword     VARCHAR(255),
            cuenta_puc  VARCHAR(10) NOT NULL,
            descripcion TEXT,
            usos        INTEGER DEFAULT 1,
            confianza   NUMERIC(5, 4) DEFAULT 0.5,
            ultima_vez  TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_mapeos_puc_nit ON mapeos_puc(nit)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_mapeos_puc_keyword ON mapeos_puc(keyword)"))

    # ── historial_decisiones (trazabilidad) ───────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS historial_decisiones (
            id               SERIAL PRIMARY KEY,
            numero_dian      VARCHAR(80),
            nit_proveedor    VARCHAR(20),
            descripcion_item TEXT,
            cuenta_sugerida  VARCHAR(10),
            cuenta_aplicada  VARCHAR(10),
            cod_impuesto     VARCHAR(10),
            fue_corregida    BOOLEAN DEFAULT FALSE,
            origen           VARCHAR(20),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_historial_decisiones_numero_dian "
        "ON historial_decisiones(numero_dian)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_historial_decisiones_nit_proveedor "
        "ON historial_decisiones(nit_proveedor)"
    ))

    # ── reglas_clasificacion ──────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reglas_clasificacion (
            id         SERIAL PRIMARY KEY,
            version    INTEGER NOT NULL DEFAULT 1,
            patron     VARCHAR(500) NOT NULL,
            cuenta_puc VARCHAR(10)  NOT NULL,
            prioridad  INTEGER DEFAULT 0,
            activa     BOOLEAN DEFAULT TRUE,
            tipo       VARCHAR(20) DEFAULT 'keyword',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))


def downgrade() -> None:
    # Baseline: no se revierte (equivale al esquema vacío inicial).
    conn = op.get_bind()
    for tabla in [
        "reglas_clasificacion",
        "historial_decisiones",
        "mapeos_puc",
        "tipos_comprobante",
        "codigos_impuestos",
        "cuentas_contables",
        "consecutivos",
        "facturas_causadas",
        "proveedores",
    ]:
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {tabla} CASCADE"))
