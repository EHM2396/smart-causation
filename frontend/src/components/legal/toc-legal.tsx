"use client";

import type { Seccion } from "@/components/legal/documento";

export function TocLegal({ secciones }: { secciones: Seccion[] }) {
  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
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
            <button
              type="button"
              onClick={() => scrollTo(s.id)}
              style={{
                color: "var(--text-secondary)",
                background: "none",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
                font: "inherit",
                padding: 0,
              }}
            >
              <span style={{ color: "var(--text-muted)" }}>{i + 1}.</span> {s.titulo}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
