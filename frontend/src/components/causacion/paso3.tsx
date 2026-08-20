"use client";
import { Fragment, useEffect, useMemo, useState } from "react";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { fmt } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, AlertTriangle, Loader2, Scissors, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BatchValidacionResponse } from "@/lib/types";

// SIIGO acepta máx. 500 líneas por archivo, incluyendo el encabezado → 499 de
// datos. Debe coincidir con core/exporter.MAX_FILAS_ARCHIVO en el backend.
const MAX_FILAS = 499;

// Convierte el error crudo del backend ({"detail":"…"}) en un texto legible.
function mensajeError(raw: string): string {
  if (!raw || raw === "Failed to fetch") return "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";
  const body = raw.replace(/^API \d+:\s*/, "");
  try {
    const p = JSON.parse(body);
    if (p?.detail) return String(p.detail);
  } catch { /* no era JSON */ }
  return body || raw;
}

const TUTORIAL_REPORTE: BatchValidacionResponse = {
  comprobantes: [
    { consecutivo: 1, numero_dian: "FERM44825", total_debito: 2750000, total_credito: 2750000, diferencia: 0, cuadra: true, filas: 3 },
    { consecutivo: 2, numero_dian: "SE-241001",  total_debito: 1190000, total_credito: 1190000, diferencia: 0, cuadra: true, filas: 3 },
    { consecutivo: 3, numero_dian: "FE-2026001", total_debito: 580000,  total_credito: 580000,  diferencia: 0, cuadra: true, filas: 3 },
  ],
  global_cuadra: true,
  gran_total_debitos: 4520000,
  gran_total_creditos: 4520000,
};

