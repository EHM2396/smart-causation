"""006 – verificación de email, tokens, y fix FK owner_id

Revision ID: 006
Revises: 005
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. email_verificado en usuarios ──────────────────────────────────────
    op.execute("""
        ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verificado BOOLEAN DEFAULT FALSE;
    """)
    # Usuarios existentes ya verificados (registrados antes de esta migración)
    op.execute("""
        UPDATE usuarios SET email_verificado = TRUE WHERE email_verificado = FALSE;
    """)

    # ── 2. Tabla tokens_email (reset de contraseña + verificación) ────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS tokens_email (
            id          SERIAL PRIMARY KEY,
            usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            token       VARCHAR(64) UNIQUE NOT NULL,
            tipo        VARCHAR(20) NOT NULL,
            expira_at   TIMESTAMP WITH TIME ZONE NOT NULL,
            usado       BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tokens_email_token
            ON tokens_email (token);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tokens_email_usuario_id
            ON tokens_email (usuario_id);
    """)

    # ── 3. Fix FK empresas.owner_id → ON DELETE SET NULL ─────────────────────
    op.execute("""
        DO $$
        DECLARE
            _constraint TEXT;
        BEGIN
            SELECT tc.constraint_name INTO _constraint
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name   = 'empresas'
              AND kcu.column_name = 'owner_id'
              AND tc.constraint_type = 'FOREIGN KEY';

            IF _constraint IS NOT NULL THEN
                EXECUTE 'ALTER TABLE empresas DROP CONSTRAINT ' || quote_ident(_constraint);
            END IF;
        END $$;
    """)
    op.execute("""
        ALTER TABLE empresas ALTER COLUMN owner_id DROP NOT NULL;
    """)
    op.execute("""
        ALTER TABLE empresas
            ADD CONSTRAINT empresas_owner_id_fkey
            FOREIGN KEY (owner_id) REFERENCES usuarios(id) ON DELETE SET NULL;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tokens_email;")
    op.execute("ALTER TABLE usuarios DROP COLUMN IF EXISTS email_verificado;")
    op.execute("""
        ALTER TABLE empresas DROP CONSTRAINT IF EXISTS empresas_owner_id_fkey;
    """)
    op.execute("""
        ALTER TABLE empresas ALTER COLUMN owner_id SET NOT NULL;
    """)
    op.execute("""
        ALTER TABLE empresas
            ADD CONSTRAINT empresas_owner_id_fkey
            FOREIGN KEY (owner_id) REFERENCES usuarios(id);
    """)
