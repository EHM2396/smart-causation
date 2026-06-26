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
- [ ] **Onboarding post-registro** — después del primer login, guiar al usuario a crear su empresa y cargar sus catálogos

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
