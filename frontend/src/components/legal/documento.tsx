import type { ReactNode } from "react";
import { BotonPDF } from "@/components/legal/boton-pdf";
import { LogoCiolixImpresion } from "@/components/logo-ciolix";
import { ENTIDAD, FECHA_VIGENCIA, VERSION_LEGAL } from "@/lib/legal";

export interface Seccion {
  id: string;
  titulo: string;
}

/**
 * Mapa id → número de sección, derivado del orden de SECCIONES.
 *
 * Evita numerar a mano: al insertar una sección nueva, tanto los títulos como
 * las referencias cruzadas del texto ("ver sección 9") se recalculan solas.
 * En un documento legal una referencia cruzada equivocada es un defecto real,
 * no cosmético.
 */
export function numeracion<T extends readonly Seccion[]>(secciones: T): Record<string, number> {
  return Object.fromEntries(secciones.map((s, i) => [s.id, i + 1]));
}

/**
 * Encabezado + índice compartido por los documentos legales.
 * El índice usa anclas hacia los `id` que renderiza <H2>.
 */
export function Documento({
  titulo,
  resumen,
  secciones,
  children,
}: {
  titulo: string;
  resumen: string;
  secciones: Seccion[];
  children: ReactNode;
}) {
  return (
    <article>
      {/* Identificación de la entidad. Solo se imprime: en pantalla ya está en
          el encabezado y el pie del layout, que la impresión oculta. */}
      <div
        className="mb-6 hidden border-b pb-3 print:block"
        style={{ borderColor: "var(--border-soft)" }}
      >
        <LogoCiolixImpresion />
        <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
          {ENTIDAD.razonSocial} — NIT {ENTIDAD.nit} — {ENTIDAD.ciudad}, {ENTIDAD.pais}
        </p>
      </div>

      <h1 className="text-2xl font-bold sm:text-3xl" style={{ color: "var(--text-primary)" }}>
        {titulo}
      </h1>

      <p className="mt-3 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {resumen}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-muted)",
            border: "1px solid var(--border-soft)",
          }}
        >
          Versión {VERSION_LEGAL}
        </span>
        <span
          className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-muted)",
            border: "1px solid var(--border-soft)",
          }}
        >
          Vigente desde el {FECHA_VIGENCIA}
        </span>
        <BotonPDF />
      </div>

      <nav
        className="mt-8 rounded-xl border p-5"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)" }}
      >
        <p
          className="text-xs font-semibold uppercase tracking-wide"
          style={{ color: "var(--text-muted)" }}
        >
          Contenido
        </p>
        <ol className="mt-3 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {secciones.map((s, i) => (
            <li key={s.id} className="text-sm">
              <a href={`#${s.id}`} style={{ color: "var(--text-secondary)" }}>
                <span style={{ color: "var(--text-muted)" }}>{i + 1}.</span> {s.titulo}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="mt-10">{children}</div>
    </article>
  );
}
