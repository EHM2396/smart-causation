# Hoja de Ruta — Migración Frontend + Auth + Multi-Tenant

## Stack de despliegue (100% free)

| Capa | Tecnología | Plataforma |
|---|---|---|
| Frontend | Next.js + Tailwind + shadcn/ui | Vercel (free) |
| Backend | FastAPI (actual) | Render (free) |
| Base de datos | PostgreSQL | Supabase (free, ya activo) |
| Autenticación | Supabase Auth | Supabase (free) |
| Google OAuth | Google Cloud Console | Google (free) |

---

## Fase 1 — Multi-Tenant + Supabase Auth (2-3 días)

### Objetivo
Preparar la base de datos y Supabase para soportar múltiples contadores de forma aislada.

### Pasos

1. Activar Auth en Supabase Dashboard → Authentication → Providers
2. Configurar Google OAuth:
   - Crear proyecto en Google Cloud Console → APIs & Services → Credentials
   - Crear OAuth 2.0 Client ID (tipo Web)
   - Pegar `client_id` y `client_secret` en Supabase → Auth → Providers → Google
3. Ejecutar SQL de estructura multi-tenant en Supabase SQL Editor:

```sql
-- Tenant (empresa/despacho contable)
CREATE TABLE organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre      TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Perfil de usuario vinculado a auth.users de Supabase
CREATE TABLE profiles (
  id               UUID PRIMARY KEY REFERENCES auth.users(id),
  nombre           TEXT,
  organization_id  UUID REFERENCES organizations(id),
  rol              TEXT DEFAULT 'contador',
  created_at       TIMESTAMPTZ DEFAULT now()
);

-- Añadir tenant_id a tablas de negocio existentes
ALTER TABLE proveedores           ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE facturas_causadas     ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE mapeos_puc            ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE historial_decisiones  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE reglas_clasificacion  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);
ALTER TABLE consecutivos          ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES organizations(id);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_proveedores_tenant      ON proveedores(tenant_id);
CREATE INDEX IF NOT EXISTS idx_facturas_tenant         ON facturas_causadas(tenant_id);
CREATE INDEX IF NOT EXISTS idx_mapeos_tenant           ON mapeos_puc(tenant_id);
CREATE INDEX IF NOT EXISTS idx_historial_tenant        ON historial_decisiones(tenant_id);
CREATE INDEX IF NOT EXISTS idx_consecutivos_tenant     ON consecutivos(tenant_id);
```

4. Activar Row Level Security (RLS) — cada usuario solo ve su tenant:

```sql
ALTER TABLE proveedores           ENABLE ROW LEVEL SECURITY;
ALTER TABLE facturas_causadas     ENABLE ROW LEVEL SECURITY;
ALTER TABLE mapeos_puc            ENABLE ROW LEVEL SECURITY;
ALTER TABLE historial_decisiones  ENABLE ROW LEVEL SECURITY;

-- Ejemplo de política (repetir por cada tabla)
CREATE POLICY "tenant_isolation" ON proveedores
  USING (tenant_id = (
    SELECT organization_id FROM profiles WHERE id = auth.uid()
  ));
```

5. Trigger para crear `profile` automáticamente al registrar usuario:

