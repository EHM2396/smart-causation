import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(n: number) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(n);
}

// Orden cronológico por fecha de emisión del XML (y para reordenar un borrador
// ya configurado sin desalinear su configuración): ver lib/orden-documentos.ts.
export { fechaEmisionKey, ordenarPorFechaEmision, reordenarBorrador } from "./orden-documentos";

/** "YYYY-MM-DD" en hora local — la fecha "en crudo" que usan los DatePicker. */
export function localYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Tope de meses por consulta en los módulos que extraen con el token DIAN
// (espejo de MAX_MESES_CONSULTA en services/dian_service.py).
export const MAX_MESES_CONSULTA = 4;
export const AVISO_TOPE_CALENDARIO =
  `Solo se permiten máximo ${MAX_MESES_CONSULTA} meses por consulta. Los días bloqueados quedan fuera de ese límite.`;

/** Último "hasta" permitido: mismo día MAX meses después, menos uno (01/01 → 30/04).
 * Si ese día no existe en el mes destino, se usa el último del mes. */
export function limiteHasta(desdeISO: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(desdeISO)) return "9999-12-31";
  const [y, m, d] = desdeISO.split("-").map(Number);
  const ultimoDia = new Date(y, m - 1 + MAX_MESES_CONSULTA + 1, 0).getDate();
  const f = new Date(y, m - 1 + MAX_MESES_CONSULTA, Math.min(d, ultimoDia));
  f.setDate(f.getDate() - 1);
  return localYMD(f);
}

export interface PeriodoPreset {
  id: string;
  label: string;
  desde: string;
  hasta: string;
}

/**
 * Los periodos de Formulario 300 y de Analítica (incluida la Analítica de
 * IVA): "Este mes" (en curso) y los dos periodos REALES de declaración de
 * IVA (Art. 600 ET) — bimestre y cuatrimestre, del último que ya CERRÓ, no
 * del que está corriendo. Nada de Trimestre/Semestre/Año: no se pidieron
 * para ninguna de las dos pantallas — el rango personalizado (los DatePicker
 * de al lado) ya cubre cualquier otro periodo que haga falta mirar.
 *
 * Antes mostraban el bimestre/cuatrimestre EN CURSO, y en cualquier mes que
 * fuera el primero de ambos periodos a la vez (enero, mayo, septiembre) los
 * tres botones daban exactamente el mismo rango que "Este mes" — parecía que
 * Bimestral y Cuatrimestral no hacían nada, porque el resultado era idéntico
 * al que ya estaba puesto. Mostrar el periodo YA CERRADO además tiene más
 * sentido para el caso real: cuando declarás, te interesa el periodo que
 * terminó, no el que todavía está corriendo.
 */
export function periodosIVA(): PeriodoPreset[] {
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth();

  const inicioBimestreActual = Math.floor(m / 2) * 2;
  const inicioCuatrimestreActual = Math.floor(m / 4) * 4;

  // `new Date(y, mes, 0)` es el último día del mes ANTERIOR a `mes` — así se
  // consigue el cierre del periodo previo sin tener que manejar a mano el
  // cambio de año (diciembre → enero ya lo resuelve el propio Date).
  const finBimestreAnterior = new Date(y, inicioBimestreActual, 0);
  const inicioBimestreAnterior = new Date(
    finBimestreAnterior.getFullYear(), finBimestreAnterior.getMonth() - 1, 1
  );

  const finCuatrimestreAnterior = new Date(y, inicioCuatrimestreActual, 0);
  const inicioCuatrimestreAnterior = new Date(
    finCuatrimestreAnterior.getFullYear(), finCuatrimestreAnterior.getMonth() - 3, 1
  );

  return [
    { id: "mes", label: "Este mes", desde: localYMD(new Date(y, m, 1)), hasta: localYMD(now) },
    { id: "bimestre", label: "Último bimestre", desde: localYMD(inicioBimestreAnterior), hasta: localYMD(finBimestreAnterior) },
    { id: "cuatrimestre", label: "Último cuatrimestre", desde: localYMD(inicioCuatrimestreAnterior), hasta: localYMD(finCuatrimestreAnterior) },
  ];
}

// Correo con dominio completo (usuario@empresa.com, usuario@empresa.com.co…).
// El input type="email" del navegador acepta "usuario@empresa" sin extensión,
// así que se valida aparte. Debe coincidir con core/correo.py del backend.
const EMAIL_RE = /^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$/;
export const MENSAJE_EMAIL_INVALIDO =
  "El correo no es válido. Revisa que esté completo, por ejemplo: usuario@empresa.com";
export function emailValido(email: string): boolean {
  const e = (email || "").trim();
  return e.length <= 254 && !e.includes("..") && EMAIL_RE.test(e);
}

// Convierte "API 401: {"detail":"..."}" en el mensaje legible del backend.
export function mensajeApiError(err: unknown, porDefecto = "Ocurrió un error. Intenta de nuevo."): string {
  const raw = err instanceof Error ? err.message : "";
  const cuerpo = raw.replace(/^API\s+\d+:\s*/, "");
  try {
    const p = JSON.parse(cuerpo);
    if (typeof p?.detail === "string") return p.detail;
    if (Array.isArray(p?.detail)) return porDefecto;
  } catch {}
  if (raw === "Failed to fetch") return "No pudimos conectar con el servidor. Revisa tu conexión e intenta de nuevo.";
  return cuerpo || porDefecto;
}
