"use client";

import React, { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Combobox } from "@/components/ui/combobox";
import { Badge } from "@/components/ui/badge";
import { DataTableShell, FilterChips, SortableTh, useDataTable } from "@/components/ui/data-table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AlertCircle, Database, Receipt, BookOpen, Brain, Upload, Download, CheckCircle2, Trash2, Loader2, FileSpreadsheet } from "lucide-react";
import type { CuentaOpcion, ImpuestoOut, TipoComprobanteOpcion, IARegla, IADecision } from "@/lib/types";

// - Module-level stable search functions -
const searchImpuesto = (i: ImpuestoOut, q: string) =>
  i.codigo.toLowerCase().includes(q) ||
  (i.nombre ?? "").toLowerCase().includes(q) ||
  (i.tipo_impuesto ?? "").toLowerCase().includes(q);

const searchCuenta = (c: CuentaOpcion, q: string) =>
  c.codigo.toLowerCase().includes(q) || c.nombre.toLowerCase().includes(q);

const searchTipo = (t: TipoComprobanteOpcion, q: string) =>
  t.codigo.toLowerCase().includes(q) || t.titulo.toLowerCase().includes(q);

const searchRegla = (r: IARegla, q: string) =>
  r.patron.toLowerCase().includes(q) ||
  (r.cuenta_puc ?? "").toLowerCase().includes(q);

const searchDecision = (d: IADecision, q: string) =>
  (d.nit_proveedor ?? "").toLowerCase().includes(q) ||
  (d.descripcion_item ?? "").toLowerCase().includes(q) ||
  (d.cuenta_aplicada ?? "").toLowerCase().includes(q);

// - Types -
type UploadResult = { insertados: number; actualizados: number; omitidos_codigo?: number; omitidos_nivel?: number; omitidos?: number; formato?: string; errores: { fila: number; error: string }[] };

