# Smart Causación — Roadmap

## Estado actual (completado)

- Autenticación JWT (login, logout, persistencia de sesión, auto-logout por inactividad)
- Multi-tenancy completo por `empresa_id` en todas las tablas operativas y de catálogo
- Catálogos (impuestos, plan de cuentas PUC, tipos de comprobante) con carga Excel y plantilla descargable
- Aislamiento de aprendizaje por `(usuario_id, empresa_id)` — cada usuario tiene su propio historial
- Flujo de causación completo: parseo DIAN → sugerencia de cuentas → generación SIIGO
- Historial de causaciones por usuario/empresa
- Caché limpio al cerrar sesión (sin datos de sesión anterior)
- Infraestructura de producción: Render (back) + Vercel (front) + Supabase (BD), migraciones automáticas en deploy

---

## Fase 1 — Registro y acceso autónomo (próximo sprint)

El usuario debe poder registrarse y empezar a usar la plataforma sin intervención manual.

- [ ] **Registro de usuario** — formulario `/registro` funcional: nombre, email, contraseña, selección de plan
- [ ] **Verificación de email** — enviar email de confirmación antes de activar la cuenta (SendGrid o Resend)
- [ ] **Recuperación de contraseña** — flujo "olvidé mi contraseña" con enlace por email y token de un solo uso
- [ ] **Login social (Google / Microsoft)** — ver paso a paso detallado abajo
- [ ] **Onboarding post-registro** — después del primer login, guiar al usuario a crear su empresa y cargar sus catálogos

### Login social — paso a paso de implementación

La estrategia es mantener el sistema JWT actual intacto. El backend maneja todo el flujo OAuth y al final emite el mismo JWT que el login normal. El frontend solo necesita un botón.

**Cambios en base de datos (1 migración)**
```
ALTER TABLE usuarios ADD COLUMN proveedor VARCHAR(20) DEFAULT 'local';
ALTER TABLE usuarios ALTER COLUMN password_hash DROP NOT NULL;
```
- `proveedor`: `'local'` (email+contraseña) o `'google'` / `'microsoft'`
- `password_hash` pasa a ser nullable para cuentas OAuth

**Paso 1 — Google Cloud Console**
1. Ir a console.cloud.google.com → crear proyecto "Smart Causación"
2. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
3. Tipo: Web application
4. Authorized redirect URIs: `https://smart-causation.onrender.com/auth/google/callback`
   (y `http://localhost:8000/auth/google/callback` para desarrollo)
5. Guardar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` como variables de entorno en Render

**Paso 2 — Backend: nueva dependencia**
```
authlib==1.3.1   # agregar a requirements_api.txt
```

**Paso 3 — Backend: endpoints OAuth**
Crear `api/routers/oauth.py` con dos endpoints:
- `GET /auth/google` → redirige al consentimiento de Google
- `GET /auth/google/callback` → recibe el code, obtiene email de Google, busca o crea el usuario en `usuarios`, emite JWT y redirige al frontend con el token en la URL: `https://smartcausacion.com/auth/callback?token=xxx&empresa_id=yyy`

Lógica del callback:
1. Si el email ya existe en `usuarios` (proveedor local o google) → login normal, emite JWT
2. Si el email no existe → crear usuario con `proveedor='google'`, `password_hash=NULL`, asignar empresa por defecto según plan → emite JWT

**Paso 4 — Frontend: página de callback**
Crear `frontend/src/app/auth/callback/page.tsx`:
- Lee `token`, `empresa_id`, `usuario_id`, etc. de los query params de la URL
- Llama a `useAuthStore.login(data)` igual que el login normal
- Redirige a `/causacion`

**Paso 5 — Frontend: botón en login y registro**
Agregar en ambas páginas:
```tsx
<a href="https://smart-causation.onrender.com/auth/google">
  <button>Continuar con Google</button>
</a>
```

**Para agregar Microsoft/GitHub después:**
El mismo patrón se repite: registrar app en Azure AD o GitHub OAuth Apps, crear `/auth/microsoft` y `/auth/microsoft/callback`, agregar botón. El resto del sistema no cambia.

---

## Fase 2 — Planes y suscripciones

La plataforma cobra por suscripción mensual. Los límites se deben validar en backend.

| Plan        | Usuarios | Empresas | Causaciones/mes |
|-------------|----------|----------|-----------------|
| Básico      | 1        | 1        | 50              |
| Profesional | 5        | 5        | 200             |
| Firma       | 15       | 15       | 1 000           |
| Enterprise  | Ilimitado| Ilimitado| Ilimitado       |

- [ ] **Modelo de planes en BD** — tabla `planes` y FK en `empresas` / `usuarios`
- [ ] **Validación de límites en backend** — al causar, al crear usuario, al crear empresa: verificar que no se excedió el plan
- [ ] **Integración Stripe** — checkout de suscripción, webhook para activar/desactivar plan, portal de billing
- [ ] **Página de precios** — pública, sin login, con los 4 planes y botón de compra
- [ ] **Gestión de suscripción** — dentro de la plataforma: ver plan actual, upgrade, cancelar

---

## Fase 3 — Panel de administración por organización (Plan Profesional+)

Los clientes de Profesional, Firma y Enterprise reciben una **cuenta admin** para gestionar sus propios usuarios internos.

- [ ] **Rol `org_admin`** — puede crear usuarios dentro de su organización, asignar empresas y ver reportes
- [ ] **Creación y gestión de usuarios** — invitar por email, asignar empresas permitidas, activar/desactivar
- [ ] **Dashboard org admin** — tabla de usuarios: causaciones realizadas, empresas asignadas, última actividad
- [ ] **Reportes de uso por usuario** — cuántas causaciones hizo cada contador en el mes, por empresa
- [ ] **Límites por usuario** — el org admin decide cuántas empresas puede manejar cada usuario de su equipo

---

## Fase 4 — Dashboard de Corxium (super admin de la plataforma)

El admin interno de Corxium necesita visibilidad sobre todos los clientes.

- [ ] **Panel super admin** — listado de todas las empresas registradas, plan activo, última actividad, estado
- [ ] **Gestión de clientes** — activar/desactivar cuentas, cambiar plan manualmente, ver historial de pagos
- [ ] **Métricas de la plataforma** — total de causaciones, usuarios activos, MRR estimado, tasa de churn
- [ ] **Reglas de clasificación globales** — el super admin puede crear reglas que apliquen a todos los usuarios (el Motor IA ya existe, falta el UI de gestión)

---

## Fase 5 — Mejoras al flujo de causación

- [ ] **Causación en lote** — subir varios archivos DIAN a la vez y descargar un ZIP con todos los SIIGO
- [ ] **Vista previa antes de descargar** — revisar movimientos generados antes de confirmar
- [ ] **Regeneración desde historial** — re-descargar el SIIGO de una factura ya causada sin reprocesar
- [ ] **Soporte multi-empresa en UI** — el usuario puede cambiar entre sus empresas desde el topbar sin re-login
- [ ] **Clasificación automática mejorada** — usar el historial acumulado para aumentar la tasa de sugerencias correctas

---

## Pendiente técnico

- [ ] Subir imágenes de marca Corxium a `frontend/public/brand/` (logo + "desarrollado por")
- [ ] Tests automatizados básicos (endpoints críticos: login, causación, catálogos)
- [ ] Rate limiting en endpoints de auth (evitar fuerza bruta)
- [ ] Logs estructurados en producción (correlación por `empresa_id` + `usuario_id`)