export function Paso3() {
  const { facturasParaCausar, mapeos, tipoComp, centroCosto, setPaso, setReporte, setXlsxBlob, setFacturasParaCausar, setMapeos } = useWizardStore();
  const [reporte, setLocalReporte] = useState<BatchValidacionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generando, setGenerando] = useState(false);
  const [corte, setCorte] = useState(0);

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
        setError(mensajeError((e as Error).message));
      }
      setLoading(false);
    };
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Acumulado de filas y máximo de facturas que caben en un archivo (≤ MAX_FILAS)
  const cut = useMemo(() => {
    const comps = reporte?.comprobantes ?? [];
    const acum: number[] = [];
    let s = 0;
    for (const c of comps) { s += c.filas || 0; acum.push(s); }
    let maxCabe = 0;
    for (let i = 0; i < comps.length; i++) {
      if (acum[i] <= MAX_FILAS) maxCabe = i + 1; else break;
    }
    return { acum, total: s, maxCabe, count: comps.length };
  }, [reporte]);

  // Corte por defecto = máximo que cabe, cuando llega el reporte
  useEffect(() => {
    if (reporte) setCorte(cut.maxCabe);
  }, [reporte, cut.maxCabe]);

  const necesitaTandas = cut.total > MAX_FILAS;
  const facturaMuyGrande = cut.count > 0 && cut.maxCabe === 0; // una sola factura > MAX_FILAS
  const tandaCuadra = reporte ? reporte.comprobantes.slice(0, corte).every((c) => c.cuadra) : false;
  const filasEnTanda = corte > 0 ? (cut.acum[corte - 1] ?? 0) : 0;
  const restantes = cut.count - corte;

  const handleGenerar = async () => {
    if (corte < 1) return;
    setGenerando(true);
    setError("");
    try {
      const tandaFacturas = facturasParaCausar.slice(0, corte);
      const tandaMapeos = mapeos.filter((m) => m.idx_factura < corte);

      if (useWizardStore.getState().tutorialActivo) {
        setFacturasParaCausar(tandaFacturas);
        setMapeos(tandaMapeos);
        setPaso(4);
        return;
      }

      const items = tandaFacturas.map((f, idx) => ({
        factura: f,
        mapeos_confirmados: tandaMapeos.filter((m) => m.idx_factura === idx),
      }));
      const blob = await api.batchGenerar({ items, tipo_comprobante: tipoComp, centro_costo: centroCosto, confirmar: false });

      // Fijar la tanda como el set exacto a confirmar en paso4 + reporte recortado
      setFacturasParaCausar(tandaFacturas);
      setMapeos(tandaMapeos);
      if (reporte) {
        const compsTanda = reporte.comprobantes.slice(0, corte);
        setReporte({
          comprobantes: compsTanda,
          global_cuadra: compsTanda.every((c) => c.cuadra),
          gran_total_debitos: compsTanda.reduce((s, c) => s + c.total_debito, 0),
          gran_total_creditos: compsTanda.reduce((s, c) => s + c.total_credito, 0),
        });
      }
      setXlsxBlob(blob);
      setPaso(4);
    } catch (e) {
      setError(mensajeError((e as Error).message));
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

  // Falló la validación inicial: mostrar error PERO con salida (no dejar atascado).
  if (!reporte) return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 rounded-xl border p-5" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)", color: "var(--error-text)" }}>
        <XCircle className="h-5 w-5 shrink-0 mt-0.5" />
        <p className="text-sm">{error || "No se pudo validar la partida doble."}</p>
      </div>
      <Button variant="outline" onClick={() => setPaso(2)}>← Volver al mapeo</Button>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">Validación de partida doble</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">Verifica que todos los comprobantes cuadren antes de generar el archivo.</p>
      </div>

      {/* Factura demasiado grande: bloqueo */}
      {facturaMuyGrande && (
        <div className="flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)", color: "var(--error-text)" }}>
          <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-semibold">Una factura supera el límite del archivo</p>
            <p className="mt-1">
              La factura <span className="font-mono">{reporte.comprobantes[0].numero_dian || `#${reporte.comprobantes[0].consecutivo}`}</span> genera <strong>{reporte.comprobantes[0].filas} filas</strong>, más del máximo de <strong>{MAX_FILAS}</strong> por archivo SIIGO. No es posible importarla en un solo archivo; revisa sus ítems o divídela manualmente.
            </p>
          </div>
        </div>
      )}

      {/* Aviso de tandas + control de corte */}
      {necesitaTandas && !facturaMuyGrande && (
        <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: "var(--brand)", backgroundColor: "var(--brand-muted)" }}>
          <div className="flex items-start gap-3">
            <Layers className="h-5 w-5 shrink-0 mt-0.5" style={{ color: "var(--brand)" }} />
            <div className="text-sm" style={{ color: "var(--text-primary)" }}>
              <p className="font-semibold">Estas {cut.count} facturas generan {cut.total} filas · el límite es {MAX_FILAS} por archivo.</p>
              <p className="mt-1" style={{ color: "var(--text-secondary)" }}>
                Este archivo llevará las primeras <strong>{corte}</strong> factura{corte !== 1 ? "s" : ""} (<strong>{filasEnTanda}</strong> filas); quedan <strong>{restantes}</strong> para la siguiente tanda. Podrás continuar con ellas después de importar esta.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <label className="flex items-center gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              <Scissors className="h-3.5 w-3.5" style={{ color: "var(--brand)" }} />
              Facturas en esta tanda:
              <input
                type="number"
                min={1}
                max={cut.maxCabe}
                value={corte}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (Number.isNaN(v)) return;
                  setCorte(Math.max(1, Math.min(cut.maxCabe, v)));
                }}
                className="w-20 rounded-lg border px-2 py-1 text-right text-sm font-mono tabular-nums outline-none focus:ring-2 focus:ring-[var(--brand)]"
                style={{ borderColor: "var(--border-strong)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)" }}
              />
              <span style={{ color: "var(--text-muted)" }}>de {cut.count} · máx. {cut.maxCabe} caben ({MAX_FILAS} filas)</span>
            </label>
            {corte !== cut.maxCabe && (
              <button
                onClick={() => setCorte(cut.maxCabe)}
                className="rounded-lg border px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80"
                style={{ borderColor: "var(--brand)", color: "var(--brand)", backgroundColor: "var(--bg-surface)" }}
              >
                Usar el máximo ({cut.maxCabe})
              </button>
            )}
          </div>
        </div>
      )}

      {/* Tabla */}
      <div data-tutorial="validar-reporte" className="rounded-xl border border-[var(--border-soft)] overflow-hidden overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-[var(--border-soft)] bg-[var(--bg-elevated)]">
              <th className="px-4 py-3 text-left text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Comprobante</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Débitos</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Créditos</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Diferencia</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Filas</th>
              {necesitaTandas && <th className="px-4 py-3 text-right text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Acum.</th>}
              <th className="px-4 py-3 text-center text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-soft)]">
            {reporte.comprobantes.map((c, idx) => {
              const diferida = necesitaTandas && idx >= corte;
              const esCorte = necesitaTandas && idx === corte - 1;
              return (
                <Fragment key={c.consecutivo}>
                  <tr
                    className="transition-colors"
                    style={{ opacity: diferida ? 0.45 : 1, backgroundColor: diferida ? "var(--bg-elevated)" : undefined }}
                  >
                    <td className="px-4 py-3 text-[var(--text-secondary)] font-mono text-xs">{c.numero_dian || `#${c.consecutivo}`}</td>
                    <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono">{fmt(c.total_debito)}</td>
                    <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono">{fmt(c.total_credito)}</td>
                    <td className={cn("px-4 py-3 text-right font-mono", c.cuadra ? "text-[var(--success-text)]" : "text-[var(--error-text)]")}>
                      {fmt(Math.abs(c.diferencia))}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-[var(--text-secondary)]">{c.filas}</td>
                    {necesitaTandas && (
                      <td className="px-4 py-3 text-right font-mono tabular-nums" style={{ color: (cut.acum[idx] ?? 0) > MAX_FILAS ? "var(--error-text)" : "var(--text-muted)" }}>
                        {cut.acum[idx] ?? 0}
                      </td>
                    )}
                    <td className="px-4 py-3 text-center">
                      {diferida
                        ? <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Siguiente tanda</span>
                        : c.cuadra
                          ? <CheckCircle2 className="h-4 w-4 mx-auto" style={{ color: "var(--success-text)" }} />
                          : <XCircle className="h-4 w-4 mx-auto" style={{ color: "var(--error-text)" }} />}
                    </td>
                  </tr>
                  {esCorte && restantes > 0 && (
                    <tr>
                      <td colSpan={necesitaTandas ? 7 : 6} className="px-4 py-1.5">
                        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--brand)" }}>
                          <Scissors className="h-3 w-3" />
                          Corte del archivo · {filasEnTanda} filas
                          <span className="flex-1 border-t border-dashed" style={{ borderColor: "var(--brand)" }} />
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Status de la tanda */}
      {tandaCuadra ? (
        <div className="flex items-center gap-3 rounded-xl border p-4" style={{ borderColor: "var(--success-border)", backgroundColor: "var(--success-bg)", color: "var(--success-text)" }}>
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <p className="text-sm font-medium">
            {necesitaTandas
              ? `Los ${corte} comprobantes de esta tanda cuadran. Puedes generar el archivo.`
              : "Todos los comprobantes cuadran. Puedes generar el archivo."}
          </p>
        </div>
      ) : !facturaMuyGrande && (
        <div className="flex items-center gap-3 rounded-xl border p-4" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)", color: "var(--error-text)" }}>
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <p className="text-sm">Hay comprobantes que no cuadran. Revisa el mapeo de cuentas.</p>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)", color: "var(--error-text)" }}>
          <XCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      <div className="flex items-center justify-between pt-2">
        <Button variant="outline" onClick={() => setPaso(2)}>← Volver al mapeo</Button>
        <Button
          data-tutorial="generar-btn"
          size="lg"
          onClick={handleGenerar}
          disabled={!tandaCuadra || generando || corte < 1 || facturaMuyGrande}
          variant={tandaCuadra ? "default" : "secondary"}
        >
          {generando
            ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generando…</>
            : necesitaTandas
              ? `Generar tanda (${corte} de ${cut.count}) →`
              : "Generar archivo SIIGO →"}
        </Button>
      </div>
    </div>
  );
}
