"use client";
import { createPortal } from "react-dom";
import { X, TrendingDown, CheckCircle2, FileText } from "lucide-react";
import type { FacturaOmitida } from "@/lib/types";

interface Props {
  omitidas: FacturaOmitida[];
  onClose: () => void;
}

const MOTIVO_CONFIG = {
  venta: {
    label: "Factura de venta",
    color: "rgb(99,102,241)",
    bg: "rgba(99,102,241,0.12)",
    border: "rgba(99,102,241,0.3)",
    Icon: TrendingDown,
  },
  ya_causada: {
    label: "Ya causada",
    color: "var(--success)",
    bg: "color-mix(in srgb, var(--success) 12%, transparent)",
    border: "color-mix(in srgb, var(--success) 30%, transparent)",
    Icon: CheckCircle2,
  },
};

export function OmitidasModal({ omitidas, onClose }: Props) {
  const ventas = omitidas.filter((o) => o.motivo === "venta");
  const causadas = omitidas.filter((o) => o.motivo === "ya_causada");

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="flex w-full max-w-2xl flex-col rounded-2xl border shadow-2xl"
        style={{ maxHeight: "85vh", borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-6 py-4 shrink-0"
          style={{ borderColor: "var(--border-soft)" }}
        >
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              Facturas omitidas
            </h2>
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-primary)" }}>
              {omitidas.length} factura{omitidas.length !== 1 ? "s" : ""} no procesada{omitidas.length !== 1 ? "s" : ""}
              {ventas.length > 0 && causadas.length > 0 && (
                <> · {ventas.length} venta{ventas.length !== 1 ? "s" : ""}, {causadas.length} ya causada{causadas.length !== 1 ? "s" : ""}</>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-opacity hover:opacity-70"
            style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body — solo la tabla, scrolleable */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">
          <div
            className="overflow-hidden rounded-xl border"
            style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
          >
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                  {["#", "N° Factura", "Archivo", "Motivo"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {omitidas.map((o, idx) => {
                  const cfg = MOTIVO_CONFIG[o.motivo];
                  const Icon = cfg.Icon;
                  return (
                    <tr
                      key={idx}
                      style={{ borderBottom: idx < omitidas.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                    >
                      {/* # */}
                      <td className="px-4 py-3">
                        <div
                          className="flex h-7 w-7 items-center justify-center rounded-lg text-xs font-semibold"
                          style={{
                            backgroundColor: cfg.bg,
                            color: cfg.color,
                            border: `1px solid ${cfg.border}`,
                          }}
                        >
                          {idx + 1}
                        </div>
                      </td>

                      {/* N° Factura */}
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                          {o.numero || "—"}
                        </span>
                      </td>

                      {/* Archivo */}
                      <td className="max-w-[240px] px-4 py-3">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <FileText className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-secondary)" }} />
                          <span
                            className="truncate text-xs"
                            style={{ color: "var(--text-secondary)" }}
                            title={o.filename}
                          >
                            {o.filename || "—"}
                          </span>
                        </div>
                      </td>

                      {/* Motivo */}
                      <td className="px-4 py-3">
                        <span
                          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
                          style={{ backgroundColor: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}
                        >
                          <Icon className="h-3 w-3" />
                          {cfg.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer fijo — leyenda explicativa */}
        {(ventas.length > 0 || causadas.length > 0) && (
          <div
            className="shrink-0 border-t px-6 py-4 space-y-1.5"
            style={{ borderColor: "var(--border-soft)" }}
          >
            {ventas.length > 0 && (
              <p className="text-xs" style={{ color: "var(--text-primary)" }}>
                <span className="font-semibold" style={{ color: "rgb(99,102,241)" }}>Facturas de venta</span>
                {" "}— emitidas por tu empresa. Este módulo solo procesa compras; la causación de ventas estará disponible próximamente.
              </p>
            )}
            {causadas.length > 0 && (
              <p className="text-xs" style={{ color: "var(--text-primary)" }}>
                <span className="font-semibold" style={{ color: "var(--success)" }}>Ya causadas</span>
                {" "}— estas facturas ya fueron procesadas anteriormente y están registradas en el historial.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
