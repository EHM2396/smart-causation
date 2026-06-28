"use client";
import { useState } from "react";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { fmt } from "@/lib/utils";
import { Download, CheckCircle2, PartyPopper } from "lucide-react";

export function Paso4() {
  const { facturas, mapeos, tipoComp, centroCosto, reporte, xlsxBlob, reset, tutorialActivo } = useWizardStore();
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const handleDownload = () => {
    if (tutorialActivo) return;
    if (!xlsxBlob) return;
    const url = URL.createObjectURL(xlsxBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `importacion_SIIGO_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleConfirmar = async () => {
    if (tutorialActivo) { setConfirmed(true); return; }
    setConfirming(true);
    try {
      const items = facturas.map((f, idx) => ({
        factura: f,
        mapeos_confirmados: mapeos.filter((m) => m.idx_factura === idx),
      }));
      await api.batchGenerar({ items, tipo_comprobante: tipoComp, centro_costo: centroCosto, confirmar: true });
      setConfirmed(true);
    } catch (e) {
      alert((e as Error).message);
    }
    setConfirming(false);
  };

  const primerConsec = reporte ? (reporte.comprobantes[0]?.consecutivo ?? "—") : "—";
  const ultimoConsec = reporte ? (reporte.comprobantes.at(-1)?.consecutivo ?? "—") : "—";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">Descargar e importar a SIIGO</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">El archivo está listo. Descárgalo e impórtalo en SIIGO.</p>
      </div>

      {confirmed ? (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 py-12 text-center">
          <PartyPopper className="h-12 w-12 text-emerald-400" />
          <p className="text-lg font-semibold text-[var(--text-primary)]">¡Importación confirmada!</p>
          <p className="text-sm text-[var(--text-secondary)]">El aprendizaje fue guardado. Próximo consecutivo: <strong className="text-[var(--text-primary)]">{Number(ultimoConsec) + 1}</strong></p>
          <Button variant="outline" onClick={reset}>Procesar nuevas facturas</Button>
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

          <div className="flex flex-col sm:flex-row gap-3">
            <Button data-tutorial="descargar-btn" size="lg" onClick={handleDownload} disabled={!xlsxBlob && !tutorialActivo} className="gap-2">
              <Download className="h-4 w-4" />
              Descargar importacion_SIIGO.xlsx
            </Button>
            <Button data-tutorial="guardar-aprendizaje-btn" size="lg" variant="success" onClick={handleConfirmar} disabled={confirming} className="gap-2">
              <CheckCircle2 className="h-4 w-4" />
              {confirming ? "Guardando..." : "Confirmar y guardar aprendizaje"}
            </Button>
          </div>

          <p className="text-xs text-[var(--text-muted)]">
            "Confirmar" guarda el historial de decisiones para mejorar las sugerencias automáticas en futuras causaciones.
          </p>
        </>
      )}
    </div>
  );
}
