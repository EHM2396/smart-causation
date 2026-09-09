"""Capa de Cuentas (multiempresa por plan): CuentaCliente, cupos y backfill

Revision ID: 018
Revises: 017
Create Date: 2026-09-08

B1 del plan de Cuentas/Planes:
  - Tabla `cuentas_cliente` (la "Cuenta" que compra el plan y agrupa usuarios/empresas).
  - `planes`: + `max_causaciones_mes` (NULL = ilimitado) y + `visible` (False = plan oculto).
  - `usuarios`/`empresas`: + `cuenta_id`.
  - `facturas_causadas`: + `usuario_id` (quién causó, para informes).
  - Tabla `causaciones_adicionales` (top-up del plan Básico).
  - Siembra un plan oculto "Tester" (ilimitado) y hace backfill: crea una Cuenta por
    cada usuario actual y la asigna al plan Tester (para que los usuarios que ya usan
    Ciolix sigan sin límites durante las pruebas).

Idempotente: seguro de re-ejecutar. Downgrade es no-op (no se borran datos).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Tabla cuentas_cliente ──────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cuentas_cliente (
            id          SERIAL PRIMARY KEY,
            nombre      VARCHAR(255) NOT NULL,
            plan_id     INTEGER REFERENCES planes(id),
            estado      VARCHAR(20) NOT NULL DEFAULT 'activa',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    # ── 2. planes: cupo mensual + visibilidad; max_* pasan a nullable (ilimitado) ─
    conn.execute(sa.text("ALTER TABLE planes ADD COLUMN IF NOT EXISTS max_causaciones_mes INTEGER"))
    conn.execute(sa.text("ALTER TABLE planes ADD COLUMN IF NOT EXISTS visible BOOLEAN NOT NULL DEFAULT TRUE"))
    conn.execute(sa.text("ALTER TABLE planes ALTER COLUMN max_empresas DROP NOT NULL"))
    conn.execute(sa.text("ALTER TABLE planes ALTER COLUMN max_usuarios DROP NOT NULL"))

    # ── 3. cuenta_id en usuarios y empresas ───────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cuenta_id INTEGER REFERENCES cuentas_cliente(id)"))
    conn.execute(sa.text(
        "ALTER TABLE empresas ADD COLUMN IF NOT EXISTS cuenta_id INTEGER REFERENCES cuentas_cliente(id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_usuarios_cuenta_id ON usuarios (cuenta_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_empresas_cuenta_id ON empresas (cuenta_id)"))

    # ── 4. usuario_id en facturas_causadas (informes por usuario) ─────────────
    conn.execute(sa.text(
        "ALTER TABLE facturas_causadas ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES usuarios(id)"))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_facturas_causadas_usuario_id ON facturas_causadas (usuario_id)"))

    # ── 5. Tabla causaciones_adicionales (top-up Básico) ──────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS causaciones_adicionales (
            id          SERIAL PRIMARY KEY,
            cuenta_id   INTEGER NOT NULL REFERENCES cuentas_cliente(id),
            periodo     VARCHAR(7) NOT NULL,
            cantidad    INTEGER NOT NULL,
            motivo      VARCHAR(20) NOT NULL DEFAULT 'compra',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_causaciones_adicionales_cuenta ON causaciones_adicionales (cuenta_id)"))

    # ── 6. Cupo del plan base + plan oculto Tester ────────────────────────────
    conn.execute(sa.text(
        "UPDATE planes SET max_causaciones_mes = 300 "
        "WHERE lower(nombre) IN ('base', 'básico', 'basico') AND max_causaciones_mes IS NULL"))
    conn.execute(sa.text("""
        INSERT INTO planes (nombre, max_empresas, max_usuarios, max_causaciones_mes, activo, visible)
        VALUES ('Tester', NULL, NULL, NULL, TRUE, FALSE)
        ON CONFLICT (nombre) DO NOTHING
    """))

    # ── 7. Backfill de Cuentas (plan Tester) para los usuarios actuales ───────
    tester_id = conn.execute(sa.text("SELECT id FROM planes WHERE nombre = 'Tester'")).scalar()

    # 7a. Dueños: usuarios (no superadmin) con plan o que poseen alguna empresa
    owners = conn.execute(sa.text("""
        SELECT DISTINCT u.id AS id, COALESCE(NULLIF(u.nombre, ''), u.email) AS nombre
        FROM usuarios u
        WHERE u.rol <> 'admin' AND u.cuenta_id IS NULL
          AND (u.plan_id IS NOT NULL OR EXISTS (SELECT 1 FROM empresas e WHERE e.owner_id = u.id))
    """)).fetchall()
    for o in owners:
        cid = conn.execute(sa.text(
            "INSERT INTO cuentas_cliente (nombre, plan_id, estado) "
            "VALUES (:n, :p, 'activa') RETURNING id"
        ), {"n": o.nombre, "p": tester_id}).scalar()
        conn.execute(sa.text("UPDATE usuarios SET cuenta_id = :c WHERE id = :u"), {"c": cid, "u": o.id})
        conn.execute(sa.text(
            "UPDATE empresas SET cuenta_id = :c WHERE owner_id = :u AND cuenta_id IS NULL"),
            {"c": cid, "u": o.id})
        # Miembros (via usuario_empresa) de esas empresas, sin cuenta aún
        conn.execute(sa.text("""
            UPDATE usuarios SET cuenta_id = :c
            WHERE cuenta_id IS NULL AND id IN (
                SELECT ue.usuario_id FROM usuario_empresa ue
                JOIN empresas e ON e.id = ue.empresa_id WHERE e.cuenta_id = :c
            )
        """), {"c": cid})

    # 7b. Cualquier usuario real (no superadmin) que quedó sin cuenta → su propia Cuenta Tester
    rest = conn.execute(sa.text(
        "SELECT id, COALESCE(NULLIF(nombre, ''), email) AS nombre "
        "FROM usuarios WHERE rol <> 'admin' AND cuenta_id IS NULL"
    )).fetchall()
    for r in rest:
        cid = conn.execute(sa.text(
            "INSERT INTO cuentas_cliente (nombre, plan_id, estado) "
            "VALUES (:n, :p, 'activa') RETURNING id"
        ), {"n": r.nombre, "p": tester_id}).scalar()
        conn.execute(sa.text("UPDATE usuarios SET cuenta_id = :c WHERE id = :u"), {"c": cid, "u": r.id})


def downgrade() -> None:
    # No-op intencional: no se eliminan columnas/tablas ni datos.
    pass
