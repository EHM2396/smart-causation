/**
 * Primitivas tipográficas para los documentos legales.
 *
 * Existen para que /legal/terminos y /legal/privacidad no repitan estilos inline
 * en cada párrafo. Siguen las mismas variables CSS que el resto de la app.
 */

import type { ReactNode } from "react";

export function H2({ id, num, children }: { id: string; num: number; children: ReactNode }) {
  return (
    <h2
      id={id}
      className="mt-12 scroll-mt-24 text-lg font-bold first:mt-0"
      style={{ color: "var(--text-primary)" }}
    >
      <span style={{ color: "var(--brand)" }}>{num}.</span> {children}
    </h2>
  );
}

export function H3({ children }: { children: ReactNode }) {
  return (
    <h3 className="mt-7 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
      {children}
    </h3>
  );
}

export function P({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
      {children}
    </p>
  );
}

export function UL({ children }: { children: ReactNode }) {
  return (
    <ul
      className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed"
      style={{ color: "var(--text-secondary)" }}
    >
      {children}
    </ul>
  );
}

export function OL({ children }: { children: ReactNode }) {
  return (
    <ol
      className="mt-3 list-[lower-alpha] space-y-2 pl-5 text-sm leading-relaxed"
      style={{ color: "var(--text-secondary)" }}
    >
      {children}
    </ol>
  );
}

export function Term({ children }: { children: ReactNode }) {
  return (
    <strong className="font-semibold" style={{ color: "var(--text-primary)" }}>
      {children}
    </strong>
  );
}

/** Bloque destacado para advertencias que el usuario no debe pasar por alto. */
export function Callout({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div
      className="mt-5 rounded-xl border-l-4 p-4"
      style={{
        backgroundColor: "var(--bg-elevated)",
        borderLeftColor: "var(--brand-accent)",
        border: "1px solid var(--border-soft)",
        borderLeftWidth: "4px",
        borderLeftStyle: "solid",
      }}
    >
      <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        {titulo}
      </p>
      <div className="mt-1.5 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {children}
      </div>
    </div>
  );
}

/** Tabla responsive: nunca desborda horizontalmente la página. */
export function Tabla({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return (
    <div
      className="mt-4 overflow-x-auto rounded-xl border"
      style={{ borderColor: "var(--border-soft)" }}
    >
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <thead>
          <tr style={{ backgroundColor: "var(--bg-elevated)" }}>
            {headers.map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--text-muted)" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t" style={{ borderColor: "var(--border-soft)" }}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className="px-4 py-2.5 align-top leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
