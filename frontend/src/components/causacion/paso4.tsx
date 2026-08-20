"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { fmt } from "@/lib/utils";
import { Download, CheckCircle2, PartyPopper, AlertTriangle, Plus, ArrowLeft, WifiOff, Layers } from "lucide-react";

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
  const { facturas, facturasParaCausar, facturasYaCausadas, mapeos, tipoComp, centroCosto, reporte, xlsxBlob, reset, setPaso, tutorialActivo, setFacturasYaCausadas } = useWizardStore();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);
  // Facturas que quedan por causar tras confirmar esta tanda (0 = todas listas)
  const [restantes, setRestantes] = useState<number | null>(null);

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
    if (tutorialActivo) { setConfirmed(true); setRestantes(0); return; }
    setConfirming(true);
    setConfirmError(null);
    try {
      // Confirmar SOLO la tanda actual (facturasParaCausar, alineado con mapeos).
      const items = facturasParaCausar.map((f, idx) => ({
        factura: f,
        mapeos_confirmados: mapeos.filter((m) => m.idx_factura === idx),
      }));
      await api.batchGenerar({ items, tipo_comprobante: tipoComp, centro_costo: centroCosto, confirmar: true });

      // Refrescar causadas de toda la carga: alimenta el modal y el filtro de paso2.
      const prev = useWizardStore.getState().facturasYaCausadas;
      let causadasInfo = prev;
      try {
        const numeros = facturas.map((f) => f.numero_dian).filter(Boolean);
        const { ya_causadas } = await api.verificarCausadas(numeros);
        causadasInfo = ya_causadas; // fuente de verdad completa (con consecutivo, detalle…)
      } catch {
        // Fallback si falla la verificación: marcar al menos la tanda recién causada
        // con info mínima, para que no reaparezca en paso2 ni desaparezca del modal.
        const existentes = new Set(prev.map((c) => c.numero_dian));
        const nuevas = facturasParaCausar
          .filter((f) => !existentes.has(f.numero_dian))
          .map((f) => ({
            numero_dian: f.numero_dian,
            nit_proveedor: f.nit ?? null,
            razon_social: f.razon_social ?? null,
            fecha_factura: f.fecha ?? null,
            total: f.total ?? null,
            consecutivo: null,
            tipo_comprobante: null,
            fecha_causacion: null,
            datos_json: null,
          }));
        causadasInfo = [...prev, ...nuevas];
      }
      setFacturasYaCausadas(causadasInfo);
      const causadas = new Set(causadasInfo.map((c) => c.numero_dian));

      const quedan = facturas.filter((f) => !causadas.has(f.numero_dian)).length;
      setRestantes(quedan);
      setConfirmed(true);

      // Solo descartar el borrador cuando ya no queda nada pendiente.
      if (quedan === 0) {
        api.descartarBorrador()
          .then(() => queryClient.invalidateQueries({ queryKey: ["borrador"] }))
          .catch(() => {});
      }
    } catch (e) {
      setConfirmError(_parseApiError((e as Error).message));
    }
    setConfirming(false);
  };

  const primerConsec = reporte ? (reporte.comprobantes[0]?.consecutivo ?? "—") : "—";
  const ultimoConsec = reporte ? (reporte.comprobantes.at(-1)?.consecutivo ?? "—") : "—";

  // Vista previa de cuántas facturas quedan por causar tras esta tanda (antes de confirmar).
  const tandaNums = new Set(facturasParaCausar.map((f) => f.numero_dian));
  const causadasNums = new Set(facturasYaCausadas.map((c) => c.numero_dian));
  const quedanPreview = facturas.filter((f) => !tandaNums.has(f.numero_dian) && !causadasNums.has(f.numero_dian)).length;
  const esTandaParcial = quedanPreview > 0;

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
        restantes && restantes > 0 ? (
          /* Tanda importada, aún quedan facturas por causar */
          <div className="flex flex-col items-center gap-4 rounded-xl border py-12 text-center" style={{ borderColor: "var(--brand)", backgroundColor: "var(--brand-muted)" }}>
            <CheckCircle2 className="h-12 w-12" style={{ color: "var(--brand)" }} />
            <p className="text-lg font-semibold text-[var(--text-primary)]">Tanda importada ✓</p>
            <p className="text-sm text-[var(--text-secondary)] max-w-md">
              Estas facturas quedaron causadas (las verás en <strong>“Ya causadas”</strong>). Quedan <strong className="text-[var(--text-primary)]">{restantes}</strong> factura{restantes !== 1 ? "s" : ""} por causar — vuelve a configurarlas y verifícalas para continuar con la siguiente tanda.
            </p>
            <Button onClick={() => setPaso(2)} className="gap-2">
              <ArrowLeft className="h-4 w-4" /> Volver a configurar las {restantes} factura{restantes !== 1 ? "s" : ""} restantes
            </Button>
          </div>
        ) : (
          /* Todo causado */
          <div className="flex flex-col items-center gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 py-12 text-center">
            <PartyPopper className="h-12 w-12 text-emerald-400" />
            <p className="text-lg font-semibold text-[var(--text-primary)]">¡Importación confirmada!</p>
            <p className="text-sm text-[var(--text-secondary)]">El aprendizaje fue guardado. Próximo consecutivo: <strong className="text-[var(--text-primary)]">{Number(ultimoConsec) + 1}</strong></p>
            <Button variant="outline" onClick={reset} className="gap-2">
              <Plus className="h-4 w-4" /> Procesar nuevas facturas
            </Button>
          </div>
        )
      ) : (
        <>
          {/* Resumen — refleja SOLO esta tanda (lo que lleva el archivo generado) */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { label: esTandaParcial ? "Facturas (esta tanda)" : "Facturas", value: facturasParaCausar.length },
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

          {/* Tanda parcial: explicar cómo continuar con las restantes */}
          {esTandaParcial && (
            <div className="flex items-start gap-2.5 rounded-lg px-3 py-2.5 text-sm" style={{ backgroundColor: "var(--brand-muted)", border: "1px solid var(--brand)", color: "var(--text-primary)" }}>
              <Layers className="h-4 w-4 shrink-0 mt-0.5" style={{ color: "var(--brand)" }} />
              <span>
                Este archivo es una <strong>tanda de {facturasParaCausar.length} facturas</strong> (quedan <strong>{quedanPreview}</strong> por causar). Descárgalo e impórtalo en SIIGO; al pulsar <strong>“Confirmar y guardar aprendizaje”</strong> se marcarán como causadas y podrás <strong>volver al paso 2</strong> a configurar y causar las restantes.
              </span>
            </div>
          )}

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
