"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { fmt } from "@/lib/utils";
import { Download, CheckCircle2, PartyPopper, AlertTriangle, Plus, ArrowLeft, WifiOff } from "lucide-react";

function _parseApiError(raw: string): string {
  if (!raw || raw === "Failed to fetch") return "__network__";
  const body = raw.replace(/^API \d+:\s*/, "");
  try {
    const parsed = JSON.parse(body);
    if (parsed?.detail) return String(parsed.detail);
  } catch {}
  return body || raw;
}

export function Paso4() {
  const { facturas, mapeos, tipoComp, centroCosto, reporte, xlsxBlob, reset, setPaso, tutorialActivo } = useWizardStore();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);

  const handleDownload = () => {
    if (tutorialActivo) return;
    if (!xlsxBlob) return;
    const url = URL.createObjectURL(xlsxBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `importacion_SIIGO_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
    setDownloaded(true);
  };

  const handleConfirmar = async () => {
    if (tutorialActivo) { setConfirmed(true); return; }
    setConfirming(true);
    setConfirmError(null);
    try {
      const items = facturas.map((f, idx) => ({
        factura: f,
        mapeos_confirmados: mapeos.filter((m) => m.idx_factura === idx),
      }));
      await api.batchGenerar({ items, tipo_comprobante: tipoComp, centro_costo: centroCosto, confirmar: true });
      setConfirmed(true);
      // La causación quedó completa: descartar el borrador temporal si existía.
      api.descartarBorrador()
        .then(() => queryClient.invalidateQueries({ queryKey: ["borrador"] }))
        .catch(() => {});
    } catch (e) {
      setConfirmError(_parseApiError((e as Error).message));
    }
    setConfirming(false);
  };

  const primerConsec = reporte ? (reporte.comprobantes[0]?.consecutivo ?? "—") : "—";
  const ultimoConsec = reporte ? (reporte.comprobantes.at(-1)?.consecutivo ?? "—") : "—";

  return (
    <div className="space-y-6">
      {/* Header con botón volver */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">Descargar e importar a SIIGO</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">El archivo está listo. Descárgalo e impórtalo en SIIGO.</p>
        </div>
        {!confirmed && (
          <Button variant="outline" onClick={() => setPaso(3)} className="gap-1.5 shrink-0">
            <ArrowLeft className="h-3.5 w-3.5" /> Volver a validación
          </Button>
        )}
      </div>

      {confirmed ? (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 py-12 text-center">
          <PartyPopper className="h-12 w-12 text-emerald-400" />
          <p className="text-lg font-semibold text-[var(--text-primary)]">¡Importación confirmada!</p>
          <p className="text-sm text-[var(--text-secondary)]">El aprendizaje fue guardado. Próximo consecutivo: <strong className="text-[var(--text-primary)]">{Number(ultimoConsec) + 1}</strong></p>
          <Button variant="outline" onClick={reset} className="gap-2">
            <Plus className="h-4 w-4" /> Procesar nuevas facturas
          </Button>
        </div>
      ) : (
        <>
          {/* Resumen */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { label: "Facturas", value: facturas.length },
              { label: "Primer consecutivo", value: primerConsec },
              { label: "Último consecutivo", value: ultimoConsec },
              { label: "Total débitos", value: fmt(reporte?.gran_total_debitos ?? 0) },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-xl border border-[var(--border-soft)] bg-[var(--bg-surface)] p-4">
                <p className="text-xs text-[var(--text-muted)]">{label}</p>
                <p className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{value}</p>
              </div>
            ))}
          </div>

          {/* Recomendación de orden */}
          {!downloaded && (
            <div className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs" style={{ backgroundColor: "var(--info-bg)", border: "1px solid var(--info-border)", color: "var(--info-text)" }}>
              <span className="font-semibold">Recomendación:</span> descarga el archivo primero e impórtalo en SIIGO, luego confirma el aprendizaje.
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3">
            <Button data-tutorial="descargar-btn" size="lg" onClick={handleDownload} disabled={!xlsxBlob && !tutorialActivo} className="gap-2">
              <Download className="h-4 w-4" />
              {downloaded ? "Descargar de nuevo" : "Descargar importacion_SIIGO.xlsx"}
            </Button>
            <Button data-tutorial="guardar-aprendizaje-btn" size="lg" variant="success" onClick={handleConfirmar} disabled={confirming} className="gap-2">
              <CheckCircle2 className="h-4 w-4" />
              {confirming ? "Guardando..." : "Confirmar y guardar aprendizaje"}
            </Button>
          </div>

          {/* Error inline al confirmar */}
          {confirmError && (() => {
            const esRed = confirmError === "__network__";
            return (
              <div className="flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--error-border, #f87171)", backgroundColor: "var(--error-bg, rgba(239,68,68,0.07))" }}>
                {esRed ? <WifiOff className="h-5 w-5 shrink-0 mt-0.5 text-red-400" /> : <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5 text-red-400" />}
                <div className="flex-1 space-y-2">
                  <p className="text-sm font-semibold text-red-400">No se pudo guardar el aprendizaje</p>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    {esRed
                      ? "Error de conexión con el servidor. Verifica tu conexión a internet y vuelve a intentarlo."
                      : confirmError}
                  </p>
                  {!esRed && downloaded && (
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                      El archivo XLSX ya fue descargado. Puedes volver a intentar guardar el aprendizaje.
                    </p>
                  )}
                  <div className="flex gap-2 flex-wrap mt-1">
                    <Button size="sm" variant="outline" onClick={handleConfirmar} disabled={confirming} className="gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5" /> {confirming ? "Reintentando..." : "Reintentar"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={reset} className="gap-1.5">
                      <Plus className="h-3.5 w-3.5" /> Procesar nuevas facturas
                    </Button>
                  </div>
                </div>
              </div>
            );
          })()}

          <p className="text-xs text-[var(--text-muted)]">
            "Confirmar" guarda el historial de decisiones para mejorar las sugerencias automáticas en futuras causaciones.
          </p>

          {/* Acceso rápido para reiniciar sin confirmar */}
          <div style={{ borderTop: "1px solid var(--border-soft)", paddingTop: "1rem" }}>
            <Button variant="outline" onClick={reset} className="gap-2">
              <Plus className="h-4 w-4" /> Procesar nuevas facturas sin confirmar aprendizaje
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
