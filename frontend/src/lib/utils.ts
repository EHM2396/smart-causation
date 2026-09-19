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
