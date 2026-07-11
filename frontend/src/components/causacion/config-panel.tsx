"use client";
import { useWizardStore } from "@/stores/wizard";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AlertTriangle, History, ChevronDown, Settings2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { fmt } from "@/lib/utils";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";

export function ConfigPanel() {
  const { tipoComp, setTipoComp, centroCosto, setCentroCosto } = useWizardStore();
  const [histOpen, setHistOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [consecutivoManual, setConsecutivoManual] = useState(0);
  const [hovered, setHovered] = useState(false);
  const leaveTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    clearTimeout(leaveTimerRef.current);
    setHovered(false);
  }, [tipoComp]);

  const { data: tipos = [] } = useQuery({ queryKey: ["tipos-comp"], queryFn: api.getTiposComprobante });
  const { data: consec, refetch: refetchConsec } = useQuery({
    queryKey: ["consecutivo", tipoComp],
    queryFn: () => api.getConsecutivo(tipoComp),
    enabled: !!tipoComp,
  });
  const { data: historial = [] } = useQuery({ queryKey: ["historial"], queryFn: () => api.getHistorial() });

  const handleSetConsec = async () => {
    if (!tipoComp || consecutivoManual <= 0) return;
    await api.setConsecutivo(tipoComp, consecutivoManual);
    refetchConsec();
    setConsecutivoManual(0);
  };

  const tipoOpts = tipos.map((t) => ({ value: t.codigo, label: `${t.codigo} — ${t.titulo}` }));
  const isCollapsed = !!tipoComp && !hovered;

  // ── Shared inner content ─────────────────────────────────────────────────────
  const innerContent = (
    <>
      {/* Tipo comprobante */}
      <div data-tutorial="tipo-comprobante" className="space-y-2">
        <label className="text-xs text-[var(--sidebar-text)]">Tipo de comprobante</label>
        <Combobox
          options={tipoOpts}
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
        <div className="mt-3 rounded-xl overflow-hidden" style={{ border: "1px solid var(--border-soft)" }}>
          {/* Header con gradiente */}
          <div
            className="flex items-center justify-between px-3 py-2.5"
            style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
          >
            <span className="text-xs font-semibold text-white/90 uppercase tracking-wide">Consecutivo</span>
            <span className="font-mono text-base font-bold text-white leading-none">{consec.proximo}</span>
          </div>

          {/* Cuerpo */}
          <div className="p-3 space-y-2.5" style={{ backgroundColor: "var(--bg-surface)" }}>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>Último usado</span>
              <span className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{consec.ultimo}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>Próximo</span>
              <span
                className="font-mono text-sm font-bold px-2 py-0.5 rounded-md"
                style={{
                  backgroundColor: "color-mix(in srgb, var(--brand-btn) 12%, transparent)",
                  color: "var(--brand-btn)",
                }}
              >
                {consec.proximo}
              </span>
            </div>

            {/* Ajuste manual */}
            <div className="pt-1" style={{ borderTop: "1px solid var(--border-soft)" }}>
              <p className="text-xs mb-1.5" style={{ color: "var(--text-muted)" }}>Ajustar inicio a:</p>
              <div className="flex gap-2">
                <input
                  type="number"
                  min={1}
                  value={consecutivoManual || ""}
                  onChange={(e) => setConsecutivoManual(Number(e.target.value))}
                  placeholder="Número..."
                  className="min-w-0 flex-1 h-8 rounded-lg px-3 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
                  style={{
                    border: "1px solid var(--border-strong)",
                    backgroundColor: "var(--bg-elevated)",
                    color: "var(--text-primary)",
                  }}
                />
                <button
                  type="button"
                  onClick={handleSetConsec}
                  disabled={consecutivoManual <= 0}
                  className="h-8 shrink-0 px-3 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{
                    background: consecutivoManual > 0
                      ? "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)"
                      : "var(--bg-elevated)",
                    color: consecutivoManual > 0 ? "#fff" : "var(--text-muted)",
                    border: consecutivoManual > 0 ? "none" : "1px solid var(--border-soft)",
                  }}
                >
                  Aplicar
                </button>
              </div>
            </div>
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

      {/* Historial */}
      <div style={{ borderTop: "1px solid var(--sidebar-border)", marginTop: "1rem", paddingTop: "1rem" }}>
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
    </>
  );

  return (
    <>
      {/* ── MOBILE: collapsible top bar ─────────────────────────────────────── */}
      <div
        className="lg:hidden shrink-0"
        style={{
          backgroundColor: "var(--sidebar-bg)",
          borderBottom: "1px solid var(--sidebar-border)",
        }}
      >
        <button
          type="button"
          onClick={() => setMobileOpen((o) => !o)}
          className="flex w-full items-center justify-between px-4 py-3"
        >
          <div className="flex items-center gap-2">
            <Settings2 className="h-4 w-4" style={{ color: "var(--brand)" }} />
            <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Configuración</span>
            {!tipoComp && (
              <span className="flex items-center gap-1 text-xs text-amber-500">
                <AlertTriangle className="h-3 w-3" /> Requerida
              </span>
            )}
            {tipoComp && (
              <span
                className="rounded-full px-2 py-0.5 text-xs font-medium"
                style={{ backgroundColor: "var(--brand-subtle, #e6f4ef)", color: "var(--brand)" }}
              >
                {tipoComp}
              </span>
            )}
          </div>
          <ChevronDown className={cn("h-4 w-4 transition-transform", mobileOpen && "rotate-180")} style={{ color: "var(--text-muted)" }} />
        </button>

        {mobileOpen && (
          <div className="px-4 pb-4 space-y-0">
            {innerContent}
          </div>
        )}
      </div>

      {/* ── DESKTOP: collapsible sidebar ────────────────────────────────────── */}
      <aside
        className="hidden lg:flex lg:flex-col shrink-0 overflow-hidden"
        style={{
          width: isCollapsed ? "52px" : "288px",
          transition: "width 0.25s ease",
          backgroundColor: "var(--sidebar-bg)",
          borderLeft: "1px solid var(--sidebar-border)",
          cursor: isCollapsed ? "pointer" : "default",
        }}
        onMouseEnter={() => {
          clearTimeout(leaveTimerRef.current);
          setHovered(true);
        }}
        onMouseLeave={() => {
          leaveTimerRef.current = setTimeout(() => setHovered(false), 300);
        }}
      >
        {/* ── Collapsed strip ── */}
        <div
          className="flex flex-col items-center gap-4 py-5"
          style={{
            opacity: isCollapsed ? 1 : 0,
            transition: "opacity 0.15s ease",
            pointerEvents: isCollapsed ? "auto" : "none",
            position: isCollapsed ? "relative" : "absolute",
            width: "52px",
          }}
        >
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ backgroundColor: "color-mix(in srgb, var(--brand) 12%, transparent)" }}
          >
            <CheckCircle2 className="h-4 w-4" style={{ color: "var(--brand)" }} />
          </div>
          <span
            className="text-xs font-bold tracking-widest select-none"
            style={{
              color: "var(--brand)",
              writingMode: "vertical-rl",
              transform: "rotate(180deg)",
              letterSpacing: "0.12em",
            }}
          >
            {tipoComp}
          </span>
          <div
            className="rounded-full"
            style={{
              width: "4px",
              height: "4px",
              backgroundColor: "var(--text-muted)",
              opacity: 0.4,
            }}
          />
          <span
            className="text-[10px] font-medium select-none"
            style={{
              color: "var(--text-muted)",
              writingMode: "vertical-rl",
              transform: "rotate(180deg)",
              opacity: 0.6,
            }}
          >
            CONFIG
          </span>
        </div>

        {/* ── Expanded content ── */}
        <div
          className="flex flex-col px-5 py-6 space-y-6"
          style={{
            opacity: isCollapsed ? 0 : 1,
            transition: "opacity 0.15s ease 0.1s",
            minWidth: "288px",
            pointerEvents: isCollapsed ? "none" : "auto",
          }}
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--sidebar-label)] mb-3">Área de configuración</p>
          <div>{innerContent}</div>
        </div>
      </aside>
    </>
  );
}
