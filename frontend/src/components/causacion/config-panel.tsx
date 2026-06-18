"use client";
import { useWizardStore } from "@/stores/wizard";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AlertTriangle, History, RotateCcw, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { fmt } from "@/lib/utils";
import { useState } from "react";
import { cn } from "@/lib/utils";

export function ConfigPanel() {
  const { tipoComp, setTipoComp, centroCosto, setCentroCosto, reset } = useWizardStore();
  const [histOpen, setHistOpen] = useState(false);
  const [consecutivoManual, setConsecutivoManual] = useState(0);

  const { data: tipos = [] } = useQuery({ queryKey: ["tipos-comp"], queryFn: api.getTiposComprobante });
  const { data: consec, refetch: refetchConsec } = useQuery({
    queryKey: ["consecutivo", tipoComp],
    queryFn: () => api.getConsecutivo(tipoComp),
    enabled: !!tipoComp,
  });
  const { data: historial = [] } = useQuery({ queryKey: ["historial"], queryFn: api.getHistorial });

  const handleSetConsec = async () => {
    if (!tipoComp || consecutivoManual <= 0) return;
    await api.setConsecutivo(tipoComp, consecutivoManual);
    refetchConsec();
    setConsecutivoManual(0);
  };

  return (
    <aside
      className="w-72 shrink-0 overflow-y-auto px-5 py-6 space-y-6"
      style={{
        backgroundColor: "var(--sidebar-bg)",
        borderLeft: "1px solid var(--sidebar-border)",
      }}
    >
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--sidebar-label)] mb-3">Área de configuración</p>

        {/* Tipo comprobante */}
        <div className="space-y-2">
          <label className="text-xs text-[var(--sidebar-text)]">Tipo de comprobante</label>
          <Combobox
            options={tipos.map((t) => ({ value: t.codigo, label: `${t.codigo} — ${t.titulo}` }))}
            value={tipoComp}
            onChange={setTipoComp}
            placeholder="Selecciona un tipo..."
          />
          {!tipoComp && (
            <div className="flex items-center gap-1.5 text-xs text-amber-500">
              <AlertTriangle className="h-3 w-3" /> Obligatorio para continuar
            </div>
          )}
        </div>

        {/* Consecutivo */}
        {tipoComp && consec && (
          <div
            className="mt-3 rounded-lg p-3 space-y-2"
          style={{ backgroundColor: "var(--sidebar-icon-bg)", border: "1px solid var(--sidebar-border)" }}
          >
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">Último consecutivo</span>
              <span className="font-mono text-[var(--text-secondary)]">{consec.ultimo}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">Próximo</span>
              <span className="font-mono font-semibold text-[var(--brand)]">{consec.proximo}</span>
            </div>
            <div className="flex gap-2 pt-1">
              <input
                type="number"
                min={1}
                value={consecutivoManual || ""}
                onChange={(e) => setConsecutivoManual(Number(e.target.value))}
                placeholder="Ajustar..."
                className="min-w-0 flex-1 h-7 rounded-md px-2 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--brand)]"
                style={{
                  border: "1px solid var(--sidebar-border)",
                  backgroundColor: "var(--sidebar-icon-bg)",
                  color: "var(--sidebar-text-active)",
                }}
              />
              <Button size="sm" variant="outline" onClick={handleSetConsec} disabled={consecutivoManual <= 0} className="h-7 shrink-0 text-xs px-2">
                Aplicar
              </Button>
            </div>
          </div>
        )}

        {/* Centro de costo */}
        <div className="mt-3 space-y-1.5">
          <label className="text-xs text-[var(--sidebar-text)]">Centro de costo</label>
          <input
            value={centroCosto}
            onChange={(e) => setCentroCosto(e.target.value)}
            placeholder="Vacío si no aplica"
            className="w-full h-9 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
            style={{
              border: "1px solid var(--sidebar-border)",
              backgroundColor: "var(--sidebar-icon-bg)",
              color: "var(--sidebar-text-active)",
            }}
          />
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--sidebar-border)", paddingTop: "1rem" }}>
        <button
          onClick={() => setHistOpen((o) => !o)}
          className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wide transition-colors"
          style={{ color: "var(--sidebar-label)" }}
        >
          <span className="flex items-center gap-1.5"><History className="h-3.5 w-3.5" /> Historial</span>
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", histOpen && "rotate-180")} />
        </button>

        {histOpen && (
          <div className="mt-3 space-y-1.5 max-h-64 overflow-y-auto">
            {historial.length === 0 ? (
              <p className="text-xs text-center py-4" style={{ color: "var(--text-muted)" }}>Sin facturas causadas aún</p>
            ) : historial.map((h, i) => (
              <div
                key={i}
                className="rounded-lg px-3 py-2"
                style={{ border: "1px solid var(--sidebar-border)", backgroundColor: "var(--sidebar-icon-bg)" }}
              >
                <p className="text-xs font-medium truncate" style={{ color: "var(--sidebar-text-active)" }}>{h.numero_dian}</p>
                <p className="text-xs truncate" style={{ color: "var(--sidebar-text)" }}>{h.razon_social}</p>
                <p className="text-xs" style={{ color: "var(--sidebar-label)" }}>{fmt(h.total)} · {h.fecha_causacion}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ borderTop: "1px solid var(--sidebar-border)", paddingTop: "1rem" }}>
        <Button variant="ghost" size="sm" onClick={reset} className="w-full" style={{ color: "var(--sidebar-label)" }}>
          <RotateCcw className="h-3.5 w-3.5 mr-1.5" /> Reiniciar sesión
        </Button>
      </div>
    </aside>
  );
}