```sql
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO profiles (id, nombre)
  VALUES (NEW.id, NEW.raw_user_meta_data->>'full_name');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

---

## Fase 2 — FastAPI protegido con JWT de Supabase (2-3 días)

### Objetivo
Que todos los endpoints validen el JWT de Supabase y filtren datos por tenant.

### Archivos a crear/modificar

- **`api/deps.py`** — extrae `user_id` y `tenant_id` del JWT
- **`api/routers/*.py`** — añadir `Depends(get_current_tenant)` a cada router
- **`requirements_api.txt`** — añadir `python-jose[cryptography]`, `httpx`

### Lógica del middleware

```python
# api/deps.py (esquema)
# 1. Leer Authorization: Bearer <token>
# 2. Verificar firma con SUPABASE_JWT_SECRET
# 3. Extraer user_id del sub del JWT
# 4. Consultar profiles para obtener organization_id (tenant_id)
# 5. Inyectar tenant_id en todos los servicios
```

### Variable de entorno necesaria en Render
```
SUPABASE_JWT_SECRET=<JWT secret de Supabase → Settings → API → JWT Secret>
```

---

## Fase 3 — Frontend Next.js + Páginas de Auth (4-5 días)

### Objetivo
App web moderna que reemplaza Streamlit, con login normal y login con Google.

### Estructura de páginas

```
/                        → redirect a /dashboard o /login
/login                   → formulario email+password + botón Google
/register                → registro + creación de organización
/auth/callback           → callback OAuth Google (manejado por Supabase)
/onboarding              → primer uso: nombre empresa, configuración inicial
/dashboard               → resumen y acceso rápido
/causacion               → flujo de 4 pasos (carga, mapeo, validación, descarga)
/catalogos/impuestos     → gestión de impuestos
/catalogos/cuentas       → plan de cuentas PUC
/catalogos/comprobantes  → tipos de comprobante
/catalogos/ia            → control IA por proveedor
/historial               → facturas causadas anteriores
```

### Dependencias clave

```bash
npx create-next-app@latest smart-causation-front --typescript --tailwind --app
npm install @supabase/supabase-js @supabase/auth-helpers-nextjs
npm install @tanstack/react-query axios
npm install react-hook-form zod @hookform/resolvers
npm install @shadcn/ui  # componentes UI
npm install @tanstack/react-table  # tablas de ítems de factura
```

### Variables de entorno en Vercel

```
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key de Supabase>
NEXT_PUBLIC_API_URL=https://<nombre>.onrender.com
```

---

## Fase 4 — Despliegue y conexión (1-2 días)

### Vercel (Frontend)

1. `git push` del repo Next.js a GitHub
2. Conectar repo en vercel.com → New Project
3. Configurar variables de entorno (ver arriba)
4. Deploy automático en cada push a `main`
5. URL resultado: `https://smart-causation.vercel.app`

### Render (Backend FastAPI)

1. Conectar repo actual (`EHM2396/smart-causation`) en render.com
2. Crear servicio tipo Web Service → Python
3. Build command: `pip install -r requirements_api.txt`
4. Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
5. Configurar variables de entorno:
   ```
   DATABASE_URL=postgresql+psycopg2://...
   SUPABASE_JWT_SECRET=...
   OPENAI_API_KEY=...
   ```
6. URL resultado: `https://smart-causation-api.onrender.com`

### Conexión entre servicios

```
Usuario (browser)
  ↓ HTTPS
Vercel (Next.js)
  ├─→ Supabase Auth (login / registro / Google OAuth)
  └─→ Render (FastAPI) ← JWT del usuario para autorización
        └─→ Supabase PostgreSQL (datos + RLS)
```

---

## Limitaciones del free tier

| Servicio | Limitación relevante |
|---|---|
| Render | Duerme tras 15 min sin uso — primer request ~30s de espera |
| Supabase | 500MB BD, 50.000 usuarios activos/mes, 2GB bandwidth |
| Vercel | 100GB bandwidth/mes, builds ilimitados |
| Google OAuth | Sin límite para autenticación básica |

> Para pruebas y validación del producto son más que suficientes.

---

## Estrategia de ramas (Git)

Todo el desarrollo nuevo se hace en una rama separada para no afectar `main` (producción actual con Streamlit).

```
main              ← producción actual (Streamlit + FastAPI), NO tocar
└── feature/frontend-nextjs   ← todo el desarrollo nuevo aquí
```

### Crear la rama antes de empezar

```powershell
git checkout main
git pull origin main
git checkout -b feature/frontend-nextjs
git push -u origin feature/frontend-nextjs
```

### Reglas durante el desarrollo

- Todo commit del nuevo front va a `feature/frontend-nextjs`
- `main` solo recibe cambios de la app Streamlit actual
- Cuando Next.js esté validado en producción → PR de `feature/frontend-nextjs` → `main`
- Solo después de merge se apaga Streamlit

### Flujo de trabajo

```
feature/frontend-nextjs  →  PR revisado  →  merge a main  →  apagar Streamlit
```

---

## Orden de ejecución

- [ ] **Crear rama** `feature/frontend-nextjs` y hacer push a origin
- [ ] **Fase 1** — Ejecutar SQL multi-tenant en Supabase + configurar Google OAuth
- [ ] **Fase 2** — Proteger FastAPI con JWT (`api/deps.py` + `Depends`)
- [ ] **Fase 3** — Crear proyecto Next.js + páginas de auth + flujo causación
- [ ] **Fase 4** — Deploy Vercel + Render + pruebas end-to-end
- [ ] **Validación** — Probar registro, login, login con Google, causación completa, aislamiento de datos entre tenants
- [ ] **Streamlit** — Mantener activo en paralelo hasta que Next.js esté 100% validado, luego apagar
