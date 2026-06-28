"use client";
import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Badge } from "@/components/ui/badge";
import { NuevoImpuestoDialog } from "@/components/causacion/nuevo-impuesto-dialog";
import { fmt } from "@/lib/utils";
import {
  AlertTriangle, Plus, Sparkles, Loader2,
  ChevronLeft, ChevronRight, ArrowLeft, CheckCircle2, Clock, Search,
} from "lucide-react";
import type { MapeoItem, CuentaOpcion, ImpuestoOut, FuenteMapeo, Sugerencia } from "@/lib/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function cuentaOpts(cuentas: CuentaOpcion[]) {
  return cuentas.map((c) => ({ value: c.codigo, label: c.label ?? `${c.codigo} – ${c.nombre}` }));
}

function impOpts(imps: ImpuestoOut[], tipos?: string[]) {
  return imps
    .filter((i) => !tipos || tipos.some((t) => (i.tipo_impuesto ?? "").toLowerCase().includes(t)))
    .map((i) => ({ value: i.codigo, label: `${i.codigo} — ${i.tipo_impuesto ?? ""} ${i.tarifa ?? 0}%` }));
}

const ORIGEN_BADGE: Record<string, { label: string; variant: "success" | "info" | "purple" | "warning" | "default" }> = {
  aprendizaje: { label: "Aprendido",      variant: "success" },
  regla:       { label: "Regla",          variant: "info" },
  ia_alta:     { label: "IA · Alta",      variant: "purple" },
  ia_media:    { label: "IA · Media",     variant: "warning" },
  ia_baja:     { label: "IA · Baja",      variant: "default" },
  ia:          { label: "IA",             variant: "purple" },
  manual:      { label: "Manual",         variant: "default" },
};

function origenToFuente(origen: string | null): FuenteMapeo {
  if (origen === "aprendizaje") return "aprendido";
  if (origen === "regla") return "regla";
  if (origen === "ia") return "ia_alta";
  return "manual";
}

