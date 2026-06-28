"use client";
import { useState } from "react";
import { createPortal } from "react-dom";
import { X, ArrowLeft, ChevronRight, CheckCircle2, Calendar, Hash, Building2, CreditCard } from "lucide-react";
import { fmt } from "@/lib/utils";
import type { FacturaCausadaInfo } from "@/lib/types";

interface DatosJson {
  factura: {
    numero_dian: string;
    razon_social: string;
    nit: string;
    fecha: string;
    total: number;
    tipo_proveedor?: string;
    items: { descripcion: string; base: number; cod_impuesto?: string; porcentaje?: number; valor_impuesto: number }[];
  };
  mapeos: {
    descripcion: string;
    base: number;
    cuenta_gasto: string;
    cod_impuesto: string;
    porcentaje: number;
    valor_impuesto: number;
    cuenta_impuesto_deb: string;
    cuenta_impuesto_cre: string;
    es_retencion: boolean;
    cuenta_pago: string;
    cuenta_pago_nombre?: string;
    fuente?: string;
  }[];
  tipo_comprobante: string;
  centro_costo: string;
}

interface Props {
  facturas: FacturaCausadaInfo[];
  onClose: () => void;
}

function Field({ label, value, mono = false }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{label}</p>
      <p className={`mt-0.5 truncate text-sm font-medium${mono ? " font-mono" : ""}`} style={{ color: "var(--text-primary)" }}>
        {value || "—"}
      </p>
    </div>
  );
}

