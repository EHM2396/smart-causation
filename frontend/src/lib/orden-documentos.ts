// Orden cronológico de los documentos electrónicos (facturas, NC, ND, soporte).
//
// Regla: manda la FECHA DE EMISIÓN que trae el XML. La fecha en que el documento
// se descargó, importó o creó en ciolix NO decide su posición: si se trae
// primero septiembre y después agosto, agosto queda ANTES de septiembre. Como el
// backend asigna los consecutivos SIIGO en el orden de la lista, esto también
// evita una secuencia artificial según el momento de la descarga.
//
// Desempate entre documentos del mismo día: tipo de documento → prefijo →
// consecutivo (numérico) → CUFE. El número del documento solo se LEE para
// ordenar: nunca se modifica.
//
// Módulo sin dependencias (ni alias "@/"), para poder probarlo con `node --test`.

import type { Paso2Snapshot, Sugerencia } from "./types";

export interface DocumentoOrdenable {
  fecha: string;
  numero_dian: string;
  tipo_documento?: string;
  cufe?: string;
}

/** Clave YYYYMMDD de la fecha de emisión ("DD/MM/YYYY", el formato del parser;
 * también acepta "YYYY-MM-DD"). Fechas inválidas van al final. */
export function fechaEmisionKey(fecha: string): number {
  const f = (fecha || "").trim();
  const dmy = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(f);
  if (dmy) return Number(dmy[3]) * 10000 + Number(dmy[2]) * 100 + Number(dmy[1]);
  const ymd = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(f);
  if (ymd) return Number(ymd[1]) * 10000 + Number(ymd[2]) * 100 + Number(ymd[3]);
  return Number.POSITIVE_INFINITY;
}

// El mismo día, la factura va antes que las notas que la ajustan.
const ORDEN_TIPO: Record<string, number> = {
  factura: 0,
  documento_soporte: 0,
  nota_debito: 1,
  nota_credito: 2,
  nota_ajuste_soporte: 2,
};

/** Prefijo y consecutivo del número DIAN ("FE1234" → "FE" + "1234"). El
 * consecutivo se devuelve como TEXTO tal cual viene: solo se usa para comparar. */
export function partesNumero(numero: string): { prefijo: string; consecutivo: string } {
  const n = (numero || "").trim();
  const m = /^(.*?)(\d+)$/.exec(n);
  if (!m) return { prefijo: n.toUpperCase(), consecutivo: "" };
  return { prefijo: m[1].toUpperCase(), consecutivo: m[2] };
}

// Compara consecutivos como números sin convertirlos (no pierde precisión con
// números largos): menos dígitos significativos = menor.
function compararConsecutivo(a: string, b: string): number {
  if (!a || !b) return (a ? 0 : 1) - (b ? 0 : 1); // sin consecutivo, al final
  const x = a.replace(/^0+(?=\d)/, "");
  const y = b.replace(/^0+(?=\d)/, "");
  if (x.length !== y.length) return x.length - y.length;
  return x < y ? -1 : x > y ? 1 : 0;
}

/** Comparador cronológico: fecha de emisión → tipo → prefijo → consecutivo → CUFE. */
export function compararDocumentos(a: DocumentoOrdenable, b: DocumentoOrdenable): number {
  const fa = fechaEmisionKey(a.fecha);
  const fb = fechaEmisionKey(b.fecha);
  if (fa !== fb) return fa < fb ? -1 : 1;
  const ta = ORDEN_TIPO[a.tipo_documento ?? "factura"] ?? 3;
  const tb = ORDEN_TIPO[b.tipo_documento ?? "factura"] ?? 3;
  if (ta !== tb) return ta - tb;
  const na = partesNumero(a.numero_dian);
  const nb = partesNumero(b.numero_dian);
  if (na.prefijo !== nb.prefijo) return na.prefijo < nb.prefijo ? -1 : 1;
  const c = compararConsecutivo(na.consecutivo, nb.consecutivo);
  if (c !== 0) return c;
  const ca = a.cufe ?? "";
  const cb = b.cufe ?? "";
  return ca < cb ? -1 : ca > cb ? 1 : 0;
}

/** Copia de la lista ordenada cronológicamente (más antigua primero). */
export function ordenarPorFechaEmision<T extends DocumentoOrdenable>(facturas: T[]): T[] {
  return [...facturas].sort(compararDocumentos);
}

// ── Reordenar un borrador sin desalinear su configuración ─────────────────────
// En el paso 2 todo se guarda POR POSICIÓN: la cuenta, la verificada, etc. de la
// factura 3 vive en la clave 3, y la de sus ítems en "3_0", "3_1"… Por eso NO
// basta con ordenar las facturas: hay que mover también esas claves a la nueva
// posición de cada factura.

type Registro = Record<string, unknown>;

/** Mueve las claves por factura ("3") o por ítem ("3_1") a la nueva posición.
 * Las claves de facturas que ya no existen se descartan. */
function remapearClaves<V>(registro: Record<string, V>, nuevaPos: number[]): Record<string, V> {
  const out: Record<string, V> = {};
  for (const [k, v] of Object.entries(registro)) {
    const m = /^(\d+)(_.*)?$/.exec(k);
    if (!m) { out[k] = v; continue; }
    const destino = nuevaPos[Number(m[1])];
    if (destino === undefined) continue;
    out[`${destino}${m[2] ?? ""}`] = v;
  }
  return out;
}

export interface BorradorOrdenable<F extends DocumentoOrdenable> {
  facturas: F[];
  suggestions?: Record<string, Sugerencia> | null;
  paso2?: Paso2Snapshot | null;
}

/** Ordena las facturas del borrador por fecha de emisión y lleva consigo sus
 * sugerencias y la configuración del paso 2. Si ya estaban en orden, devuelve
 * el mismo objeto. */
export function reordenarBorrador<F extends DocumentoOrdenable, B extends BorradorOrdenable<F>>(borrador: B): B {
  const facturas = borrador.facturas ?? [];
  const orden = facturas.map((_, i) => i).sort((i, j) => compararDocumentos(facturas[i], facturas[j]) || i - j);
  if (orden.every((viejo, nuevo) => viejo === nuevo)) return borrador;

  // nuevaPos[posición vieja] = posición nueva
  const nuevaPos: number[] = [];
  orden.forEach((viejo, nuevo) => { nuevaPos[viejo] = nuevo; });

  let paso2 = borrador.paso2;
  if (paso2) {
    const remapeado: Registro = {};
    for (const [campo, valor] of Object.entries(paso2 as unknown as Registro)) {
      remapeado[campo] = valor && typeof valor === "object" && !Array.isArray(valor)
        ? remapearClaves(valor as Registro, nuevaPos)
        : valor;
    }
    paso2 = remapeado as unknown as Paso2Snapshot;
  }

  return {
    ...borrador,
    facturas: orden.map((i) => facturas[i]),
    suggestions: borrador.suggestions ? remapearClaves(borrador.suggestions, nuevaPos) : borrador.suggestions,
    paso2,
  } as B;
}
