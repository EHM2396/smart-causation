"use client";

import { Download } from "lucide-react";

/**
 * Abre el diálogo de impresión del navegador con destino "Guardar como PDF".
 *
 * El PDF resultante es el mismo documento publicado, con los estilos de
 * @media print de globals.css. No se genera con una librería para que no
 * exista una segunda copia del texto legal que pueda quedar desactualizada.
 */
export function BotonPDF() {
  return (
    <button
      type="button"
      data-print="hide"
      onClick={() => window.print()}
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-opacity hover:opacity-75"
      style={{
        backgroundColor: "var(--bg-elevated)",
        color: "var(--text-secondary)",
        border: "1px solid var(--border-soft)",
      }}
    >
      <Download className="h-3.5 w-3.5" />
      Descargar PDF
    </button>
  );
}