// - Full-screen loading overlay shown while a file is being processed -
function UploadOverlay({ filename }: { filename: string }) {
  return (
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center gap-6"
      style={{ backgroundColor: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)" }}
    >
      {/* Animated rings */}
      <div className="relative flex h-24 w-24 items-center justify-center">
        <span
          className="absolute h-24 w-24 rounded-full border-4 border-transparent animate-spin"
          style={{ borderTopColor: "#059669", borderRightColor: "#0891b2", animationDuration: "1s" }}
        />
        <span
          className="absolute h-16 w-16 rounded-full border-4 border-transparent animate-spin"
          style={{ borderTopColor: "#0891b2", animationDuration: "0.7s", animationDirection: "reverse" }}
        />
        <FileSpreadsheet className="h-8 w-8" style={{ color: "#fff" }} />
      </div>

      {/* Text */}
      <div className="flex flex-col items-center gap-2 text-center">
        <p className="text-lg font-semibold text-white">Procesando archivo</p>
        <p className="max-w-xs truncate rounded-full px-3 py-0.5 text-sm" style={{ backgroundColor: "rgba(255,255,255,0.12)", color: "rgba(255,255,255,0.8)" }}>
          {filename}
        </p>
        <p className="text-xs" style={{ color: "rgba(255,255,255,0.5)" }}>
          No cierres esta ventana mientras termina la carga…
        </p>
      </div>

      {/* Animated dots progress bar */}
      <div className="flex gap-1.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 rounded-full"
            style={{
              backgroundColor: "#059669",
              animation: `bounce 1.2s ease-in-out ${i * 0.15}s infinite`,
            }}
          />
        ))}
      </div>

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scaleY(1); opacity: 0.4; }
          40% { transform: scaleY(2); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// - Upload Excel panel with confirmation dialog + spinner -
function UploadExcelPanel({
  onUpload,
  onPlantilla,
  onLimpiar,
  onSuccess,
  limpiarLabel = "Limpiar catálogo",
}: {
  onUpload: (file: File) => Promise<UploadResult>;
  onPlantilla: () => Promise<Blob>;
  onLimpiar?: () => Promise<{ desactivados: number }>;
  onSuccess: () => void;
  limpiarLabel?: string;
}) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [err, setErr] = useState("");

  // Confirmation before upload
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [lastFilename, setLastFilename] = useState("");
  const [confirmUploadOpen, setConfirmUploadOpen] = useState(false);

  // Clear catalog
  const [confirmLimpiarOpen, setConfirmLimpiarOpen] = useState(false);
  const [limpiando, setLimpiando] = useState(false);
  const [limpiarResult, setLimpiarResult] = useState<{ desactivados: number } | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setErr("");
    setResult(null);
    setLimpiarResult(null);
    setPendingFile(file);
    setConfirmUploadOpen(true);
  };

  const handleConfirmUpload = async () => {
    if (!pendingFile) return;
    const file = pendingFile;
    setLastFilename(file.name);
    setConfirmUploadOpen(false);
    setPendingFile(null);   // limpiar antes de la carga para que el overlay se muestre
    setUploading(true);
    setErr("");
    setResult(null);
    try {
      const res = await onUpload(file);
      setResult(res);
      onSuccess();
    } catch (ex) {
      const raw = (ex as Error).message ?? "";
      if (raw.includes("columna 'codigo'") || raw.includes("columna 'titulo'") || raw.includes("columna 'nombre'")) {
        setErr("Archivo no válido para esta sección. Verifica que estés en el tab correcto o usa la plantilla de ejemplo.");
      } else if (raw.includes("No se pudo leer")) {
        setErr("No se pudo leer el archivo. Asegúrate de que sea un Excel (.xlsx) válido.");
      } else {
        setErr(raw);
      }
    }
    setUploading(false);
  };

  const handlePlantilla = async () => {
    try {
      const blob = await onPlantilla();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "plantilla.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setErr("No se pudo descargar la plantilla");
    }
  };

  const handleLimpiar = async () => {
    if (!onLimpiar) return;
    setConfirmLimpiarOpen(false);
    setLimpiando(true);
    setResult(null);
    setErr("");
    try {
      const res = await onLimpiar();
      setLimpiarResult(res);
      onSuccess();
    } catch (ex) {
      setErr((ex as Error).message);
    }
    setLimpiando(false);
  };

  return (
    <>
      {/* Full-screen overlay blocks all interaction while uploading */}
      {uploading && <UploadOverlay filename={lastFilename} />}

      <div
        className="flex flex-wrap items-center gap-3 rounded-xl border p-3"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
      >
        {/* Upload button */}
        <label
          className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
          style={{
            backgroundColor: "var(--brand)",
            color: "#fff",
            pointerEvents: uploading ? "none" : "auto",
            opacity: uploading ? 0.6 : 1,
          }}
        >
          <Upload className="h-3.5 w-3.5" />
          Cargar desde Excel
          <input type="file" accept=".xlsx,.xls" className="sr-only" onChange={handleFileSelect} disabled={uploading} />
        </label>

        {/* Download template */}
        <button
          type="button"
          onClick={handlePlantilla}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
          style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
        >
          <Download className="h-3.5 w-3.5" />
          Descargar plantilla
        </button>

        {/* Limpiar catálogo */}
        {onLimpiar && (
          <button
            type="button"
            onClick={() => { setLimpiarResult(null); setErr(""); setConfirmLimpiarOpen(true); }}
            disabled={limpiando}
            className="ml-auto flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-50"
            style={{ borderColor: "var(--error-border)", color: "var(--error)", backgroundColor: "var(--error-bg)" }}
          >
            {limpiando ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            {limpiando ? "Limpiando..." : limpiarLabel}
          </button>
        )}

        {/* Upload result */}
        {result && !err && (
          <div className="w-full flex flex-col gap-0.5 text-sm pt-1 border-t" style={{ borderColor: "var(--border-soft)" }}>
            <div className="flex items-center gap-1.5" style={{ color: "var(--success)" }}>
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              {result.insertados} nuevas · {result.actualizados} actualizadas
              {result.formato && (
                <span className="rounded px-1.5 py-0.5 text-xs font-medium" style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border-soft)" }}>
                  {result.formato === "siigo" ? "SIIGO" : "Plantilla"}
                </span>
              )}
            </div>
            {((result.omitidos_codigo ?? 0) > 0 || (result.omitidos_nivel ?? 0) > 0) && (
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                Omitidas: {result.omitidos_codigo ?? 0} sin 8 dígitos
                {(result.omitidos_nivel ?? 0) > 0 && ` · ${result.omitidos_nivel} no Transaccional`}
              </div>
            )}
            {(result.omitidos ?? 0) > 0 && (
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                Omitidas: {result.omitidos} filas de pie de página
              </div>
            )}
            {result.errores.length > 0 && (
              <div className="text-xs" style={{ color: "var(--warning)" }}>
                {result.errores.length} error(es) al procesar
              </div>
            )}
          </div>
        )}

        {/* Limpiar result */}
        {limpiarResult && !err && (
          <div className="w-full flex items-center gap-1.5 text-sm pt-1 border-t" style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}>
            <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "var(--success)" }} />
            Se desactivaron {limpiarResult.desactivados} registros del catálogo.
          </div>
        )}

        {err && (
          <div className="w-full flex items-center gap-1.5 text-sm" style={{ color: "var(--error)" }}>
            <AlertCircle className="h-4 w-4 shrink-0" />
            {err}
          </div>
        )}
      </div>

      {/* Modal: confirmar carga */}
      <Dialog open={confirmUploadOpen} onOpenChange={(o) => { if (!o) { setConfirmUploadOpen(false); setPendingFile(null); } }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Confirmar carga de archivo</DialogTitle>
            <DialogDescription>Revisa el archivo antes de iniciar la carga al catálogo.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-1">
            <div
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
            >
              <span className="font-medium" style={{ color: "var(--text-primary)" }}>{pendingFile?.name}</span>
              <br />
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {pendingFile ? `${(pendingFile.size / 1024).toFixed(1)} KB` : ""}
              </span>
            </div>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Los registros existentes se actualizarán y los nuevos se agregarán al catálogo.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => { setConfirmUploadOpen(false); setPendingFile(null); }}
                className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
                style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmUpload}
                className="flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-sm font-semibold transition-opacity hover:opacity-80"
                style={{ backgroundColor: "var(--brand)", color: "#fff" }}
              >
                <Upload className="h-3.5 w-3.5" />
                Confirmar carga
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Modal: confirmar limpiar */}
      <Dialog open={confirmLimpiarOpen} onOpenChange={setConfirmLimpiarOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>¿Limpiar catálogo?</DialogTitle>
            <DialogDescription>Esta acción desactivará todos los registros actuales de la empresa.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-1">
            <div
              className="rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)", color: "var(--error)" }}
            >
              Todos los registros actuales serán desactivados. Esta acción no se puede deshacer fácilmente.
            </div>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Útil para reimportar el catálogo desde cero. Los registros se marcan como inactivos (no se eliminan físicamente).
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmLimpiarOpen(false)}
                className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-opacity hover:opacity-80"
                style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleLimpiar}
                className="flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-sm font-semibold transition-opacity hover:opacity-80"
                style={{ backgroundColor: "var(--error)", color: "#fff" }}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Sí, limpiar
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// - Error banner -
function ErrBanner({ msg }: { msg: string }) {
  return (
    <div
      className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
      style={{
        backgroundColor: "var(--error-bg)",
        borderColor: "var(--error-border)",
        color: "var(--error)",
      }}
    >
      <AlertCircle className="h-4 w-4 shrink-0" />
      {msg}
    </div>
  );
}

