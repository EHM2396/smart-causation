"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DataTableShell, useDataTable } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Download, RefreshCw, Calendar, X, Trash2, AlertTriangle, PackageOpen } from "lucide-react";
import { fmt } from "@/lib/utils";
import type { HistorialItem } from "@/lib/types";

// ─── Search function ─────────────────────────────────────────────────────────

const searchFn = (h: HistorialItem, q: string) =>
  (h.numero_dian ?? "").toLowerCase().includes(q) ||
  (h.nit_proveedor ?? "").toLowerCase().includes(q) ||
  (h.razon_social ?? "").toLowerCase().includes(q) ||
  (h.consecutivo ?? "").toLowerCase().includes(q) ||
  (h.tipo_comprobante ?? "").toLowerCase().includes(q);

// ─── Date input component ─────────────────────────────────────────────────────

function DateInput({
  label,
  value,
  onChange,
  max,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  max?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
        {label}
      </label>
      <input
        type="date"
        value={value}
        max={max}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 rounded-lg border px-2 text-xs focus:outline-none focus:ring-2"
        style={{
          borderColor: value ? "var(--brand)" : "var(--border-soft)",
          backgroundColor: "var(--bg-surface)",
          color: "var(--text-primary)",
          colorScheme: "inherit",
        }}
      />
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const TODAY = new Date().toISOString().slice(0, 10);

export default function HistorialPage() {
  const [fechaDesde, setFechaDesde] = useState(TODAY);
  const [fechaHasta, setFechaHasta] = useState(TODAY);
  const [regenerating, setRegenerating] = useState<number | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exportingLote, setExportingLote] = useState(false);

  const hasDateFilter = fechaDesde !== TODAY || fechaHasta !== TODAY;
  const queryClient = useQueryClient();

  const { data: historial = [], isLoading, refetch } = useQuery({
    queryKey: ["historial-causaciones", fechaDesde, fechaHasta],
    queryFn: () => api.getHistorial({ fechaDesde, fechaHasta }),
    staleTime: 30_000,
  });

  const dt = useDataTable(historial, searchFn);

  const totalImporte = historial.reduce((s, r) => s + (r.total ?? 0), 0);
  const conDatos = historial.filter((r) => r.tiene_datos).length;
  const rangoLabel =
    fechaDesde === fechaHasta
      ? fechaDesde
      : `${fechaDesde} → ${fechaHasta}`;

  const handleExportarLote = async () => {
    setExportingLote(true);
    try {
      const blob = await api.exportarLoteHistorial({ fechaDesde, fechaHasta });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `SIIGO_lote_${fechaDesde}_${fechaHasta}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert((e as Error).message);
    }
    setExportingLote(false);
  };

  const handleEliminar = async () => {
    setDeleting(true);
    try {
      await api.limpiarHistorial({ fechaDesde, fechaHasta });
      setShowDeleteDialog(false);
      queryClient.invalidateQueries({ queryKey: ["historial-causaciones"] });
    } catch (e) {
      alert((e as Error).message);
    }
    setDeleting(false);
  };

  const clearFiltros = () => {
    setFechaDesde(TODAY);
    setFechaHasta(TODAY);
  };

  const handleRegenerar = async (row: HistorialItem) => {
    setRegenerating(row.id);
    try {
      const blob = await api.regenerarHistorial(row.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `regenerado_SIIGO_${row.numero_dian}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert((e as Error).message);
    }
    setRegenerating(null);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      {/* Confirm delete dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" style={{ color: "var(--error-text)" }} />
              ¿Eliminar registros?
            </DialogTitle>
          </DialogHeader>

          <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
            Esta acción es <strong>irreversible</strong>. Se eliminarán permanentemente los siguientes registros:
          </p>

          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="rounded-lg p-3 text-center" style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)" }}>
              <p className="text-2xl font-bold" style={{ color: "var(--error-text)" }}>{historial.length}</p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>facturas</p>
            </div>
            <div className="rounded-lg p-3 text-center col-span-2" style={{ backgroundColor: "var(--bg-elevated)", border: "1px solid var(--border-soft)" }}>
              <p className="text-sm font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmt(totalImporte)}</p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>total causado</p>
            </div>
          </div>

          <div className="rounded-lg px-3 py-2 mb-6 text-xs" style={{ backgroundColor: "var(--bg-elevated)", border: "1px solid var(--border-soft)" }}>
            <span style={{ color: "var(--text-muted)" }}>Período: </span>
            <span className="font-mono font-medium" style={{ color: "var(--text-primary)" }}>{rangoLabel}</span>
          </div>

          <div className="flex justify-end gap-3">
            <button
              onClick={() => setShowDeleteDialog(false)}
              disabled={deleting}
              className="rounded-lg border px-4 py-2 text-sm transition-colors hover:opacity-80"
              style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-surface)" }}
            >
              Cancelar
            </button>
            <button
              onClick={handleEliminar}
              disabled={deleting}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors hover:opacity-90 disabled:opacity-60"
              style={{ backgroundColor: "var(--error-text)", color: "#fff" }}
            >
              {deleting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              {deleting ? "Eliminando..." : `Sí, eliminar ${historial.length} registro${historial.length !== 1 ? "s" : ""}`}
            </button>
          </div>
        </DialogContent>
      </Dialog>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Historial de causaciones
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Todas las facturas confirmadas. Filtrá por fecha y regenerá el archivo SIIGO cuando lo necesites.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {historial.length > 0 && (
            <button
              onClick={() => setShowDeleteDialog(true)}
              className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors hover:opacity-80"
              style={{ borderColor: "var(--error-border)", color: "var(--error-text)", backgroundColor: "var(--error-bg)" }}
            >
              <Trash2 className="h-3.5 w-3.5" />
              Limpiar historial
            </button>
          )}
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors hover:opacity-80"
            style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)", backgroundColor: "var(--bg-surface)" }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Actualizar
          </button>
        </div>
      </div>

      {/* Date range filter bar */}
      <div
        className="flex flex-wrap items-end gap-4 rounded-xl border px-4 py-3"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-card)" }}
      >
        <Calendar className="h-4 w-4 shrink-0 self-end mb-1.5" style={{ color: "var(--text-muted)" }} />
        <DateInput label="Desde" value={fechaDesde} onChange={setFechaDesde} max={fechaHasta || undefined} />
        <DateInput label="Hasta" value={fechaHasta} onChange={setFechaHasta} max={new Date().toISOString().slice(0, 10)} />

        {/* Spacer */}
        <div className="flex-1" />

        {/* Download all button */}
        {historial.length > 0 && (
          <div className="self-end flex flex-col items-end gap-0.5 mb-0.5">
            <button
              onClick={handleExportarLote}
              disabled={exportingLote || conDatos === 0}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: conDatos > 0 ? "var(--brand-btn)" : "var(--bg-elevated)", color: conDatos > 0 ? "#fff" : "var(--text-muted)", border: conDatos === 0 ? "1px solid var(--border-soft)" : "none" }}
              title={conDatos === 0 ? "Ningún registro del período tiene datos exportables" : `Descargar ${conDatos} factura${conDatos !== 1 ? "s" : ""} como un único archivo SIIGO`}
            >
              {exportingLote ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <PackageOpen className="h-3.5 w-3.5" />}
              {exportingLote ? "Generando..." : `Descargar SIIGO${conDatos < historial.length ? ` (${conDatos}/${historial.length})` : ` (${conDatos})`}`}
            </button>
            {conDatos < historial.length && conDatos > 0 && (
              <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                {historial.length - conDatos} sin datos exportables
              </span>
            )}
          </div>
        )}

        {hasDateFilter && (
          <button
            onClick={clearFiltros}
            className="flex items-center gap-1 self-end mb-1 rounded-lg px-2.5 py-1 text-xs transition-colors hover:opacity-80"
            style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border-soft)" }}
          >
            <X className="h-3 w-3" /> Volver a hoy
          </button>
        )}
      </div>

      {/* Table */}
      <DataTableShell
        title="Facturas causadas"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        searchPlaceholder="Buscar por N° DIAN, NIT, proveedor o consecutivo..."
      >
        <table className="w-full min-w-[900px] text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              {["Consec.", "N° Factura DIAN", "Proveedor", "F. Factura", "F. Causación", "Total", "Tipo comp.", "Archivo origen", "Acciones"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--text-muted)" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                  Cargando historial...
                </td>
              </tr>
            ) : dt.rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                  {hasDateFilter ? "Sin resultados para el rango de fechas seleccionado." : "No hay facturas causadas aún."}
                </td>
              </tr>
            ) : (
              dt.rows.map((row, idx) => (
                <tr
                  key={row.id}
                  className="tr-row"
                  style={{ borderBottom: idx < dt.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}
                >
                  {/* Consecutivo */}
                  <td className="px-4 py-3 font-mono text-xs font-semibold" style={{ color: "var(--brand)" }}>
                    {row.consecutivo ?? "-"}
                  </td>

                  {/* N° DIAN */}
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-primary)" }}>
                    {row.numero_dian}
                  </td>

                  {/* Proveedor */}
                  <td className="px-4 py-3 max-w-[200px]">
                    <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }} title={row.razon_social ?? ""}>
                      {row.razon_social ?? "-"}
                    </p>
                    <p className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                      {row.nit_proveedor ?? ""}
                    </p>
                  </td>

                  {/* Fecha factura */}
                  <td className="px-4 py-3 text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {row.fecha_factura ?? "-"}
                  </td>

                  {/* Fecha causación */}
                  <td className="px-4 py-3 text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {row.fecha_causacion ?? "-"}
                  </td>

                  {/* Total */}
                  <td className="px-4 py-3 text-right font-mono text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    {fmt(row.total)}
                  </td>

                  {/* Tipo comprobante */}
                  <td className="px-4 py-3">
                    {row.tipo_comprobante ? (
                      <Badge variant="info">{row.tipo_comprobante}</Badge>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>-</span>
                    )}
                  </td>

                  {/* Archivo origen */}
                  <td className="px-4 py-3 max-w-[140px]">
                    <span className="truncate text-xs block" style={{ color: "var(--text-muted)" }} title={row.archivo_origen ?? ""}>
                      {row.archivo_origen ?? "-"}
                    </span>
                  </td>

                  {/* Acciones */}
                  <td className="px-4 py-3">
                    {row.tiene_datos ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={regenerating === row.id}
                        onClick={() => handleRegenerar(row)}
                        className="flex items-center gap-1.5 text-xs"
                      >
                        {regenerating === row.id ? (
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Download className="h-3.5 w-3.5" />
                        )}
                        {regenerating === row.id ? "Generando..." : "Descargar"}
                      </Button>
                    ) : (
                      <span
                        className="cursor-help text-xs underline decoration-dotted"
                        style={{ color: "var(--text-muted)" }}
                        title="Esta factura fue causada antes de que el sistema almacenara datos de regeneraci\u00f3n. Solo facturas causadas desde esta versi\u00f3n pueden descargarse nuevamente."
                      >
                        No disponible
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </DataTableShell>
    </div>
  );
}