function DataField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{label}</p>
      <p
        className={`mt-1 truncate text-sm font-medium${mono ? " font-mono" : ""}`}
        style={{ color: "var(--text-primary)" }}
        title={value}
      >
        {value || "—"}
      </p>
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function Paso2() {
  const { facturas, tipoComp, setPaso, setMapeos, suggestions, setSuggestions } = useWizardStore();

  const { data: cuentasGasto = [] } = useQuery({ queryKey: ["cuentas-gasto"], queryFn: api.getCuentasGasto });
  const { data: cuentasPago = [] } = useQuery({ queryKey: ["cuentas-pago"], queryFn: api.getCuentasPago });
  const { data: impuestosRaw = [], refetch: refetchImps } = useQuery({ queryKey: ["impuestos"], queryFn: api.getImpuestos });

  // null = lista de facturas, number = detalle de factura idx
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

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

  const [sugsLoading, setSugsLoading] = useState(false);
  const [searchItems, setSearchItems] = useState("");
  const [verificadas, setVerificadas] = useState<Record<number, boolean>>({});
  const lastIdxRef = useRef<number | null>(null);

  // Una factura está completamente configurada cuando tiene cuenta de pago
  // Y todos sus ítems tienen cuenta de gasto (global o por ítem)
  const estaCompleta = (idx: number) => {
    if (!cuentaPago[idx]) return false;
    if (cuentaGastoGlobal[idx]) return true;
    return facturas[idx]?.items.every((_, jdx) => !!cuentaGastoItem[`${idx}_${jdx}`]) ?? false;
  };

  // Volver a lista y restaurar posición del scroll
  const goBackToList = () => {
    lastIdxRef.current = selectedIdx;
    setSelectedIdx(null);
  };

  // Hacer scroll al último ítem seleccionado al volver a la lista
  useEffect(() => {
    if (selectedIdx !== null || lastIdxRef.current === null) return;
    const row = document.getElementById(`invoice-row-${lastIdxRef.current}`);
    row?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedIdx]);

  useEffect(() => {
    if (facturas.length === 0) return;

    const allItems = facturas.flatMap((f, idx) =>
      f.items.map((item, jdx) => ({
        key: `${idx}_${jdx}`,
        nit: f.nit,
        descripcion: item.descripcion,
        tipo_proveedor: f.tipo_proveedor ?? "juridica",
      }))
    );

    // Aplica auto-fill solo sobre ítems del lote actual para evitar contaminación con claves de cargas anteriores
    const autoFill = (sugs: Record<string, Sugerencia>) => {
      setCuentaGastoItem(prev => {
        const next = { ...prev };
        allItems.forEach(({ key }) => {
          const sug = sugs[key];
          if (!sug) return;
          const esAutoconfiable = sug.origen === "regla" || sug.origen === "aprendizaje";
          if (!next[key] && sug.cuenta && esAutoconfiable) next[key] = sug.cuenta;
        });
        return next;
      });
      setCuentaPago(prev => {
        const next = { ...prev };
        facturas.forEach((factura, idx) => {
          if (next[idx]) return;
          for (let jdx = 0; jdx < factura.items.length; jdx++) {
            const sug = sugs[`${idx}_${jdx}`];
            if (sug?.cuenta_pago_sugerida && sug.cuenta_pago_origen === "aprendizaje") {
              next[idx] = sug.cuenta_pago_sugerida;
              break;
            }
          }
        });
        return next;
      });
    };

    const pendientes = allItems.filter(({ key }) => !(key in suggestions));

    if (pendientes.length === 0) {
      // Todo cacheado (re-montaje): reaplicar auto-fill desde el store para restaurar estado local
      autoFill(suggestions);
      return;
    }

    setSugsLoading(true);
    api.sugerirCuentasBatch(pendientes)
      .then(({ resultados }) => {
        const nuevas: Record<string, Sugerencia> = {};
        Object.entries(resultados).forEach(([key, r]) => {
          nuevas[key] = {
            cuenta: r.cuenta_sugerida,
            origen: r.origen,
            explicacion_ia: r.explicacion_ia,
            confianza_ia: r.confianza_ia,
            cuenta_pago_sugerida: r.cuenta_pago_sugerida,
            cuenta_pago_origen: r.cuenta_pago_origen,
          };
        });
        // Actualizar store y auto-fill en el mismo lote para evitar renders intermedios inconsistentes
        const todasSugs = { ...suggestions, ...nuevas };
        setSuggestions(todasSugs);
        autoFill(todasSugs); // usa el conjunto completo para que ítems cacheados también se restauren
        setSugsLoading(false);
      })
      .catch(() => {
        const fallback: Record<string, Sugerencia> = {};
        pendientes.forEach(({ key }) => {
          fallback[key] = { cuenta: null, origen: null, explicacion_ia: null, confianza_ia: null, cuenta_pago_sugerida: null, cuenta_pago_origen: null };
        });
        setSuggestions({ ...suggestions, ...fallback });
        setSugsLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facturas]);

  const gastoOpts = cuentaOpts(cuentasGasto);
  const pagoOpts  = cuentaOpts(cuentasPago);
  const rfOpts    = impOpts(impuestosRaw, ["retefuente"]);
  const riOpts    = impOpts(impuestosRaw, ["reteica"]);
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
          idx_factura: idx, descripcion: item.descripcion, base: item.base,
          cod_impuesto: impInfo?.codigo ?? cod,
          porcentaje: impInfo?.tarifa ?? item.porcentaje ?? 0,
          valor_impuesto: item.valor_impuesto,
          cuenta_gasto: cgFinal, fuente,
          cuenta_impuesto_deb: impInfo?.cta_compras ?? "",
          cuenta_impuesto_cre: "", es_retencion: false,
          cuenta_pago: pago, cuenta_pago_nombre: pagoNombre,
        });

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

  // ── Guard ────────────────────────────────────────────────────────────────────
  if (!tipoComp) {
    return (
      <div className="flex items-center gap-3 rounded-xl border p-5" style={{ borderColor: "var(--warning-border)", backgroundColor: "var(--warning-bg)", color: "var(--warning-text)" }}>
        <AlertTriangle className="h-5 w-5 shrink-0" />
        <p className="text-sm">Selecciona un <strong>Tipo de comprobante</strong> en la barra lateral antes de continuar.</p>
      </div>
    );
  }

  // ── LIST VIEW ────────────────────────────────────────────────────────────────
  if (selectedIdx === null) {
    const listos = facturas.filter((_, i) => estaCompleta(i)).length;

    return (
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Mapear cuentas contables
            </h2>
            <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
              {facturas.length} factura{facturas.length !== 1 ? "s" : ""} parseadas · selecciona una para configurarla
              {sugsLoading && (
                <span className="ml-2 inline-flex items-center gap-1" style={{ color: "var(--brand)" }}>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Cargando sugerencias IA…
                </span>
              )}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setPaso(1)}>← Volver</Button>
            <Button size="sm" onClick={handleValidar}>Validar partida doble →</Button>
          </div>
        </div>

        {/* Progress bar */}
        <div
          className="flex items-center gap-3 rounded-xl border px-4 py-3"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
        >
          <div className="flex-1 h-1.5 overflow-hidden rounded-full" style={{ backgroundColor: "var(--border-soft)" }}>
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{ width: `${(listos / facturas.length) * 100}%`, backgroundColor: "var(--success)" }}
            />
          </div>
          <span className="whitespace-nowrap text-xs" style={{ color: "var(--text-muted)" }}>
            {listos} / {facturas.length} configuradas
          </span>
        </div>

        {/* Overlay pantalla completa mientras carga sugerencias IA */}
        {sugsLoading && (
          <div
            className="fixed inset-0 z-[9999] flex flex-col items-center justify-center gap-6"
            style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
          >
            <div className="relative flex h-24 w-24 items-center justify-center">
              <span
                className="absolute h-24 w-24 rounded-full border-4 border-transparent animate-spin"
                style={{ borderTopColor: "#059669", borderRightColor: "#0891b2", animationDuration: "1s" }}
              />
              <span
                className="absolute h-16 w-16 rounded-full border-4 border-transparent animate-spin"
                style={{ borderTopColor: "#0891b2", animationDuration: "0.7s", animationDirection: "reverse" }}
              />
              <Sparkles className="h-8 w-8" style={{ color: "#fff" }} />
            </div>
            <div className="flex flex-col items-center gap-2 text-center">
              <p className="text-lg font-semibold text-white">Analizando sugerencias IA</p>
              <p className="rounded-full px-3 py-0.5 text-sm" style={{ backgroundColor: "rgba(255,255,255,0.12)", color: "rgba(255,255,255,0.8)" }}>
                {facturas.length} facturas · {facturas.reduce((s, f) => s + f.items.length, 0)} ítems
              </p>
              <p className="text-xs" style={{ color: "rgba(255,255,255,0.5)" }}>
                Por favor espera antes de configurar las facturas…
              </p>
            </div>
            <div className="flex gap-1.5">
              {[0, 1, 2, 3, 4].map((i) => (
                <span
                  key={i}
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: "#059669", animation: `sug-bounce 1.2s ease-in-out ${i * 0.15}s infinite` }}
                />
              ))}
            </div>
            <style>{`@keyframes sug-bounce { 0%,80%,100%{transform:scaleY(1);opacity:.4} 40%{transform:scaleY(2);opacity:1} }`}</style>
          </div>
        )}

        {/* Invoice table */}
        <div
          className="overflow-hidden rounded-xl border"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-card)" }}
        >
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                {["#", "N° Factura", "Proveedor / NIT", "Fecha", "Subtotal", "Total", "Estado", ""].map((h) => (
                  <th
                    key={h}
                    className={`px-4 py-3 text-xs font-semibold uppercase tracking-wide${h === "Total" ? " text-right" : " text-left"}`}
                    style={{ color: "var(--text-muted)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {facturas.map((f, idx) => {
                const isListo = estaCompleta(idx);
                const isVerificada = !!verificadas[idx];
                const numSugs = f.items.filter((_, jdx) => suggestions[`${idx}_${jdx}`]?.cuenta).length;
                const subtotal = f.items.reduce((s, it) => s + it.base, 0);
                return (
                  <tr
                    key={idx}
                    id={`invoice-row-${idx}`}
                    className="cursor-pointer transition-colors tr-row"
                    style={{ borderBottom: idx < facturas.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                    onClick={() => setSelectedIdx(idx)}
                  >
                    <td className="px-4 py-3">
                      <div
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-xs font-semibold"
                        style={{ backgroundColor: "var(--info-bg)", color: "var(--info-text)", border: "1px solid var(--info-border)" }}
                      >
                        {idx + 1}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                      {f.numero_dian}
                    </td>
                    <td className="max-w-[220px] px-4 py-3">
                      <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }} title={f.razon_social}>
                        {f.razon_social}
                      </p>
                      <p className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>{f.nit}</p>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-xs" style={{ color: "var(--text-secondary)" }}>
                      {f.fecha}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm" style={{ color: "var(--text-secondary)" }}>
                      {fmt(subtotal)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                      {fmt(f.total)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {isVerificada ? (
                          <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                            style={{ backgroundColor: "color-mix(in srgb, var(--success) 22%, transparent)", color: "var(--success)", border: "1.5px solid color-mix(in srgb, var(--success) 50%, transparent)" }}
                          >
                            <CheckCircle2 className="h-3 w-3" /> Verificada
                          </span>
                        ) : isListo ? (
                          <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                            style={{ backgroundColor: "color-mix(in srgb, var(--success) 10%, transparent)", color: "var(--success)", border: "1px solid color-mix(in srgb, var(--success) 25%, transparent)", opacity: 0.85 }}
                          >
                            <CheckCircle2 className="h-3 w-3" /> Configurada
                          </span>
                        ) : (
                          <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                            style={{ backgroundColor: "var(--warning-bg)", color: "var(--warning-text)", border: "1px solid var(--warning-border)" }}
                          >
                            <Clock className="h-3 w-3" /> Pendiente
                          </span>
                        )}
                        {!sugsLoading && numSugs > 0 && !isListo && (
                          <span className="inline-flex items-center gap-0.5 text-xs" style={{ color: "var(--brand)" }}>
                            <Sparkles className="h-3 w-3" />{numSugs}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80"
                        style={{
                          borderColor: isListo ? "var(--border-soft)" : "var(--brand)",
                          color: isListo ? "var(--text-muted)" : "var(--brand)",
                          backgroundColor: isListo ? "var(--bg-elevated)" : "color-mix(in srgb, var(--brand) 8%, transparent)",
                        }}
                        onClick={(e) => { e.stopPropagation(); setSelectedIdx(idx); }}
                      >
                        {isListo ? "Editar" : "Configurar"} <ChevronRight className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // ── DETAIL VIEW ──────────────────────────────────────────────────────────────
  const factura = facturas[selectedIdx];
  const isFirst = selectedIdx === 0;
  const isLast  = selectedIdx === facturas.length - 1;
  const retGlobalActiva = !!(rfGlobal[selectedIdx] || riGlobal[selectedIdx]);
  const isVerificada = !!verificadas[selectedIdx];
  const cuentaPagoVacia = !cuentaPago[selectedIdx];
  // No pulsar si todos los ítems ya tienen cuenta asignada por aprendizaje/regla
  const todosItemsTienenCuenta = factura.items.every((_, jdx) => !!cuentaGastoItem[`${selectedIdx}_${jdx}`]);
  const cuentaGastoGlobalVacia = !cuentaGastoGlobal[selectedIdx] && !todosItemsTienenCuenta;
  // Sugerencia IA de cuenta_pago: buscar la primera sugerencia con cuenta_pago de origen IA
  const esOrigenIA = (o: string | null | undefined) => ["ia_alta", "ia_media", "ia_baja", "ia"].includes(o ?? "");
  const cuentaPagoIASug = (() => {
    if (!cuentaPagoVacia || sugsLoading) return null;
    for (let jdx = 0; jdx < factura.items.length; jdx++) {
      const sug = suggestions[`${selectedIdx}_${jdx}`];
      if (sug?.cuenta_pago_sugerida && esOrigenIA(sug.cuenta_pago_origen)) return sug;
    }
    return null;
  })();

  return (
    <>
    <style>{`
      @keyframes ring-pulse {
        0%, 100% { box-shadow: 0 0 0 0px rgba(245,158,11,0.5); }
        50%       { box-shadow: 0 0 0 4px rgba(245,158,11,0.12); }
      }
      .require-pulse { animation: ring-pulse 1.8s ease-in-out infinite; border-color: rgba(245,158,11,0.6) !important; }
      .require-row   { background: color-mix(in srgb, #f59e0b 6%, transparent) !important; }
    `}</style>
    <div className="space-y-4">
      {/* Navigation bar */}
      <div className="flex items-center gap-2">
        <button
          onClick={goBackToList}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
          style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Lista
        </button>
        <div className="flex-1" />
        <button
          disabled={isFirst}
          onClick={() => setSelectedIdx(selectedIdx - 1)}
          className="flex h-8 w-8 items-center justify-center rounded-lg border transition-opacity disabled:opacity-30 hover:opacity-80"
          style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="min-w-[90px] text-center text-sm" style={{ color: "var(--text-muted)" }}>
          Factura <strong style={{ color: "var(--text-primary)" }}>{selectedIdx + 1}</strong> / {facturas.length}
        </span>
        <button
          disabled={isLast}
          onClick={() => setSelectedIdx(selectedIdx + 1)}
          className="flex h-8 w-8 items-center justify-center rounded-lg border transition-opacity disabled:opacity-30 hover:opacity-80"
          style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        {estaCompleta(selectedIdx) && (
          <button
            onClick={() => setVerificadas(p => ({ ...p, [selectedIdx]: !p[selectedIdx] }))}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold transition-opacity hover:opacity-80"
            style={verificadas[selectedIdx]
              ? { backgroundColor: "var(--success)", color: "#fff", border: "none" }
              : { border: "1.5px solid var(--success)", color: "var(--success)", backgroundColor: "transparent" }
            }
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {verificadas[selectedIdx] ? "Verificada" : "Verificar"}
          </button>
        )}
      </div>

      {/* Banner de verificada */}
      {isVerificada && (
        <div
          className="flex items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium"
          style={{ borderColor: "color-mix(in srgb, var(--success) 40%, transparent)", backgroundColor: "color-mix(in srgb, var(--success) 10%, transparent)", color: "var(--success)" }}
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          Factura verificada — para editar, haz clic en "Verificada" arriba para quitar la verificación.
        </div>
      )}

      {/* Invoice header card */}
      <div
        className="rounded-xl border p-4"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-card)" }}
      >
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-5">
          <DataField label="N° Factura DIAN" value={factura.numero_dian} mono />
          <DataField label="Fecha emisión" value={factura.fecha} />
          <div className="col-span-2">
            <DataField label="Proveedor" value={factura.razon_social} />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Total factura</p>
            <p className="mt-1 text-xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmt(factura.total)}</p>
          </div>
        </div>
        {factura.advertencias && factura.advertencias.length > 0 && (
          <div
            className="mt-3 flex items-start gap-2 rounded-lg px-3 py-2 text-xs"
            style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning-border)", color: "var(--warning-text)" }}
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <ul className="space-y-0.5">
              {factura.advertencias.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}
      </div>

      {/* Datos del proveedor */}
      <div
        className="rounded-xl border p-4 space-y-3"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
      >
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Datos del proveedor</p>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>NIT proveedor</label>
            <input
              value={nitEdit[selectedIdx] ?? factura.nit}
              onChange={(e) => setNitEdit((p) => ({ ...p, [selectedIdx]: e.target.value }))}
              disabled={isVerificada}
              className="flex h-9 w-full rounded-lg border px-3 text-sm outline-none transition-colors focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50"
              style={{ borderColor: "var(--border-strong)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)" }}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Tipo proveedor</label>
            <select
              value={tipoProveedor[selectedIdx] ?? factura.tipo_proveedor ?? "juridica"}
              onChange={(e) => setTipoProveedor((p) => ({ ...p, [selectedIdx]: e.target.value }))}
              disabled={isVerificada}
              className="flex h-9 w-full rounded-lg border px-3 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-50"
              style={{ borderColor: "var(--border-strong)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)" }}
            >
              <option value="juridica">Jurídica</option>
              <option value="natural">Natural</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium flex items-center gap-1.5" style={{ color: cuentaPagoVacia ? "rgb(245,158,11)" : "var(--text-muted)" }}>
              Cuenta de pago
              {cuentaPagoVacia && <span className="text-[10px] font-semibold uppercase tracking-wide rounded px-1 py-0.5" style={{ backgroundColor: "rgba(245,158,11,0.15)", color: "rgb(245,158,11)" }}>Requerida</span>}
            </label>
            {cuentaPagoIASug && (() => {
              const iaBadge = ORIGEN_BADGE[cuentaPagoIASug.cuenta_pago_origen ?? "ia"] ?? ORIGEN_BADGE.ia;
              const nombrePago = cuentasPago.find(c => c.codigo === cuentaPagoIASug.cuenta_pago_sugerida)?.nombre ?? cuentaPagoIASug.cuenta_pago_sugerida;
              return (
                <div
                  className="rounded-lg px-3 py-2 space-y-1"
                  style={{ backgroundColor: "color-mix(in srgb, var(--brand) 6%, transparent)", border: "1px solid color-mix(in srgb, var(--brand) 20%, transparent)" }}
                >
                  <div className="flex items-center gap-1.5">
                    <Badge variant={iaBadge.variant}><Sparkles className="mr-0.5 inline h-2.5 w-2.5" /> {iaBadge.label}</Badge>
                    <span className="text-xs font-medium font-mono" style={{ color: "var(--brand)" }}>{cuentaPagoIASug.cuenta_pago_sugerida}</span>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{(nombrePago ?? "").length > 45 ? (nombrePago ?? "").slice(0, 45) + "…" : (nombrePago ?? "")}</p>
                  <button
                    type="button"
                    disabled={isVerificada}
                    onClick={() => setCuentaPago(p => ({ ...p, [selectedIdx]: cuentaPagoIASug.cuenta_pago_sugerida! }))}
                    className="flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
                    style={{ backgroundColor: "var(--brand)", color: "#fff" }}
                  >
                    <Sparkles className="h-3 w-3" /> Usar esta cuenta
                  </button>
                </div>
              );
            })()}
            <div className={cuentaPagoVacia ? "require-pulse rounded-lg" : ""}>
              <Combobox
                options={pagoOpts}
                value={cuentaPago[selectedIdx] ?? ""}
                onChange={(v) => setCuentaPago((p) => ({ ...p, [selectedIdx]: v }))}
                placeholder="Buscar cuenta de pago…"
                disabled={isVerificada}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Global config — key differentiator */}
      <div
        className="rounded-xl border p-4 space-y-3"
        style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}
      >
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--info-text)" }}>
            Global — aplica a todos los ítems de esta factura
          </p>
          <div className="flex gap-1.5">
            <button
              type="button"
              disabled={isVerificada}
              onClick={() => setDlgOpen("retefuente")}
              className="flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
              style={{ borderColor: "var(--info-border)", color: "var(--info-text)", backgroundColor: "rgba(255,255,255,0.12)" }}
            >
              <Plus className="h-3 w-3" /> Retefuente
            </button>
            <button
              type="button"
              disabled={isVerificada}
              onClick={() => setDlgOpen("reteica")}
              className="flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
              style={{ borderColor: "var(--info-border)", color: "var(--info-text)", backgroundColor: "rgba(255,255,255,0.12)" }}
            >
              <Plus className="h-3 w-3" /> ReteICA
            </button>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium flex items-center gap-1.5" style={{ color: "var(--info-text)", opacity: 0.85 }}>
              Cuenta gasto/costo
              {cuentaGastoGlobalVacia && <span className="text-[10px] font-semibold uppercase tracking-wide rounded px-1 py-0.5" style={{ backgroundColor: "rgba(245,158,11,0.25)", color: "rgb(245,158,11)", opacity: 1 }}>O por ítem</span>}
            </label>
            <div className={cuentaGastoGlobalVacia ? "require-pulse rounded-lg" : ""}>
              <Combobox
                options={gastoOpts}
                value={cuentaGastoGlobal[selectedIdx] ?? ""}
                onChange={(v) => setCuentaGastoGlobal((p) => ({ ...p, [selectedIdx]: v }))}
                placeholder="Aplica a todos los ítems…"
                disabled={isVerificada}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium" style={{ color: "var(--info-text)", opacity: 0.85 }}>Retefuente</label>
            <Combobox
              options={rfOpts}
              value={rfGlobal[selectedIdx] ?? ""}
              onChange={(v) => setRfGlobal((p) => ({ ...p, [selectedIdx]: v }))}
              placeholder="Código retefuente…"
              disabled={isVerificada}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium" style={{ color: "var(--info-text)", opacity: 0.85 }}>ReteICA</label>
            <Combobox
              options={riOpts}
              value={riGlobal[selectedIdx] ?? ""}
              onChange={(v) => setRiGlobal((p) => ({ ...p, [selectedIdx]: v }))}
              placeholder="Código reteica…"
              disabled={isVerificada}
            />
          </div>
        </div>
      </div>

      {/* Items table */}
      <div
        className="overflow-hidden rounded-xl border"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-card)" }}
      >
        <div
          className="flex flex-wrap items-center gap-3 border-b px-4 py-3"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
        >
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Ítems{" "}
            <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
              ({factura.items.length})
            </span>
          </p>
          {sugsLoading && (
            <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--brand)" }}>
              <Loader2 className="h-3 w-3 animate-spin" /> Cargando sugerencias IA…
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5"
                style={{ color: "var(--text-muted)" }}
              />
              <input
                value={searchItems}
                onChange={(e) => setSearchItems(e.target.value)}
                placeholder="Buscar ítem…"
                className="h-8 rounded-lg pl-8 pr-3 text-xs outline-none focus:ring-2 focus:ring-[var(--brand)]"
                style={{
                  width: "180px",
                  border: "1px solid var(--border-strong)",
                  backgroundColor: "var(--bg-surface)",
                  color: "var(--text-primary)",
                }}
              />
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)", minWidth: "220px" }}>Descripción</th>
                <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Base</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Impuesto</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)", minWidth: "260px" }}>Cuenta gasto/costo</th>
                {!retGlobalActiva && (
                  <>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Retefuente</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>ReteICA</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {factura.items
                .map((item, jdx) => ({ item, jdx }))
                .filter(({ item }) => !searchItems || item.descripcion.toLowerCase().includes(searchItems.toLowerCase()))
                .map(({ item, jdx }) => {
                const key = `${selectedIdx}_${jdx}`;
                const impInfo = item.cod_impuesto ? getImpInfo(item.cod_impuesto) : null;
                const sug = suggestions[key];
                const currentVal = cuentaGastoGlobal[selectedIdx] || cuentaGastoItem[key];
                // Badge solo cuando hay cuenta seleccionada por el usuario (o por regla/aprendizaje)
                const origenEfectivo = currentVal
                  ? (sug?.cuenta && currentVal === sug.cuenta && !esOrigenIA(sug.origen)
                    ? (sug.origen ?? "aprendizaje")
                    : "manual")
                  : null;
                const badge = origenEfectivo ? (ORIGEN_BADGE[origenEfectivo] ?? ORIGEN_BADGE.manual) : null;
                // Sugerencia IA pendiente de aceptar (sin cuenta seleccionada aún)
                const iaSugerencia = !sugsLoading && !currentVal && !cuentaGastoGlobal[selectedIdx]
                  && sug?.cuenta && esOrigenIA(sug.origen) ? sug : null;
                const sinSugerencia = !sugsLoading && sug && sug.cuenta === null && !currentVal && !cuentaGastoGlobal[selectedIdx];
                const sinCatalogo = sug?.origen === "sin_catalogo";
                const iaNoDisponible = sug?.origen === "ia_no_disponible";
                const itemSinCuenta = !currentVal && !cuentaGastoGlobal[selectedIdx];

                return (
                  <tr
                    key={jdx}
                    className={itemSinCuenta ? "require-row" : ""}
                    style={{ borderBottom: jdx < factura.items.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                  >
                    {/* Descripción */}
                    <td className="px-4 py-3" style={{ minWidth: "220px", maxWidth: "300px" }}>
                      <p className="truncate text-sm" style={{ color: "var(--text-secondary)" }} title={item.descripcion}>
                        {item.descripcion}
                      </p>
                    </td>

                    {/* Base */}
                    <td className="px-4 py-3 text-right tabular-nums font-medium" style={{ color: "var(--success)" }}>
                      {fmt(item.base)}
                    </td>

                    {/* Impuesto */}
                    <td className="px-4 py-3">
                      {impInfo ? (
                        <div className="space-y-0.5">
                          <Badge variant="info">{impInfo.tipo_impuesto} {impInfo.tarifa}%</Badge>
                          <p className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>{impInfo.codigo}</p>
                        </div>
                      ) : (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>

                    {/* Cuenta gasto */}
                    <td className="min-w-[260px] px-4 py-3">
                      <div className="space-y-1.5">
                        {/* Cuenta ya seleccionada: badge de origen (regla/aprendizaje/manual) */}
                        {badge && (
                          <div className="flex items-center gap-1.5">
                            <Badge variant={badge.variant}>
                              {badge.variant === "success" && <Sparkles className="mr-0.5 inline h-2.5 w-2.5" />}
                              {badge.label}
                            </Badge>
                          </div>
                        )}

                        {/* Sugerencia IA pendiente: tarjeta con botón para aceptar */}
                        {iaSugerencia && (() => {
                          const iaBadge = ORIGEN_BADGE[iaSugerencia.origen ?? "ia"] ?? ORIGEN_BADGE.ia;
                          const nombreCuenta = cuentasGasto.find(c => c.codigo === iaSugerencia.cuenta)?.nombre ?? iaSugerencia.cuenta;
                          return (
                            <div
                              className="rounded-lg px-3 py-2 space-y-1.5"
                              style={{ backgroundColor: "color-mix(in srgb, var(--brand) 6%, transparent)", border: "1px solid color-mix(in srgb, var(--brand) 20%, transparent)" }}
                            >
                              <div className="flex items-center gap-1.5">
                                <Badge variant={iaBadge.variant}>
                                  <Sparkles className="mr-0.5 inline h-2.5 w-2.5" /> {iaBadge.label}
                                </Badge>
                                <span className="text-xs font-medium font-mono" style={{ color: "var(--brand)" }}>{iaSugerencia.cuenta}</span>
                              </div>
                              <p className="text-xs" style={{ color: "var(--text-secondary)" }} title={nombreCuenta ?? ""}>{(nombreCuenta ?? "").length > 40 ? (nombreCuenta ?? "").slice(0, 40) + "…" : (nombreCuenta ?? "")}</p>
                              {iaSugerencia.explicacion_ia && (
                                <p className="text-xs italic" style={{ color: "var(--text-muted)" }}>{iaSugerencia.explicacion_ia.length > 60 ? iaSugerencia.explicacion_ia.slice(0, 60) + "…" : iaSugerencia.explicacion_ia}</p>
                              )}
                              <button
                                type="button"
                                disabled={isVerificada}
                                onClick={() => setCuentaGastoItem(p => ({ ...p, [key]: iaSugerencia.cuenta! }))}
                                className="flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
                                style={{ backgroundColor: "var(--brand)", color: "#fff" }}
                              >
                                <Sparkles className="h-3 w-3" /> Usar esta cuenta
                              </button>
                            </div>
                          );
                        })()}

                        <Combobox
                          options={gastoOpts}
                          value={currentVal ?? ""}
                          onChange={(v) => setCuentaGastoItem((p) => ({ ...p, [key]: v }))}
                          disabled={isVerificada || !!cuentaGastoGlobal[selectedIdx]}
                          placeholder={cuentaGastoGlobal[selectedIdx] ? "← Usando cuenta global" : iaSugerencia ? "Acepta sugerencia o busca otra…" : "Buscar cuenta…"}
                        />

                        {/* Avisos */}
                        {sinCatalogo && (
                          <div className="flex items-start gap-1.5 rounded px-2 py-1.5" style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning-border)" }}>
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" style={{ color: "var(--warning-text)" }} />
                            <p className="text-xs leading-snug" style={{ color: "var(--warning-text)" }}>Carga tu catálogo PUC para activar sugerencias IA.</p>
                          </div>
                        )}
                        {!sinCatalogo && sinSugerencia && (
                          <div className="flex items-start gap-1.5 rounded px-2 py-1.5" style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning-border)" }}>
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" style={{ color: "var(--warning-text)" }} />
                            <p className="text-xs leading-snug" style={{ color: "var(--warning-text)" }}>
                              {iaNoDisponible ? "IA no configurada — selecciona manualmente." : "Sin mapeo previo — selecciona manualmente."}
                            </p>
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Retefuente / ReteICA por ítem (solo si no hay global) */}
                    {!retGlobalActiva && (
                      <>
                        <td className="min-w-[160px] px-4 py-3">
                          <Combobox
                            options={rfOpts}
                            value={rfItem[key] ?? ""}
                            onChange={(v) => setRfItem((p) => ({ ...p, [key]: v }))}
                            placeholder="Retefuente…"
                            disabled={isVerificada}
                          />
                        </td>
                        <td className="min-w-[160px] px-4 py-3">
                          <Combobox
                            options={riOpts}
                            value={riItem[key] ?? ""}
                            onChange={(v) => setRiItem((p) => ({ ...p, [key]: v }))}
                            placeholder="ReteICA…"
                            disabled={isVerificada}
                          />
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
              {retGlobalActiva && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-2.5 text-xs"
                    style={{ backgroundColor: "color-mix(in srgb, var(--info-bg) 60%, transparent)", color: "var(--info-text)" }}
                  >
                    Retención global activa — los selectores por ítem están deshabilitados
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Footer navigation */}
      <div className="flex items-center justify-between gap-2 pb-4 pt-2">
        <div className="flex gap-2">
          <button
            onClick={() => setSelectedIdx(null)}
            className="flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-opacity hover:opacity-80"
            style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Lista
          </button>
          <button
            disabled={isFirst}
            onClick={() => setSelectedIdx(selectedIdx - 1)}
            className="flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-opacity disabled:opacity-30 hover:opacity-80"
            style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
          >
            <ChevronLeft className="h-3.5 w-3.5" /> Anterior
          </button>
        </div>

        <span className="text-sm tabular-nums" style={{ color: "var(--text-muted)" }}>
          {selectedIdx + 1} / {facturas.length}
        </span>

        <div className="flex gap-2">
          {!isLast ? (
            <button
              onClick={() => setSelectedIdx(selectedIdx + 1)}
              className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition-opacity hover:opacity-90"
              style={{ backgroundColor: "var(--brand)", color: "#fff" }}
            >
              Siguiente <ChevronRight className="h-3.5 w-3.5" />
            </button>
          ) : (
            <Button size="lg" onClick={handleValidar}>
              Validar partida doble →
            </Button>
          )}
        </div>
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
    </>
  );
}
