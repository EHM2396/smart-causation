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

// Clave de orden cronológico a partir de la fecha de emisión "DD/MM/YYYY".
// Devuelve YYYYMMDD (número); fechas inválidas van al final. Se usa siempre que
// se arma una lista NUEVA de facturas (carga manual, importador DIAN) para que
// queden de más antigua a más reciente — así SIIGO asigna los consecutivos en
// ese orden. NO se usa al restaurar un borrador ya configurado: el orden ahí
// está ligado por índice a la configuración guardada (cuenta, verificada…) y
// reordenar lo desalinearía.
export function fechaEmisionKey(fecha: string): number {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec((fecha || "").trim());
  if (!m) return Number.POSITIVE_INFINITY;
  const [, d, mo, y] = m;
  return Number(y) * 10000 + Number(mo) * 100 + Number(d);
}

/** Ordena una lista NUEVA de facturas por fecha de emisión ascendente (más
 * antigua primero). Ver fechaEmisionKey. */
export function ordenarPorFechaEmision<T extends { fecha: string }>(facturas: T[]): T[] {
  return [...facturas].sort((a, b) => fechaEmisionKey(a.fecha) - fechaEmisionKey(b.fecha));
}

/** "YYYY-MM-DD" en hora local — la fecha "en crudo" que usan los DatePicker. */
export function localYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export interface PeriodoPreset {
  id: string;
  label: string;
  desde: string;
  hasta: string;
}

/**
 * Los periodos de la pantalla de Analítica y de Formulario 300: "Este mes"
 * (en curso) y los dos periodos REALES de declaración de IVA (Art. 600 ET),
 * pero del último que ya CERRÓ, no del que está corriendo.
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