// - Tabs config -
const TABS = [
  { id: "Codigos de Impuesto", label: "Impuestos", icon: Receipt, tutorialId: "tab-impuestos" },
  { id: "Plan de Cuentas PUC", label: "Plan de Cuentas", icon: BookOpen, tutorialId: "tab-cuentas" },
  { id: "Tipos de Comprobante", label: "Comprobantes", icon: Database, tutorialId: "tab-tipos" },
  { id: "Control IA", label: "Control IA", icon: Brain, tutorialId: "tab-ia" },
] as const;
type TabId = (typeof TABS)[number]["id"];

// - KPI stat card -
function StatCard({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div
      className="rounded-xl border p-4"
      style={{
        borderColor: "var(--border-soft)",
        backgroundColor: "var(--bg-surface)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {label}
      </p>
      <p className="mt-2 text-3xl font-bold tabular-nums" style={{ color }}>
        {value}
      </p>
    </div>
  );
}

// - Page -
export default function CatalogosPage() {
  const [tab, setTab] = useState<TabId>("Codigos de Impuesto");

  const { data: imps = [] } = useQuery({ queryKey: ["impuestos"], queryFn: api.getImpuestos });
  const { data: cuentasPago = [] } = useQuery({ queryKey: ["cuentas-pago"], queryFn: api.getCuentasPago });
  const { data: cuentasGasto = [] } = useQuery({ queryKey: ["cuentas-gasto"], queryFn: api.getCuentasGasto });
  const { data: tipos = [] } = useQuery({ queryKey: ["tipos-comp"], queryFn: api.getTiposComprobante });

  const totalCuentas = useMemo(() => {
    const uniq = new Set([...cuentasPago.map((c) => c.codigo), ...cuentasGasto.map((c) => c.codigo)]);
    return uniq.size;
  }, [cuentasPago, cuentasGasto]);

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      {/* KPI Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Códigos de impuesto" value={imps.length} color="var(--info)" />
        <StatCard label="Cuentas PUC" value={totalCuentas} color="var(--success)" />
        <StatCard label="Tipos de comprobante" value={tipos.length} color="var(--brand)" />
        <StatCard label="Estado del sistema" value="Activo" color="var(--success)" />
      </div>

      {/* Pill tabs */}
      <div
        className="flex gap-1 overflow-x-auto rounded-xl p-1"
        style={{ backgroundColor: "var(--bg-elevated)", border: "1px solid var(--border-soft)" }}
      >
        {TABS.map(({ id, label, icon: Icon, tutorialId }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              data-tutorial={tutorialId}
              onClick={() => setTab(id)}
              className="flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all"
              style={{
                backgroundColor: active ? "var(--bg-surface)" : "transparent",
                color: active ? "var(--text-primary)" : "var(--text-muted)",
                boxShadow: active ? "var(--shadow-sm)" : "none",
              }}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {tab === "Codigos de Impuesto" && (
        <ImpuestosTab imps={imps} cuentasPago={cuentasPago} cuentasGasto={cuentasGasto} />
      )}
      {tab === "Plan de Cuentas PUC" && (
        <PlanCuentasTab cuentasPago={cuentasPago} cuentasGasto={cuentasGasto} />
      )}
      {tab === "Tipos de Comprobante" && <TiposTab tipos={tipos} />}
      {tab === "Control IA" && <ControlIATab />}
    </div>
  );
}

// -
// IMPUESTOS TAB
// -
function ImpuestosTab({
  imps,
  cuentasPago,
  cuentasGasto,
}: {
  imps: ImpuestoOut[];
  cuentasPago: CuentaOpcion[];
  cuentasGasto: CuentaOpcion[];
}) {
  const qc = useQueryClient();
  const [deletingCodigo, setDeletingCodigo] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState("");
  const [tarifa, setTarifa] = useState("0");
  const [cuentaCre, setCuentaCre] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [filterTipo, setFilterTipo] = useState("all");

  const impsFiltered = useMemo(() => {
    if (filterTipo === "all") return imps;
    return imps.filter((i) => {
      const t = (i.tipo_impuesto ?? "").toLowerCase();
      if (filterTipo === "iva") return t.includes("iva");
      if (filterTipo === "retefuente") return t.includes("retefuente");
      if (filterTipo === "reteica") return t.includes("reteica");
      if (filterTipo === "otro") return !t.includes("iva") && !t.includes("rete");
      return true;
    });
  }, [imps, filterTipo]);

  const dt = useDataTable(impsFiltered, searchImpuesto, {
    sortFns: {
      codigo: (a, b) => a.codigo.localeCompare(b.codigo),
      nombre: (a, b) => (a.nombre ?? "").localeCompare(b.nombre ?? ""),
      tarifa: (a, b) => (a.tarifa ?? 0) - (b.tarifa ?? 0),
      tipo: (a, b) => (a.tipo_impuesto ?? "").localeCompare(b.tipo_impuesto ?? ""),
    },
    defaultSort: { col: "codigo", dir: "asc" },
  });

  const allCuentas: CuentaOpcion[] = [...cuentasPago, ...cuentasGasto];
  const cuentaOpts = allCuentas.map((c) => ({
    value: c.codigo,
    label: c.label ?? `${c.codigo} - ${c.nombre}`,
  }));

  const tipoVariant = (t: string | null): "success" | "info" | "warning" | "purple" | "default" => {
    if (!t) return "default";
    const l = t.toLowerCase();
    if (l.includes("iva")) return "info";
    if (l.includes("retefuente")) return "warning";
    if (l.includes("reteica")) return "purple";
    return "default";
  };

  const handleAdd = async () => {
    if (!codigo.trim() || !cuentaCre) {
      setErr("Código y cuenta crédito son obligatorios.");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      await api.crearImpuesto({
        codigo: codigo.trim(),
        nombre: nombre.trim() || undefined,
        tipo_impuesto: tipo.trim() || undefined,
        tarifa: parseFloat(tarifa) || 0,
        cta_compras: cuentaCre,
      });
      qc.invalidateQueries({ queryKey: ["impuestos"] });
      setCodigo(""); setNombre(""); setTipo(""); setTarifa("0"); setCuentaCre("");
      setModalOpen(false);
    } catch (e) {
      setErr((e as Error).message);
    }
    setSaving(false);
  };

  return (
    <>
      <UploadExcelPanel
        onUpload={api.cargarExcelImpuestos}
        onPlantilla={api.descargarPlantillaImpuestos}
        onLimpiar={api.limpiarImpuestos}
        limpiarLabel="Limpiar impuestos"
        onSuccess={() => qc.invalidateQueries({ queryKey: ["impuestos"] })}
      />
      <DataTableShell
        title="Códigos de impuesto"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        onAdd={() => { setErr(""); setModalOpen(true); }}
        addLabel="Agregar impuesto"
        searchPlaceholder="Buscar por código, nombre o tipo..."
        filters={
          <FilterChips
            label="Tipo"
            value={filterTipo}
            onChange={(v) => { setFilterTipo(v); }}
            options={[
              { value: "all", label: "Todos" },
              { value: "iva", label: "IVA" },
              { value: "retefuente", label: "Retefuente" },
              { value: "reteica", label: "Reteica" },
              { value: "otro", label: "Otro" },
            ]}
          />
        }
      >
        <table className="w-full min-w-[700px] text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <SortableTh label="Código"   col="codigo" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <SortableTh label="Nombre"   col="nombre" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <SortableTh label="Tipo"     col="tipo"   sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <SortableTh label="Tarifa %" col="tarifa" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Cta. Débito</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Cta. Crédito</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {dt.rows.map((i, idx) => (
              <tr
                key={i.id}
                className="tr-row"
                style={{ borderBottom: idx < dt.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}
              >
                <td className="px-4 py-3 font-mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{i.codigo}</td>
                <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{i.nombre ?? "-"}</td>
                <td className="px-4 py-3">
                  <Badge variant={tipoVariant(i.tipo_impuesto)}>{i.tipo_impuesto ?? "-"}</Badge>
                </td>
                <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{i.tarifa ?? "-"}</td>
                <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                  {!(i.tipo_impuesto ?? "").toLowerCase().includes("rete") ? i.cta_compras || "-" : "-"}
                </td>
                <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                  {(i.tipo_impuesto ?? "").toLowerCase().includes("rete") ? i.cta_compras || "-" : "-"}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    disabled={deletingCodigo === i.codigo}
                    onClick={async () => {
                      setDeletingCodigo(i.codigo);
                      try { await api.eliminarImpuesto(i.codigo); qc.invalidateQueries({ queryKey: ["impuestos"] }); }
                      catch { /* ignore */ }
                      setDeletingCodigo(null);
                    }}
                    className="flex h-7 w-7 items-center justify-center rounded-lg transition-opacity hover:opacity-80 disabled:opacity-40"
                    style={{ color: "var(--error)" }}
                    title="Eliminar"
                  >
                    {deletingCodigo === i.codigo ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                  </button>
                </td>
              </tr>
            ))}
            {dt.rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                  Sin resultados para &ldquo;{dt.search}&rdquo;
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </DataTableShell>

      {/* Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Nuevo código de impuesto</DialogTitle>
            <DialogDescription>Completa los campos para agregar un nuevo código al catálogo.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Código SIIGO *</Label>
                <Input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="ej. IVA19" />
              </div>
              <div className="space-y-1.5">
                <Label>Tipo impuesto</Label>
                <Input value={tipo} onChange={(e) => setTipo(e.target.value)} placeholder="ej. IVA" />
              </div>
              <div className="space-y-1.5">
                <Label>Tarifa %</Label>
                <Input type="number" value={tarifa} onChange={(e) => setTarifa(e.target.value)} min="0" max="100" step="0.5" />
              </div>
              <div className="space-y-1.5">
                <Label>Nombre</Label>
                <Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="ej. IVA 19%" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Cuenta crédito / compras (PUC) *</Label>
              <Combobox
                options={cuentaOpts}
                value={cuentaCre}
                onChange={setCuentaCre}
                placeholder="Buscar por código o nombre..."
              />
            </div>
            {err && <ErrBanner msg={err} />}
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setModalOpen(false)}>Cancelar</Button>
              <Button onClick={handleAdd} disabled={saving}>{saving ? "Guardando..." : "Guardar impuesto"}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// -
// PLAN DE CUENTAS TAB
// -
function PlanCuentasTab({
  cuentasPago,
  cuentasGasto,
}: {
  cuentasPago: CuentaOpcion[];
  cuentasGasto: CuentaOpcion[];
}) {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [nombre, setNombre] = useState("");
  const [fiscal, setFiscal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const cuentas = useMemo(() => {
    const uniq = new Map<string, CuentaOpcion>();
    [...cuentasPago, ...cuentasGasto].forEach((c) => uniq.set(c.codigo, c));
    return [...uniq.values()].sort((a, b) => a.codigo.localeCompare(b.codigo));
  }, [cuentasPago, cuentasGasto]);

  const [filterTipoCuenta, setFilterTipoCuenta] = useState("all");
  const [deletingCodigo, setDeletingCodigo] = useState<string | null>(null);

  const cuentasFiltradas = useMemo(() => {
    if (filterTipoCuenta === "all") return cuentas;
    const esPago  = (c: CuentaOpcion) => cuentasPago.some((x) => x.codigo === c.codigo);
    const esGasto = (c: CuentaOpcion) => cuentasGasto.some((x) => x.codigo === c.codigo);
    if (filterTipoCuenta === "pago")  return cuentas.filter((c) => esPago(c) && !esGasto(c));
    if (filterTipoCuenta === "gasto") return cuentas.filter((c) => esGasto(c) && !esPago(c));
    if (filterTipoCuenta === "ambos") return cuentas.filter((c) => esPago(c) && esGasto(c));
    return cuentas;
  }, [cuentas, filterTipoCuenta, cuentasPago, cuentasGasto]);

  const dt = useDataTable(cuentasFiltradas, searchCuenta, {
    sortFns: {
      codigo: (a, b) => a.codigo.localeCompare(b.codigo),
      nombre: (a, b) => a.nombre.localeCompare(b.nombre),
    },
    defaultSort: { col: "codigo", dir: "asc" },
  });

  const handleAdd = async () => {
    if (!codigo.trim() || !nombre.trim()) {
      setErr("Código y nombre son obligatorios.");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      await api.crearCuenta({ codigo: codigo.trim(), nombre: nombre.trim(), fiscal });
      qc.invalidateQueries({ queryKey: ["cuentas-pago"] });
      qc.invalidateQueries({ queryKey: ["cuentas-gasto"] });
      setCodigo(""); setNombre(""); setFiscal(false);
      setModalOpen(false);
    } catch (e) {
      setErr((e as Error).message);
    }
    setSaving(false);
  };

  return (
    <>
      <UploadExcelPanel
        onUpload={api.cargarExcelCuentas}
        onPlantilla={api.descargarPlantillaCuentas}
        onLimpiar={api.limpiarCuentas}
        limpiarLabel="Limpiar plan de cuentas"
        onSuccess={() => {
          qc.invalidateQueries({ queryKey: ["cuentas-pago"] });
          qc.invalidateQueries({ queryKey: ["cuentas-gasto"] });
        }}
      />
      <DataTableShell
        title="Plan de Cuentas PUC"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        onAdd={() => { setErr(""); setModalOpen(true); }}
        addLabel="Agregar cuenta"
        searchPlaceholder="Buscar por código o nombre..."
        filters={
          <FilterChips
            label="Tipo"
            value={filterTipoCuenta}
            onChange={setFilterTipoCuenta}
            options={[
              { value: "all",   label: "Todas" },
              { value: "pago",  label: "Solo Pago" },
              { value: "gasto", label: "Solo Gasto" },
              { value: "ambos", label: "Pago y Gasto" },
            ]}
          />
        }
      >
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <SortableTh label="Código" col="codigo" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <SortableTh label="Nombre" col="nombre" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Tipo</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {dt.rows.map((c, idx) => {
              const esPago = cuentasPago.some((x) => x.codigo === c.codigo);
              const esGasto = cuentasGasto.some((x) => x.codigo === c.codigo);
              return (
                <tr
                  key={c.codigo}
                  className="tr-row"
                  style={{ borderBottom: idx < dt.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                >
                  <td className="px-4 py-2.5 font-mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                    {c.codigo}
                  </td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{c.nombre}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-2">
                      {esPago && <Badge variant="info">Pago</Badge>}
                      {esGasto && <Badge variant="success">Gasto / Costo</Badge>}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      type="button"
                      disabled={deletingCodigo === c.codigo}
                      onClick={async () => {
                        setDeletingCodigo(c.codigo);
                        try {
                          await api.eliminarCuenta(c.codigo);
                          qc.invalidateQueries({ queryKey: ["cuentas-pago"] });
                          qc.invalidateQueries({ queryKey: ["cuentas-gasto"] });
                        } catch { /* ignore */ }
                        setDeletingCodigo(null);
                      }}
                      className="flex h-7 w-7 items-center justify-center rounded-lg transition-opacity hover:opacity-80 disabled:opacity-40"
                      style={{ color: "var(--error)" }}
                      title="Eliminar"
                    >
                      {deletingCodigo === c.codigo ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    </button>
                  </td>
                </tr>
              );
            })}
            {dt.rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                  Sin resultados para &ldquo;{dt.search}&rdquo;
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </DataTableShell>

      {/* Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Nueva cuenta PUC</DialogTitle>
            <DialogDescription>Agrega una cuenta al plan de cuentas contable.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label>Código PUC *</Label>
              <Input
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                placeholder="ej. 51050505"
                maxLength={10}
              />
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Máximo 10 caracteres, sin puntos ni espacios.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>Nombre / Descripción *</Label>
              <Input
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="ej. Honorarios servicios profesionales"
                maxLength={255}
              />
            </div>
            <label className="flex cursor-pointer items-center gap-2.5">
              <input
                type="checkbox"
                checked={fiscal}
                onChange={(e) => setFiscal(e.target.checked)}
                className="h-4 w-4 rounded border"
                style={{ accentColor: "var(--brand)" }}
              />
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Cuenta fiscal
              </span>
            </label>
            {err && <ErrBanner msg={err} />}
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setModalOpen(false)}>Cancelar</Button>
              <Button onClick={handleAdd} disabled={saving}>{saving ? "Guardando..." : "Guardar cuenta"}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// -
// TIPOS DE COMPROBANTE TAB
// -
function TiposTab({ tipos }: { tipos: TipoComprobanteOpcion[] }) {
  const qc = useQueryClient();
  const [deletingCodigo, setDeletingCodigo] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [titulo, setTitulo] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const dt = useDataTable(tipos, searchTipo, {
    sortFns: {
      codigo: (a, b) => a.codigo.localeCompare(b.codigo),
      titulo: (a, b) => a.titulo.localeCompare(b.titulo),
    },
    defaultSort: { col: "codigo", dir: "asc" },
  });

  const handleAdd = async () => {
    if (!codigo.trim() || !titulo.trim()) {
      setErr("Código y título son obligatorios.");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      await api.crearTipoComprobante({ codigo: codigo.trim(), titulo: titulo.trim() });
      qc.invalidateQueries({ queryKey: ["tipos-comp"] });
      setCodigo(""); setTitulo("");
      setModalOpen(false);
    } catch (e) {
      setErr((e as Error).message);
    }
    setSaving(false);
  };

  return (
    <>
      <UploadExcelPanel
        onUpload={api.cargarExcelTipos}
        onPlantilla={api.descargarPlantillaTipos}
        onLimpiar={api.limpiarTipos}
        limpiarLabel="Limpiar comprobantes"
        onSuccess={() => qc.invalidateQueries({ queryKey: ["tipos-comp"] })}
      />
      <DataTableShell
        title="Tipos de Comprobante"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        onAdd={() => { setErr(""); setModalOpen(true); }}
        addLabel="Agregar tipo"
        searchPlaceholder="Buscar por código o título..."
      >
        <table className="w-full min-w-[400px] text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <SortableTh label="Código" col="codigo" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <SortableTh label="Título" col="titulo" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <th />
            </tr>
          </thead>
          <tbody>
            {dt.rows.map((t, idx) => (
              <tr
                key={t.codigo}
                className="tr-row"
                style={{ borderBottom: idx < dt.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}
              >
                <td className="px-4 py-2.5 font-mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{t.codigo}</td>
                <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{t.titulo}</td>
                <td className="px-4 py-2.5">
                  <button
                    type="button"
                    disabled={deletingCodigo === t.codigo}
                    onClick={async () => {
                      setDeletingCodigo(t.codigo);
                      try { await api.eliminarTipo(t.codigo); qc.invalidateQueries({ queryKey: ["tipos-comp"] }); }
                      catch { /* ignore */ }
                      setDeletingCodigo(null);
                    }}
                    className="flex h-7 w-7 items-center justify-center rounded-lg transition-opacity hover:opacity-80 disabled:opacity-40"
                    style={{ color: "var(--error)" }}
                    title="Eliminar"
                  >
                    {deletingCodigo === t.codigo ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                  </button>
                </td>
              </tr>
            ))}
            {dt.rows.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                  Sin resultados para &ldquo;{dt.search}&rdquo;
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </DataTableShell>

      {/* Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Nuevo tipo de comprobante</DialogTitle>
            <DialogDescription>Agrega un nuevo tipo de comprobante contable al catálogo.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label>Código SIIGO *</Label>
              <Input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="ej. 12" />
            </div>
            <div className="space-y-1.5">
              <Label>Título *</Label>
              <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="ej. Ajustes contables" />
            </div>
            {err && <ErrBanner msg={err} />}
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setModalOpen(false)}>Cancelar</Button>
              <Button onClick={handleAdd} disabled={saving}>{saving ? "Guardando..." : "Guardar tipo"}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// -
// CONTROL IA TAB
// -
function ControlIATab() {
  const { data: historial = [] } = useQuery({
    queryKey: ["ia-historial"],
    queryFn: () => api.getIAHistorial(200),
  });
  const { data: reglas = [] } = useQuery({
    queryKey: ["ia-reglas"],
    queryFn: api.getIAReglas,
  });

  const dtReglas = useDataTable(reglas, searchRegla);
  const dtHistorial = useDataTable(historial as IADecision[], searchDecision);

  const corrections = historial.filter((h) => h.fue_corregida).length;
  const accuracy =
    historial.length > 0
      ? Math.round(((historial.length - corrections) / historial.length) * 100)
      : 0;

  return (
    <div className="space-y-4">
      {/* IA KPIs */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Reglas activas" value={reglas.filter((r) => r.activa).length} color="var(--brand)" />
        <StatCard label="Decisiones registradas" value={historial.length} color="var(--info)" />
        <StatCard
          label="Precisión estimada"
          value={`${accuracy}%`}
          color={accuracy >= 80 ? "var(--success)" : "var(--warning)"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Reglas */}
        <DataTableShell
          title="Reglas de clasificación"
          total={dtReglas.total}
          totalFiltered={dtReglas.totalFiltered}
          search={dtReglas.search}
          onSearch={dtReglas.onSearch}
          page={dtReglas.page}
          pageSize={dtReglas.pageSize}
          totalPages={dtReglas.totalPages}
          onPage={dtReglas.onPage}
          onPageSize={dtReglas.onPageSize}
          searchPlaceholder="Buscar patrón o cuenta..."
        >
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                {["Prioridad", "Patrón", "Cuenta PUC", "Estado"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dtReglas.rows.map((r, idx) => (
                <tr
                  key={r.id}
                  className="tr-row"
                  style={{ borderBottom: idx < dtReglas.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                >
                  <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>{r.prioridad}</td>
                  <td className="max-w-[180px] truncate px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{r.patron}</td>
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: "var(--text-muted)" }}>{r.cuenta_puc}</td>
                  <td className="px-4 py-2.5">
                    {r.activa ? <Badge variant="success">Activa</Badge> : <Badge>Inactiva</Badge>}
                  </td>
                </tr>
              ))}
              {dtReglas.rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin resultados</td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTableShell>

        {/* Historial */}
        <DataTableShell
          title="Historial de decisiones"
          total={dtHistorial.total}
          totalFiltered={dtHistorial.totalFiltered}
          search={dtHistorial.search}
          onSearch={dtHistorial.onSearch}
          page={dtHistorial.page}
          pageSize={dtHistorial.pageSize}
          totalPages={dtHistorial.totalPages}
          onPage={dtHistorial.onPage}
          onPageSize={dtHistorial.onPageSize}
          searchPlaceholder="Buscar NIT, descripción o cuenta..."
        >
          <table className="w-full min-w-[600px] text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
                {["Fecha", "NIT", "Descripción", "Cuenta", "Corregida"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dtHistorial.rows.map((h, idx) => (
                <tr
                  key={h.id}
                  className="tr-row"
                  style={{ borderBottom: idx < dtHistorial.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                >
                  <td className="whitespace-nowrap px-4 py-2.5 tabular-nums text-xs" style={{ color: "var(--text-muted)" }}>
                    {h.created_at?.slice(0, 10)}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                    {h.nit_proveedor || "-"}
                  </td>
                  <td className="max-w-[200px] truncate px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>
                    {h.descripcion_item || "-"}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                    {h.cuenta_aplicada || "-"}
                  </td>
                  <td className="px-4 py-2.5">
                    {h.fue_corregida ? <Badge variant="warning">Sí</Badge> : <Badge variant="success">No</Badge>}
                  </td>
                </tr>
              ))}
              {dtHistorial.rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin resultados</td>
                </tr>
              )}
            </tbody>
          </table>
        </DataTableShell>
      </div>
    </div>
  );
}
