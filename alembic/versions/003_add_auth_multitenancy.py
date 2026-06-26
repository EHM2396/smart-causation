"""Agregar autenticación y multi-tenancy

Revision ID: 003
Revises: 002
Create Date: 2026-06-24

Crea tablas de auth (planes, usuarios, empresas, usuario_empresa),
agrega empresa_id a las tablas operacionales y sembrar 2 usuarios +
1 empresa asignando los datos existentes.

Credenciales semilla:
  admin@smartcausacion.com  /  Admin2024!   (rol: admin)
  causacion@smartcausacion.com  /  Causar2024!   (rol: user)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Tablas de auth ─────────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS planes (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(50) NOT NULL UNIQUE,
            max_empresas INTEGER NOT NULL DEFAULT 1,
            max_usuarios INTEGER NOT NULL DEFAULT 1,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            nombre VARCHAR(255) NOT NULL,
            rol VARCHAR(20) NOT NULL DEFAULT 'user',
            plan_id INTEGER REFERENCES planes(id),
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_usuarios_email ON usuarios(email)"
    ))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS empresas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) NOT NULL,
            nit VARCHAR(20),
            activa BOOLEAN NOT NULL DEFAULT TRUE,
            owner_id INTEGER NOT NULL REFERENCES usuarios(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS usuario_empresa (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
            empresa_id INTEGER NOT NULL REFERENCES empresas(id),
            rol VARCHAR(20) NOT NULL DEFAULT 'owner',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_usuario_empresa UNIQUE (usuario_id, empresa_id)
        )
    """))

    # ── 2. Columnas empresa_id en tablas operacionales ────────────────────────
    for tabla, col in [
        ("proveedores", "ix_proveedores_empresa_id"),
        ("facturas_causadas", "ix_facturas_causadas_empresa_id"),
        ("consecutivos", "ix_consecutivos_empresa_id"),
        ("mapeos_puc", "ix_mapeos_puc_empresa_id"),
        ("historial_decisiones", "ix_historial_decisiones_empresa_id"),
    ]:
        conn.execute(sa.text(
            f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id)"
        ))
        conn.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS {col} ON {tabla}(empresa_id)"
        ))

    # ── 3. Actualizar unique constraint en consecutivos ───────────────────────
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'consecutivos_prefijo_key'
                  AND conrelid = 'consecutivos'::regclass
            ) THEN
                ALTER TABLE consecutivos DROP CONSTRAINT consecutivos_prefijo_key;
            END IF;
        END $$
    """))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_consecutivos_prefijo_empresa'
                  AND conrelid = 'consecutivos'::regclass
            ) THEN
                ALTER TABLE consecutivos
                ADD CONSTRAINT uq_consecutivos_prefijo_empresa
                UNIQUE (prefijo, empresa_id);
            END IF;
        END $$
    """))

    # ── 4. Seed plan base ─────────────────────────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO planes (nombre, max_empresas, max_usuarios, activo)
        VALUES (:nombre, :max_e, :max_u, TRUE)
        ON CONFLICT (nombre) DO NOTHING
    """), {"nombre": "base", "max_e": 1, "max_u": 1})

    # ── 5. Seed usuarios ──────────────────────────────────────────────────────
    import bcrypt as _bcrypt
    admin_hash = _bcrypt.hashpw(b"Admin2024!", _bcrypt.gensalt()).decode()
    causacion_hash = _bcrypt.hashpw(b"Causar2024!", _bcrypt.gensalt()).decode()

    conn.execute(sa.text("""
        INSERT INTO usuarios (email, password_hash, nombre, rol, activo)
        VALUES (:email, :hash, :nombre, :rol, TRUE)
        ON CONFLICT (email) DO NOTHING
    """), {"email": "admin@smartcausacion.com", "hash": admin_hash, "nombre": "Administrador", "rol": "admin"})

    conn.execute(sa.text("""
        INSERT INTO usuarios (email, password_hash, nombre, rol, activo)
        VALUES (:email, :hash, :nombre, :rol, TRUE)
        ON CONFLICT (email) DO NOTHING
    """), {"email": "causacion@smartcausacion.com", "hash": causacion_hash, "nombre": "Usuario Causacion", "rol": "user"})

    # ── 6. Seed empresa (solo si no existe ninguna) ───────────────────────────
    conn.execute(sa.text("""
        INSERT INTO empresas (nombre, nit, activa, owner_id)
        SELECT 'Empresa Demo', NULL, TRUE, u.id
        FROM usuarios u
        WHERE u.email = 'causacion@smartcausacion.com'
          AND NOT EXISTS (SELECT 1 FROM empresas LIMIT 1)
    """))

    # ── 7. Vincular usuarios a la empresa ─────────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO usuario_empresa (usuario_id, empresa_id, rol)
        SELECT u.id, e.id, 'owner'
        FROM usuarios u, (SELECT MIN(id) AS id FROM empresas) e
        WHERE u.email = 'causacion@smartcausacion.com'
        ON CONFLICT (usuario_id, empresa_id) DO NOTHING
    """))
    conn.execute(sa.text("""
        INSERT INTO usuario_empresa (usuario_id, empresa_id, rol)
        SELECT u.id, e.id, 'member'
        FROM usuarios u, (SELECT MIN(id) AS id FROM empresas) e
        WHERE u.email = 'admin@smartcausacion.com'
        ON CONFLICT (usuario_id, empresa_id) DO NOTHING
    """))

    # ── 8. Asignar datos existentes a la primera empresa ─────────────────────
    for tabla in [
        "proveedores",
        "facturas_causadas",
        "consecutivos",
        "mapeos_puc",
        "historial_decisiones",
    ]:
        conn.execute(sa.text(
            f"UPDATE {tabla} SET empresa_id = (SELECT MIN(id) FROM empresas) WHERE empresa_id IS NULL"
        ))


def downgrade() -> None:
    pass
