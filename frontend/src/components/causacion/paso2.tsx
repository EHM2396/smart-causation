"use client";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Badge } from "@/components/ui/badge";
import { NuevoImpuestoDialog } from "@/components/causacion/nuevo-impuesto-dialog";
import { fmt } from "@/lib/utils";
import { AlertTriangle, Plus, ChevronDown, ChevronUp, Sparkles, Loader2 } from "lucide-react";
import type { MapeoItem, CuentaOpcion, ImpuestoOut, FuenteMapeo } from "@/lib/types";

// Helper: build combobox options from cuenta list
function cuentaOpts(cuentas: CuentaOpcion[]) {
  return cuentas.map((c) => ({ value: c.codigo, label: c.label ?? `${c.codigo} – ${c.nombre}` }));
}

function impOpts(imps: ImpuestoOut[], tipos?: string[]) {
  return imps
    .filter((i) => !tipos || tipos.some((t) => (i.tipo_impuesto ?? "").toLowerCase().includes(t)))
    .map((i) => ({
      value: i.codigo,
      label: `${i.codigo} — ${i.tipo_impuesto ?? ""} ${i.tarifa ?? 0}%`,
    }));
}

const ORIGEN_BADGE: Record<string, { label: string; variant: "success" | "info" | "purple" | "warning" | "default" }> = {
  aprendizaje: { label: "Aprendido", variant: "success" },
  regla:       { label: "Regla",     variant: "info" },
  ia:          { label: "IA",        variant: "purple" },
  manual:      { label: "Manual",    variant: "default" },
};

type Sugerencia = { cuenta: string | null; origen: string | null };

function origenToFuente(origen: string | null): FuenteMapeo {
  if (origen === "aprendizaje") return "aprendido";
  if (origen === "regla") return "regla";
  if (origen === "ia") return "ia_alta";
  return "manual";
}

