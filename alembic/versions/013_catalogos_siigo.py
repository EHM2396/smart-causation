"""Catálogos Siigo: tipos de persona, regímenes IVA y responsabilidades fiscales

Revision ID: 013
Revises: 012
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Tipos de persona Siigo ────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS siigo_tipos_persona (
            id          SERIAL PRIMARY KEY,
            codigo      VARCHAR(30)  NOT NULL UNIQUE,
            descripcion VARCHAR(150) NOT NULL,
            valor_interno VARCHAR(20)
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO siigo_tipos_persona (codigo, descripcion, valor_interno) VALUES
            ('Empresa',    'Persona jurídica / Empresa', 'juridica'),
            ('Es persona', 'Persona natural',            'natural')
        ON CONFLICT (codigo) DO NOTHING
    """))

    # ── Regímenes IVA Siigo ───────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS siigo_regimenes_iva (
            id      SERIAL PRIMARY KEY,
            codigo  VARCHAR(5)   NOT NULL UNIQUE,
            etiqueta VARCHAR(100) NOT NULL
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO siigo_regimenes_iva (codigo, etiqueta) VALUES
            ('0', '0 - No responsable de IVA'),
            ('2', '2 - Responsable de IVA')
        ON CONFLICT (codigo) DO NOTHING
    """))

    # ── Responsabilidades fiscales Siigo ──────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS siigo_responsabilidades_fiscales (
            id          SERIAL PRIMARY KEY,
            codigo      VARCHAR(20)  NOT NULL UNIQUE,
            descripcion VARCHAR(200) NOT NULL
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO siigo_responsabilidades_fiscales (codigo, descripcion) VALUES
            ('O-13',   'Gran contribuyente'),
            ('O-15',   'Autorretenedor'),
            ('O-23',   'Agente de retención IVA'),
            ('O-47',   'Régimen simple de tributación - SIMPLE'),
            ('R-99-PN','No aplica - Otros (persona natural no responsable de IVA)')
        ON CONFLICT (codigo) DO NOTHING
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS siigo_responsabilidades_fiscales"))
    conn.execute(sa.text("DROP TABLE IF EXISTS siigo_regimenes_iva"))
    conn.execute(sa.text("DROP TABLE IF EXISTS siigo_tipos_persona"))
