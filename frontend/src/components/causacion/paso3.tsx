"use client";
import { useEffect, useState } from "react";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { fmt } from "@/lib/utils";
import { CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BatchValidacionResponse } from "@/lib/types";

const TUTORIAL_REPORTE: BatchValidacionResponse = {
  comprobantes: [
    { consecutivo: 1, numero_dian: "FERM44825", total_debito: 2750000, total_credito: 2750000, diferencia: 0, cuadra: true },
    { consecutivo: 2, numero_dian: "SE-241001",  total_debito: 1190000, total_credito: 1190000, diferencia: 0, cuadra: true },
    { consecutivo: 3, numero_dian: "FE-2026001", total_debito: 580000,  total_credito: 580000,  diferencia: 0, cuadra: true },
  ],
  global_cuadra: true,
  gran_total_debitos: 4520000,
  gran_total_creditos: 4520000,
};

export function Paso3() {
  const { facturasParaCausar, mapeos, tipoComp, centroCosto, setPaso, setReporte, setXlsxBlob } = useWizardStore();
  const [reporte, setLocalReporte] = useState<BatchValidacionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generando, setGenerando] = useState(false);

  useEffect(() => {
    if (useWizardStore.getState().tutorialActivo) {
      setLocalReporte(TUTORIAL_REPORTE);
      setReporte(TUTORIAL_REPORTE);
      setLoading(false);
      return;
    }
    const run = async () => {
      setLoading(true);
      try {
        const items = facturasParaCausar.map((f, idx) => ({
          factura: f,
          mapeos_confirmados: mapeos.filter((m) => m.idx_factura === idx),
        }));
        const r = await api.batchValidar({ items, tipo_comprobante: tipoComp, centro_costo: centroCosto });
        setLocalReporte(r);
        setReporte(r);
      } catch (e) {
        setError((e as Error).message);
      }
      setLoading(false);
    };
    run();
  }, []);

  const handleGenerar = async () => {
    setGenerando(true);
    setError("");
    try {
      const items = facturas.map((f, idx) => ({
        factura: f,
        mapeos_confirmados: mapeos.filter((m) => m.idx_factura === idx),
      }));
      const blob = await api.batchGenerar({ items, tipo_comprobante: tipoComp, centro_costo: centroCosto, confirmar: false });
      setXlsxBlob(blob);
      setPaso(4);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerando(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: "var(--brand)", borderTopColor: "transparent" }} />
      <span className="ml-3 text-sm text-[var(--text-secondary)]">Validando partida doble...</span>
    </div>
  );

  if (error) return (
    <div className="flex items-center gap-3 rounded-xl border p-5" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)", color: "var(--error-text)" }}>
      <XCircle className="h-5 w-5 shrink-0" />
      <p className="text-sm">{error}</p>
    </div>
  );

  if (!reporte) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">Validación de partida doble</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">Verifica que todos los comprobantes cuadren antes de generar el archivo.</p>
      </div>

      {/* Tabla */}
      <div data-tutorial="validar-reporte" className="rounded-xl border border-[var(--border-soft)] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border-soft)] bg-[var(--bg-elevated)]">
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Comprobante</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Débitos</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Créditos</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Diferencia</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-soft)]">
            {reporte.comprobantes.map((c) => (
              <tr key={c.consecutivo} className="hover:bg-[var(--bg-elevated)] transition-colors">
                <td className="px-4 py-3 text-[var(--text-secondary)] font-mono text-xs">{c.numero_dian || `#${c.consecutivo}`}</td>
                <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono">{fmt(c.total_debito)}</td>
                <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono">{fmt(c.total_credito)}</td>
              <td className={cn("px-4 py-3 text-right font-mono", c.cuadra ? "text-[var(--success-text)]" : "text-[var(--error-text)]")}>
                  {fmt(Math.abs(c.diferencia))}
                </td>
                <td className="px-4 py-3 text-center">
                  {c.cuadra
                    ? <CheckCircle2 className="h-4 w-4 mx-auto" style={{ color: "var(--success-text)" }} />
                    : <XCircle className="h-4 w-4 mx-auto" style={{ color: "var(--error-text)" }} />}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-[var(--border-strong)] bg-[var(--bg-elevated)]">
              <td className="px-4 py-3 text-xs font-semibold text-[var(--text-muted)] uppercase">Total</td>
              <td className="px-4 py-3 text-right font-semibold text-[var(--text-primary)] font-mono">{fmt(reporte.gran_total_debitos)}</td>
              <td className="px-4 py-3 text-right font-semibold text-[var(--text-primary)] font-mono">{fmt(reporte.gran_total_creditos)}</td>
              <td className={cn("px-4 py-3 text-right font-semibold font-mono",
                reporte.global_cuadra ? "text-[var(--success-text)]" : "text-[var(--error-text)]")}>
                {fmt(Math.abs(reporte.gran_total_debitos - reporte.gran_total_creditos))}
              </td>
              <td className="px-4 py-3 text-center">
                {reporte.global_cuadra
                  ? <CheckCircle2 className="h-5 w-5 mx-auto" style={{ color: "var(--success-text)" }} />
                  : <XCircle className="h-5 w-5 mx-auto" style={{ color: "var(--error-text)" }} />}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Status */}
      {reporte.global_cuadra ? (
        <div className="flex items-center gap-3 rounded-xl border p-4" style={{ borderColor: "var(--success-border)", backgroundColor: "var(--success-bg)", color: "var(--success-text)" }}>
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <p className="text-sm font-medium">Todos los comprobantes cuadran. Puedes generar el archivo.</p>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-xl border p-4" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)", color: "var(--error-text)" }}>
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <p className="text-sm">Hay comprobantes que no cuadran. Revisa el mapeo de cuentas.</p>
        </div>
      )}

      <div className="flex items-center justify-between pt-2">
        <Button variant="outline" onClick={() => setPaso(2)}>← Volver al mapeo</Button>
        <Button data-tutorial="generar-btn" size="lg" onClick={handleGenerar} disabled={!reporte.global_cuadra || generando} variant={reporte.global_cuadra ? "default" : "secondary"}>
          {generando ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generando…</> : "Generar archivo SIIGO →"}
        </Button>
      </div>
    </div>
  );
}
