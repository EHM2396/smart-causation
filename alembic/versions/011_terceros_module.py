"""Módulo de Terceros: tablas geo, catálogo tipos identificación, expansión proveedores

Cambios:
  1. Fix unicidad nit en proveedores → compuesta (nit, empresa_id)
  2. Nuevas tablas: tipos_identificacion, paises, departamentos, ciudades
  3. Seed de tipos_identificacion (14 códigos DIAN)
  4. Nuevas columnas en proveedores (campos Siigo)

Revision ID: 011
Revises: 010
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


_TIPOS_IDENTIFICACION = [
    (11, "Registro civil"),
    (12, "Tarjeta de identidad"),
    (13, "Cédula de ciudadanía"),
    (22, "Cédula de extranjería"),
    (21, "Tarjeta de extranjería"),
    (31, "NIT"),
    (33, "Identificación de extranjeros dif a NIT"),
    (41, "Pasaporte"),
    (42, "Documento de identificación extranjero"),
    (43, "Sin identificación del exterior o para uso definido para la DIAN"),
    (47, "Permiso especial de permanencia PEP"),
    (50, "NIT de otros país / Sin identificación del exterior"),
    (89, "Salvoconducto de permanencia"),
    (91, "NUIP"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Fix unicidad nit en proveedores ────────────────────────────────────
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_proveedores_nit"))
    conn.execute(sa.text(
        "ALTER TABLE proveedores DROP CONSTRAINT IF EXISTS proveedores_nit_key"
    ))
    conn.execute(sa.text(
        "ALTER TABLE proveedores DROP CONSTRAINT IF EXISTS uq_proveedores_nit_empresa"
    ))
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedores_nit_empresa "
        "ON proveedores(nit, empresa_id)"
    ))
    # Mantener índice no único para búsquedas rápidas por nit
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_proveedores_nit ON proveedores(nit)"
    ))

    # ── 2. Nuevas columnas en proveedores ─────────────────────────────────────
    new_cols = [
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS digito_verificacion INTEGER",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS codigo_sucursal VARCHAR(10)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS tipo_identificacion INTEGER",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS nombres_tercero VARCHAR(150)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS apellidos_tercero VARCHAR(150)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS nombre_comercial VARCHAR(255)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS departamento VARCHAR(100)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS codigo_pais VARCHAR(10) DEFAULT 'Col'",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS codigo_departamento VARCHAR(10)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS codigo_ciudad_siigo VARCHAR(10)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS codigo_postal VARCHAR(10)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS indicativo_tel INTEGER",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS telefono VARCHAR(30)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS extension_tel VARCHAR(10)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS tipo_regimen_iva VARCHAR(20)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS codigo_responsabilidad VARCHAR(50)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS nombres_contacto VARCHAR(150)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS apellidos_contacto VARCHAR(150)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS indicativo_tel_contacto INTEGER",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS telefono_contacto VARCHAR(30)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS extension_tel_contacto VARCHAR(10)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS email_contacto VARCHAR(255)",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS es_cliente BOOLEAN DEFAULT FALSE",
        "ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS fuente VARCHAR(20)",
    ]
    for sql in new_cols:
        conn.execute(sa.text(sql))

    # ── 3. Tabla tipos_identificacion ─────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS tipos_identificacion (
            id   SERIAL PRIMARY KEY,
            codigo      INTEGER NOT NULL UNIQUE,
            descripcion VARCHAR(200) NOT NULL,
            activo      BOOLEAN DEFAULT TRUE
        )
    """))

    for codigo, descripcion in _TIPOS_IDENTIFICACION:
        conn.execute(sa.text(
            "INSERT INTO tipos_identificacion (codigo, descripcion) "
            "VALUES (:c, :d) ON CONFLICT (codigo) DO NOTHING"
        ), {"c": codigo, "d": descripcion})

    # ── 4. Tabla paises ───────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS paises (
            id     SERIAL PRIMARY KEY,
            codigo VARCHAR(10) NOT NULL UNIQUE,
            nombre VARCHAR(150) NOT NULL
        )
    """))

    # ── 5. Tabla departamentos ────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS departamentos (
            id          SERIAL PRIMARY KEY,
            codigo      VARCHAR(10) NOT NULL,
            nombre      VARCHAR(150) NOT NULL,
            pais_codigo VARCHAR(10),
            CONSTRAINT uq_departamentos_codigo_pais UNIQUE (codigo, pais_codigo)
        )
    """))

    # ── 6. Tabla ciudades ─────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ciudades (
            id                  SERIAL PRIMARY KEY,
            codigo              VARCHAR(10) NOT NULL,
            nombre              VARCHAR(150) NOT NULL,
            departamento_codigo VARCHAR(10),
            pais_codigo         VARCHAR(10),
            CONSTRAINT uq_ciudades_codigo_pais UNIQUE (codigo, pais_codigo)
        )
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS ciudades"))
    conn.execute(sa.text("DROP TABLE IF EXISTS departamentos"))
    conn.execute(sa.text("DROP TABLE IF EXISTS paises"))
    conn.execute(sa.text("DROP TABLE IF EXISTS tipos_identificacion"))
    conn.execute(sa.text("DROP INDEX IF EXISTS uq_proveedores_nit_empresa"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_proveedores_nit"))
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX ix_proveedores_nit ON proveedores(nit)"
    ))
