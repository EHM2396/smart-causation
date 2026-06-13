-- ─────────────────────────────────────────────────────────────────────────────
-- Fase 1: Multi-Tenant + Supabase Auth
-- Ejecutar en Supabase Dashboard → SQL Editor (en este orden)
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Tenant (empresa/despacho contable)
CREATE TABLE IF NOT EXISTS organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre      TEXT NOT NULL,
  slug        TEXT UNIQUE,                     -- para URL amigable ej. "contadores-perez"
  plan        TEXT DEFAULT 'free',             -- 'free' | 'pro' (futuro)
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 2. Perfil de usuario vinculado a auth.users de Supabase
CREATE TABLE IF NOT EXISTS profiles (
  id               UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  nombre           TEXT,
  email            TEXT,
  organization_id  UUID REFERENCES organizations(id) ON DELETE SET NULL,
  rol              TEXT DEFAULT 'contador',    -- 'admin' | 'contador'
  created_at       TIMESTAMPTZ DEFAULT now()
);

-- 3. Añadir tenant_id a tablas de negocio existentes
ALTER TABLE proveedores           ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE facturas_causadas     ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE mapeos_puc            ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE historial_decisiones  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE reglas_clasificacion  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE consecutivos          ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);

-- 4. Índices para performance
CREATE INDEX IF NOT EXISTS idx_proveedores_tenant      ON proveedores(tenant_id);
CREATE INDEX IF NOT EXISTS idx_facturas_tenant         ON facturas_causadas(tenant_id);
CREATE INDEX IF NOT EXISTS idx_mapeos_tenant           ON mapeos_puc(tenant_id);
CREATE INDEX IF NOT EXISTS idx_historial_tenant        ON historial_decisiones(tenant_id);
CREATE INDEX IF NOT EXISTS idx_reglas_tenant           ON reglas_clasificacion(tenant_id);
CREATE INDEX IF NOT EXISTS idx_consecutivos_tenant     ON consecutivos(tenant_id);

-- 5. Row Level Security (RLS) — cada usuario solo ve su tenant
ALTER TABLE organizations         ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles              ENABLE ROW LEVEL SECURITY;
ALTER TABLE proveedores           ENABLE ROW LEVEL SECURITY;
ALTER TABLE facturas_causadas     ENABLE ROW LEVEL SECURITY;
ALTER TABLE mapeos_puc            ENABLE ROW LEVEL SECURITY;
ALTER TABLE historial_decisiones  ENABLE ROW LEVEL SECURITY;
ALTER TABLE reglas_clasificacion  ENABLE ROW LEVEL SECURITY;
ALTER TABLE consecutivos          ENABLE ROW LEVEL SECURITY;

-- Función helper para obtener tenant del usuario actual
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID AS $$
  SELECT organization_id FROM profiles WHERE id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Políticas RLS por tabla
CREATE POLICY "tenant_isolation" ON proveedores
  FOR ALL USING (tenant_id = current_tenant_id());

CREATE POLICY "tenant_isolation" ON facturas_causadas
  FOR ALL USING (tenant_id = current_tenant_id());

CREATE POLICY "tenant_isolation" ON mapeos_puc
  FOR ALL USING (tenant_id = current_tenant_id());

CREATE POLICY "tenant_isolation" ON historial_decisiones
  FOR ALL USING (tenant_id = current_tenant_id());

CREATE POLICY "tenant_isolation" ON reglas_clasificacion
  FOR ALL USING (tenant_id = current_tenant_id());

CREATE POLICY "tenant_isolation" ON consecutivos
  FOR ALL USING (tenant_id = current_tenant_id());

CREATE POLICY "ver_propio_perfil" ON profiles
  FOR ALL USING (id = auth.uid());

CREATE POLICY "ver_propia_org" ON organizations
  FOR ALL USING (id = current_tenant_id());

-- 6. Trigger: crear profile automáticamente al registrar usuario
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO profiles (id, nombre, email)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', ''),
    NEW.email
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();