function DetailView({ fc, onBack }: { fc: FacturaCausadaInfo; onBack: () => void }) {
  let datos: DatosJson | null = null;
  try {
    if (fc.datos_json) datos = JSON.parse(fc.datos_json);
  } catch { /* sin datos detallados */ }

  const mapeos = datos?.mapeos ?? [];
  const items = mapeos.filter((m) => !m.es_retencion);
  const retenciones = mapeos.filter((m) => m.es_retencion);
  const cuentaPago = mapeos.find((m) => m.cuenta_pago)?.cuenta_pago ?? null;
  const cuentaPagoNombre = mapeos.find((m) => m.cuenta_pago_nombre)?.cuenta_pago_nombre ?? null;

  return (
    <div className="flex flex-col gap-4">
      {/* Nav */}
      <button
        onClick={onBack}
        className="flex w-fit items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
        style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Volver a la lista
      </button>

      {/* Header card */}
      <div
        className="rounded-xl border p-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
      >
        <Field label="N° Factura DIAN" value={fc.numero_dian} mono />
        <Field label="Fecha emisión" value={fc.fecha_factura} />
        <div className="col-span-2">
          <Field label="Proveedor" value={fc.razon_social} />
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Total factura</p>
          <p className="mt-0.5 text-xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmt(fc.total ?? 0)}</p>
        </div>
      </div>

      {/* Causación info */}
      <div
        className="rounded-xl border px-4 py-3 flex flex-wrap gap-6"
        style={{ borderColor: "color-mix(in srgb, var(--success) 35%, transparent)", backgroundColor: "color-mix(in srgb, var(--success) 8%, transparent)" }}
      >
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "var(--success)" }} />
          <div>
            <p className="text-xs" style={{ color: "var(--success)", opacity: 0.8 }}>Causada el</p>
            <p className="text-sm font-semibold" style={{ color: "var(--success)" }}>{fc.fecha_causacion ?? "—"}</p>
          </div>
        </div>
        {fc.consecutivo && (
          <div className="flex items-center gap-2">
            <Hash className="h-4 w-4 shrink-0" style={{ color: "var(--success)" }} />
            <div>
              <p className="text-xs" style={{ color: "var(--success)", opacity: 0.8 }}>Consecutivo SIIGO</p>
              <p className="text-sm font-semibold font-mono" style={{ color: "var(--success)" }}>{fc.consecutivo}</p>
            </div>
          </div>
        )}
        {fc.nit_proveedor && (
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 shrink-0" style={{ color: "var(--success)" }} />
            <div>
              <p className="text-xs" style={{ color: "var(--success)", opacity: 0.8 }}>NIT</p>
              <p className="text-sm font-semibold font-mono" style={{ color: "var(--success)" }}>{fc.nit_proveedor}</p>
            </div>
          </div>
        )}
        {cuentaPago && (
          <div className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 shrink-0" style={{ color: "var(--success)" }} />
            <div>
              <p className="text-xs" style={{ color: "var(--success)", opacity: 0.8 }}>Cuenta de pago</p>
              <p className="text-sm font-semibold font-mono" style={{ color: "var(--success)" }}>
                {cuentaPago}{cuentaPagoNombre ? ` – ${cuentaPagoNombre}` : ""}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Items causados */}
      {items.length > 0 && (
        <div
          className="overflow-hidden rounded-xl border"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
        >
          <div className="px-4 py-3 border-b" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Ítems causados</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                  {["Descripción", "Base", "Impuesto", "Cuenta gasto/costo"].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((m, i) => (
                  <tr key={i} style={{ borderBottom: i < items.length - 1 ? "1px solid var(--border-soft)" : "none" }}>
                    <td className="px-4 py-3 max-w-[280px]">
                      <p className="truncate text-sm" style={{ color: "var(--text-secondary)" }} title={m.descripcion}>{m.descripcion}</p>
                    </td>
                    <td className="px-4 py-3 tabular-nums font-medium" style={{ color: "var(--success)" }}>{fmt(m.base)}</td>
                    <td className="px-4 py-3">
                      {m.cod_impuesto ? (
                        <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: "var(--info-bg)", color: "var(--info-text)", border: "1px solid var(--info-border)" }}>
                          {m.cod_impuesto} · {m.porcentaje}%
                        </span>
                      ) : <span className="text-xs" style={{ color: "var(--text-muted)" }}>—</span>}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs font-semibold" style={{ color: "var(--brand)" }}>
                      {m.cuenta_gasto || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Retenciones */}
      {retenciones.length > 0 && (
        <div
          className="overflow-hidden rounded-xl border"
          style={{ borderColor: "var(--info-border)", backgroundColor: "var(--bg-surface)" }}
        >
          <div className="px-4 py-3 border-b" style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}>
            <p className="text-sm font-semibold" style={{ color: "var(--info-text)" }}>Retenciones aplicadas</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[500px] text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                  {["Tipo", "Base", "Porcentaje", "Valor", "Cuenta crédito"].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {retenciones.map((m, i) => (
                  <tr key={i} style={{ borderBottom: i < retenciones.length - 1 ? "1px solid var(--border-soft)" : "none" }}>
                    <td className="px-4 py-3">
                      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{m.descripcion}</p>
                    </td>
                    <td className="px-4 py-3 tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{fmt(m.base)}</td>
                    <td className="px-4 py-3 tabular-nums text-sm" style={{ color: "var(--text-secondary)" }}>{m.porcentaje}%</td>
                    <td className="px-4 py-3 tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{fmt(m.valor_impuesto)}</td>
                    <td className="px-4 py-3 font-mono text-xs font-semibold" style={{ color: "var(--brand)" }}>
                      {m.cuenta_impuesto_cre || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!datos && (
        <p className="text-sm text-center py-6" style={{ color: "var(--text-muted)" }}>
          No hay datos detallados disponibles para esta factura.
        </p>
      )}
    </div>
  );
}

export function CausadasModal({ facturas, onClose }: Props) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="flex w-full max-w-5xl flex-col rounded-2xl border shadow-2xl"
        style={{
          maxHeight: "90vh",
          borderColor: "var(--border-soft)",
          backgroundColor: "var(--bg-page)",
        }}
      >
        {/* Modal header */}
        <div
          className="flex items-center justify-between border-b px-6 py-4 shrink-0"
          style={{ borderColor: "var(--border-soft)" }}
        >
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              Facturas ya causadas
            </h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
              {facturas.length} factura{facturas.length !== 1 ? "s" : ""} · solo lectura
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

        {/* Modal body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {selectedIdx === null ? (
            /* ── LIST VIEW ── */
            <div
              className="overflow-hidden rounded-xl border"
              style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
            >
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                    {["#", "N° Factura", "Proveedor / NIT", "Fecha", "Total", "Consecutivo", "Causada el", ""].map((h) => (
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
                  {facturas.map((fc, idx) => (
                    <tr
                      key={idx}
                      style={{ borderBottom: idx < facturas.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                    >
                      <td className="px-4 py-3">
                        <div
                          className="flex h-7 w-7 items-center justify-center rounded-lg text-xs font-semibold"
                          style={{ backgroundColor: "color-mix(in srgb, var(--success) 15%, transparent)", color: "var(--success)", border: "1px solid color-mix(in srgb, var(--success) 30%, transparent)" }}
                        >
                          {idx + 1}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                        {fc.numero_dian}
                      </td>
                      <td className="max-w-[200px] px-4 py-3">
                        <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }} title={fc.razon_social ?? ""}>
                          {fc.razon_social ?? "—"}
                        </p>
                        <p className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>{fc.nit_proveedor}</p>
                      </td>
                      <td className="px-4 py-3 text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>{fc.fecha_factura ?? "—"}</td>
                      <td className="px-4 py-3 font-mono text-sm font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
                        {fmt(fc.total ?? 0)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--brand)" }}>{fc.consecutivo ?? "—"}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>{fc.fecha_causacion ?? "—"}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setSelectedIdx(idx)}
                          className="flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80"
                          style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)", backgroundColor: "var(--bg-elevated)" }}
                        >
                          Ver detalle <ChevronRight className="h-3 w-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            /* ── DETAIL VIEW ── */
            <DetailView fc={facturas[selectedIdx]} onBack={() => setSelectedIdx(null)} />
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