export function Paso2() {
  const { facturas, tipoComp, setPaso, setMapeos } = useWizardStore();

  const { data: cuentasGasto = [] } = useQuery({ queryKey: ["cuentas-gasto"], queryFn: api.getCuentasGasto });
  const { data: cuentasPago = [] } = useQuery({ queryKey: ["cuentas-pago"], queryFn: api.getCuentasPago });
  const { data: impuestosRaw = [], refetch: refetchImps } = useQuery({ queryKey: ["impuestos"], queryFn: api.getImpuestos });

  const [expanded, setExpanded] = useState<Record<number, boolean>>({ 0: true });
  const [cuentaPago, setCuentaPago] = useState<Record<number, string>>({});
  const [tipoProveedor, setTipoProveedor] = useState<Record<number, string>>({});
  const [nitEdit, setNitEdit] = useState<Record<number, string>>({});
  const [cuentaGastoGlobal, setCuentaGastoGlobal] = useState<Record<number, string>>({});
  const [rfGlobal, setRfGlobal] = useState<Record<number, string>>({});
  const [riGlobal, setRiGlobal] = useState<Record<number, string>>({});
  const [cuentaGastoItem, setCuentaGastoItem] = useState<Record<string, string>>({});
  const [rfItem, setRfItem] = useState<Record<string, string>>({});
  const [riItem, setRiItem] = useState<Record<string, string>>({});
  const [dlgOpen, setDlgOpen] = useState<"retefuente" | "reteica" | null>(null);

  // ── Sugerencias del sistema de aprendizaje ────────────────────────────────
  const [suggestions, setSuggestions] = useState<Record<string, Sugerencia>>({});
  const [sugsLoading, setSugsLoading] = useState(false);

  useEffect(() => {
    if (facturas.length === 0) return;
    setSugsLoading(true);

    const items = facturas.flatMap((f, idx) =>
      f.items.map((item, jdx) => ({ key: `${idx}_${jdx}`, nit: f.nit, descripcion: item.descripcion }))
    );

    Promise.all(
      items.map(({ key, nit, descripcion }) =>
        api.sugerirCuenta(nit, descripcion)
          .then(r => ({ key, cuenta: r.cuenta_sugerida, origen: r.origen }))
          .catch(() => ({ key, cuenta: null, origen: null }))
      )
    ).then(results => {
      const map: Record<string, Sugerencia> = {};
      results.forEach(({ key, cuenta, origen }) => { map[key] = { cuenta, origen }; });
      setSuggestions(map);

      // Pre-llenar solo si el usuario no eligió nada aún
      setCuentaGastoItem(prev => {
        const next = { ...prev };
        results.forEach(({ key, cuenta }) => {
          if (!next[key] && cuenta) next[key] = cuenta;
        });
        return next;
      });

      setSugsLoading(false);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facturas]);

  const gastoOpts = cuentaOpts(cuentasGasto);
  const pagoOpts = cuentaOpts(cuentasPago);
  const rfOpts = impOpts(impuestosRaw, ["retefuente"]);
  const riOpts = impOpts(impuestosRaw, ["reteica"]);
  const allImpOpts = impOpts(impuestosRaw);

  const getImpInfo = (cod: string) => impuestosRaw.find((i) => i.codigo === cod);

  const handleValidar = () => {
    const mapeos: MapeoItem[] = [];

    for (let idx = 0; idx < facturas.length; idx++) {
      const factura = facturas[idx];
      const cgGlobal = cuentaGastoGlobal[idx] ?? "";
      const globalRetActiva = !!(rfGlobal[idx] || riGlobal[idx]);
      const pago = cuentaPago[idx] ?? "";
      const pagoNombre = cuentasPago.find((c) => c.codigo === pago)?.nombre ?? "";

      for (let jdx = 0; jdx < factura.items.length; jdx++) {
        const item = factura.items[jdx];
        const key = `${idx}_${jdx}`;
        const cgFinal = cgGlobal || cuentaGastoItem[key] || "";
        const cod = item.cod_impuesto ?? "";
        const impInfo = cod ? getImpInfo(cod) : null;

        const sug = suggestions[key];
        const fuente: FuenteMapeo = sug?.cuenta && cgFinal === sug.cuenta
          ? origenToFuente(sug.origen)
          : "manual";

        mapeos.push({
          idx_factura: idx,
          descripcion: item.descripcion,
          base: item.base,
          cod_impuesto: impInfo?.codigo ?? cod,
          porcentaje: impInfo?.tarifa ?? item.porcentaje ?? 0,
          valor_impuesto: item.valor_impuesto,
          cuenta_gasto: cgFinal,
          fuente,
          cuenta_impuesto_deb: impInfo?.cta_compras ?? "",
          cuenta_impuesto_cre: "",
          es_retencion: false,
          cuenta_pago: pago,
          cuenta_pago_nombre: pagoNombre,
        });

        // Retención por item
        if (!globalRetActiva) {
          if (rfItem[key]) {
            const rf = getImpInfo(rfItem[key]);
            if (rf) mapeos.push({
              idx_factura: idx, descripcion: `Retefuente ${rf.tarifa}%`,
              base: item.base, cod_impuesto: rf.codigo, porcentaje: rf.tarifa ?? 0,
              valor_impuesto: Math.round((item.base * (rf.tarifa ?? 0)) / 100),
              cuenta_gasto: "", fuente: "manual",
              cuenta_impuesto_deb: "", cuenta_impuesto_cre: rf.cta_compras ?? "",
              es_retencion: true, cuenta_pago: pago, cuenta_pago_nombre: pagoNombre,
            });
          }
          if (riItem[key]) {
            const ri = getImpInfo(riItem[key]);
            if (ri) mapeos.push({
              idx_factura: idx, descripcion: `ReteICA ${ri.tarifa}%`,
              base: item.base, cod_impuesto: ri.codigo, porcentaje: ri.tarifa ?? 0,
              valor_impuesto: Math.round((item.base * (ri.tarifa ?? 0)) / 100),
              cuenta_gasto: "", fuente: "manual",
              cuenta_impuesto_deb: "", cuenta_impuesto_cre: ri.cta_compras ?? "",
              es_retencion: true, cuenta_pago: pago, cuenta_pago_nombre: pagoNombre,
            });
          }
        }
      }

      // Retención global
      const totalBase = factura.items.reduce((s, it) => s + it.base, 0);
      if (rfGlobal[idx]) {
        const rf = getImpInfo(rfGlobal[idx]);
        if (rf) mapeos.push({
          idx_factura: idx, descripcion: `Retefuente ${rf.tarifa}%`,
          base: totalBase, cod_impuesto: rf.codigo, porcentaje: rf.tarifa ?? 0,
          valor_impuesto: Math.round((totalBase * (rf.tarifa ?? 0)) / 100),
          cuenta_gasto: "", fuente: "manual",
          cuenta_impuesto_deb: "", cuenta_impuesto_cre: rf.cta_compras ?? "",
          es_retencion: true, cuenta_pago: cuentaPago[idx] ?? "", cuenta_pago_nombre: "",
        });
      }
      if (riGlobal[idx]) {
        const ri = getImpInfo(riGlobal[idx]);
        if (ri) mapeos.push({
          idx_factura: idx, descripcion: `ReteICA ${ri.tarifa}%`,
          base: totalBase, cod_impuesto: ri.codigo, porcentaje: ri.tarifa ?? 0,
          valor_impuesto: Math.round((totalBase * (ri.tarifa ?? 0)) / 100),
          cuenta_gasto: "", fuente: "manual",
          cuenta_impuesto_deb: "", cuenta_impuesto_cre: ri.cta_compras ?? "",
          es_retencion: true, cuenta_pago: cuentaPago[idx] ?? "", cuenta_pago_nombre: "",
        });
      }
    }

    setMapeos(mapeos);
    setPaso(3);
  };

  const toggle = (i: number) => setExpanded((p) => ({ ...p, [i]: !p[i] }));

  if (!tipoComp) {
    return (
      <div className="flex items-center gap-3 rounded-xl border p-5" style={{ borderColor: "var(--warning-border)", backgroundColor: "var(--warning-bg)", color: "var(--warning-text)" }}>
        <AlertTriangle className="h-5 w-5 shrink-0" />
        <p className="text-sm">Selecciona un <strong>Tipo de comprobante</strong> en la barra lateral antes de continuar.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">Mapear cuentas contables</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {facturas.length} factura{facturas.length > 1 ? "s" : ""} listas para mapear
            {sugsLoading && (
              <span className="ml-2 inline-flex items-center gap-1" style={{ color: "var(--brand)" }}>
                <Loader2 className="h-3 w-3 animate-spin" />
                Cargando sugerencias...
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setDlgOpen("retefuente")}>
            <Plus className="h-3.5 w-3.5" /> Retefuente
          </Button>
          <Button variant="outline" size="sm" onClick={() => setDlgOpen("reteica")}>
            <Plus className="h-3.5 w-3.5" /> ReteICA
          </Button>
        </div>
      </div>

      {facturas.map((factura, idx) => (
        <div key={idx} className="rounded-xl border border-[var(--border-soft)] bg-[var(--bg-surface)] overflow-hidden">
          {/* Header */}
          <button
            onClick={() => toggle(idx)}
            className="flex w-full items-center justify-between px-5 py-4 hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-semibold" style={{ backgroundColor: "var(--info-bg)", color: "var(--info-text)", border: "1px solid var(--info-border)" }}>
                {idx + 1}
              </div>
              <div className="min-w-0 text-left">
                <p className="text-sm font-medium text-[var(--text-primary)] truncate">{factura.numero_dian} · {factura.razon_social}</p>
                <p className="text-xs text-[var(--text-muted)]">NIT {factura.nit} · {factura.fecha} · {fmt(factura.total)}</p>
              </div>
            </div>
            {expanded[idx] ? <ChevronUp className="h-4 w-4 text-[var(--text-muted)] shrink-0" /> : <ChevronDown className="h-4 w-4 text-[var(--text-muted)] shrink-0" />}
          </button>

          {expanded[idx] && (
            <div className="border-t border-[var(--border-soft)] px-5 py-5 space-y-5">
              {/* NIT + tipo + cuenta pago */}
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--text-muted)]">NIT proveedor</label>
                  <input
                    value={nitEdit[idx] ?? factura.nit}
                    onChange={(e) => setNitEdit((p) => ({ ...p, [idx]: e.target.value }))}
                    className="flex h-9 w-full rounded-lg border border-[var(--border-strong)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--text-muted)]">Tipo proveedor</label>
                  <select
                    value={tipoProveedor[idx] ?? factura.tipo_proveedor ?? "juridica"}
                    onChange={(e) => setTipoProveedor((p) => ({ ...p, [idx]: e.target.value }))}
                    className="flex h-9 w-full rounded-lg border border-[var(--border-strong)] bg-[var(--bg-surface)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  >
                    <option value="juridica">Jurídica</option>
                    <option value="natural">Natural</option>
                  </select>
                </div>
                <div className="flex flex-col items-end justify-center">
                  <p className="text-xs text-[var(--text-muted)]">Total factura</p>
                  <p className="text-xl font-bold text-[var(--text-primary)]">{fmt(factura.total)}</p>
                </div>
              </div>

              <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--text-muted)]">Cuenta de pago</label>
                <Combobox options={pagoOpts} value={cuentaPago[idx]} onChange={(v) => setCuentaPago((p) => ({ ...p, [idx]: v }))} placeholder="Buscar por código o nombre..." />
              </div>

              {/* Global box */}
              <div className="rounded-lg border p-4 space-y-3" style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--info-text)" }}>Global — aplica a todos los ítems</p>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs text-[var(--text-muted)]">Cuenta gasto/costo</label>
                    <Combobox options={gastoOpts} value={cuentaGastoGlobal[idx]} onChange={(v) => setCuentaGastoGlobal((p) => ({ ...p, [idx]: v }))} placeholder="Aplica a todos..." />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-[var(--text-muted)]">Retefuente</label>
                    <Combobox options={rfOpts} value={rfGlobal[idx]} onChange={(v) => setRfGlobal((p) => ({ ...p, [idx]: v }))} placeholder="Código retefuente..." />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs text-[var(--text-muted)]">ReteICA</label>
                    <Combobox options={riOpts} value={riGlobal[idx]} onChange={(v) => setRiGlobal((p) => ({ ...p, [idx]: v }))} placeholder="Código reteica..." />
                  </div>
                </div>
              </div>

              {/* Items */}
              <div className="space-y-3">
                {factura.items.map((item, jdx) => {
                  const key = `${idx}_${jdx}`;
                  const impInfo = item.cod_impuesto ? getImpInfo(item.cod_impuesto) : null;
                  const retGlobalActiva = !!(rfGlobal[idx] || riGlobal[idx]);
                  const sug = suggestions[key];
                  const currentVal = cuentaGastoGlobal[idx] || cuentaGastoItem[key];
                  const origenEfectivo = sug?.cuenta && currentVal === sug.cuenta
                    ? (sug.origen ?? "aprendizaje")
                    : currentVal ? "manual" : null;
                  const badge = origenEfectivo ? ORIGEN_BADGE[origenEfectivo] ?? ORIGEN_BADGE.manual : null;
                  const sinSugerencia = !sugsLoading && sug && sug.cuenta === null && !currentVal && !cuentaGastoGlobal[idx];
                  return (
                    <div key={jdx} className="rounded-lg border border-[var(--border-soft)] bg-[var(--bg-elevated)] p-4 space-y-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-[var(--text-muted)]">Ítem {jdx + 1}</span>
                        <span className="text-sm text-[var(--text-secondary)]">{item.descripcion}</span>
                      </div>
                      <div className="grid grid-cols-4 gap-3">
                        <div className="col-span-2 space-y-1.5">
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-[var(--text-muted)]">Cuenta gasto/costo</label>
                            {sugsLoading && (
                              <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--text-muted)" }} />
                            )}
                            {badge && !sugsLoading && (
                              <Badge variant={badge.variant}>{badge.label}</Badge>
                            )}
                          </div>
                          <Combobox
                            options={gastoOpts}
                            value={currentVal}
                            onChange={(v) => setCuentaGastoItem((p) => ({ ...p, [key]: v }))}
                            disabled={!!cuentaGastoGlobal[idx]}
                            placeholder="Buscar cuenta..."
                          />
                          {sinSugerencia && (
                            <div className="flex items-start gap-1.5 mt-1 rounded-lg px-2.5 py-2" style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning-border)" }}>
                              <Sparkles className="h-3.5 w-3.5 shrink-0 mt-0.5" style={{ color: "var(--warning-text)" }} />
                              <p className="text-xs leading-snug" style={{ color: "var(--warning-text)" }}>
                                Sin mapeo previo para este ítem. Selecciona la cuenta manualmente — el sistema aprenderá para la próxima vez.
                              </p>
                            </div>
                          )}
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs text-[var(--text-muted)]">Base</label>
                          <div className="flex h-9 items-center rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] px-3 text-sm font-medium text-emerald-600">
                            {fmt(item.base)}
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-xs text-[var(--text-muted)]">
                            {impInfo ? "Cód. impuesto" : "Seleccionar impuesto"}
                          </label>
                          {impInfo ? (
                            <div className="flex h-9 items-center gap-2 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] px-3 text-sm">
                              <span className="text-[var(--text-secondary)]">{impInfo.codigo}</span>
                              <Badge variant="info">{impInfo.tipo_impuesto} {impInfo.tarifa}%</Badge>
                            </div>
                          ) : (
                            <Combobox options={allImpOpts} value={""} onChange={() => {}} placeholder="Buscar..." />
                          )}
                        </div>
                      </div>
                      {/* Retención por item */}
                      {retGlobalActiva ? (
                        <p className="text-xs" style={{ color: "var(--info-text)", opacity: 0.7 }}>↑ Retención global activa — selectores por ítem deshabilitados</p>
                      ) : (
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1.5">
                            <label className="text-xs text-[var(--text-muted)]">Retefuente (solo este ítem)</label>
                            <Combobox options={rfOpts} value={rfItem[key]} onChange={(v) => setRfItem((p) => ({ ...p, [key]: v }))} placeholder="Código retefuente..." />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-xs text-[var(--text-muted)]">ReteICA (solo este ítem)</label>
                            <Combobox options={riOpts} value={riItem[key]} onChange={(v) => setRiItem((p) => ({ ...p, [key]: v }))} placeholder="Código reteica..." />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ))}

      <div className="flex items-center justify-between pt-2">
        <Button variant="outline" onClick={() => setPaso(1)}>← Volver</Button>
        <Button size="lg" onClick={handleValidar}>Validar partida doble →</Button>
      </div>

      <NuevoImpuestoDialog
        open={!!dlgOpen}
        tipo={dlgOpen ?? "retefuente"}
        onClose={() => setDlgOpen(null)}
        onCreated={() => { refetchImps(); setDlgOpen(null); }}
        cuentasPago={cuentasPago}
        cuentasGasto={cuentasGasto}
      />
    </div>
  );
}
