"use client";
/**
 * Clasificación tributaria de operaciones a tarifa 0%, para armar el
 * Formulario 300 más adelante.
 *
 * Principio de la pantalla, confirmado con el analista de impuestos:
 * "resumen primero, detalle bajo demanda". El eje es el PROVEEDOR —el NIT
 * predice el tratamiento mejor que el texto de la descripción, un mismo
 * proveedor de maquinaria factura acarreos gravados aunque diga
 * "transporte"— y dentro de cada uno se ve primero el concepto de mayor peso
 * económico, con los secundarios disponibles pero sin invadir la pantalla.
 *
 * Solo para el administrador de la cuenta por ahora (lo exige el backend):
 * es donde se toman decisiones de clasificación que se comparten con toda la
 * firma, y conviene que pase por quien lleva impuestos antes de abrirlo a
 * todos los causadores.
 */
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Building2, CalendarDays, Check, ChevronDown, Loader2,
  Pencil, ScrollText, TriangleAlert,
} from "lucide-react";

import { api } from "@/lib/api";
import { fmt } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { DatePicker } from "@/components/ui/date-picker";
import type { ConceptoF300, ProveedorF300, TratamientoIVA } from "@/lib/types";
import { TRATAMIENTO_LABEL } from "@/lib/types";

const OPCIONES_TRATAMIENTO: TratamientoIVA[] = [
  "exento", "excluido", "no_gravado", "gravado_general", "gravado_5",
];

function localYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
// Los periodos que de verdad existen para el IVA (Art. 600 ET): bimestral o
// cuatrimestral según el responsable. Para cualquier otro rango están los
// selectores de fecha, al lado.
function buildPresets() {
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth();
  const inicioBimestre = Math.floor(m / 2) * 2;
  const inicioCuatrimestre = Math.floor(m / 4) * 4;
  return [
    { id: "mes", label: "Este mes", desde: localYMD(new Date(y, m, 1)), hasta: localYMD(now) },
    { id: "bimestre", label: "Bimestral", desde: localYMD(new Date(y, inicioBimestre, 1)), hasta: localYMD(now) },
    { id: "cuatrimestre", label: "Cuatrimestral", desde: localYMD(new Date(y, inicioCuatrimestre, 1)), hasta: localYMD(now) },
  ];
}

function badgeEstado(estado: ConceptoF300["estado"]) {
  switch (estado) {
    case "validada": return <Badge variant="success">Validada</Badge>;
    case "sugerida": return <Badge variant="info">Sugerida</Badge>;
    case "manual": return <Badge variant="purple">Manual</Badge>;
    default: return <Badge variant="warning">Pendiente</Badge>;
  }
}

function ConceptoRow({
  c, empresaId, onValidado,
}: { c: ConceptoF300; empresaId: number; onValidado: () => void }) {
  const [editando, setEditando] = useState(false);
  const [soloEsteProveedor, setSoloEsteProveedor] = useState(true);
  const [guardando, setGuardando] = useState<TratamientoIVA | null>(null);
  const [error, setError] = useState<string | null>(null);

  const validar = async (tratamiento: TratamientoIVA) => {
    setGuardando(tratamiento);
    setError(null);
    try {
      await api.f300Clasificar({
        empresa_id: empresaId,
        concepto: c.concepto,
        tratamiento,
        nit_tercero: soloEsteProveedor ? c.nit_proveedor : null,
      });
      setEditando(false);
      onValidado();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar la clasificación.");
    } finally {
      setGuardando(null);
    }
  };

  return (
    <div className="rounded-lg border px-3 py-2.5" style={{ borderColor: "var(--border-soft)" }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.concepto}</p>
          <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {fmt(c.base_acumulada)} · {c.documentos} documento(s) · {c.participacion}% del proveedor
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {c.tratamiento && (
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              {TRATAMIENTO_LABEL[c.tratamiento]}
            </span>
          )}
          {badgeEstado(c.estado)}
          {c.es_excepcion && (
            <span title="Difiere de la clasificación general de la firma">
              <TriangleAlert className="h-3.5 w-3.5" style={{ color: "#d97706" }} />
            </span>
          )}
          <Button variant="outline" size="sm" onClick={() => setEditando((v) => !v)} className="gap-1.5">
            <Pencil className="h-3.5 w-3.5" /> {c.estado === "validada" ? "Cambiar" : "Clasificar"}
          </Button>
        </div>
      </div>

      {editando && (
        <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border-soft)" }}>
          <div className="flex flex-wrap gap-2">
            {OPCIONES_TRATAMIENTO.map((t) => (
              <button key={t} type="button" onClick={() => validar(t)} disabled={guardando !== null}
                className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
                style={{
                  backgroundColor: c.tratamiento === t ? "var(--brand)" : "var(--bg-elevated)",
                  color: c.tratamiento === t ? "#fff" : "var(--text-secondary)",
                  border: `1px solid ${c.tratamiento === t ? "var(--brand)" : "var(--border-soft)"}`,
                }}>
                {guardando === t ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                {TRATAMIENTO_LABEL[t]}
              </button>
            ))}
          </div>
          <label className="mt-2.5 flex items-center gap-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            <input type="checkbox" checked={soloEsteProveedor} onChange={(e) => setSoloEsteProveedor(e.target.checked)} />
            Solo para este proveedor (si lo destildás, se propone como regla general del concepto para toda la firma)
          </label>
          {error && (
            <p className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: "#dc2626" }}>
              <AlertTriangle className="h-3.5 w-3.5" /> {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ProveedorCard({
  p, empresaId, onValidado,
}: { p: ProveedorF300; empresaId: number; onValidado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-sm)" }}>
      <button type="button" onClick={() => setAbierto((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: "var(--brand-muted)" }}>
          <Building2 className="h-4 w-4" style={{ color: "var(--brand)" }} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{p.razon_social}</p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>NIT {p.nit} · {p.documentos} documento(s)</p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <div className="text-right">
            <p className="text-sm font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmt(p.base_total)}</p>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>a tarifa 0%</p>
          </div>
          {p.pendientes > 0 ? (
            <Badge variant="warning">{p.pendientes} pendiente{p.pendientes === 1 ? "" : "s"}</Badge>
          ) : (
            <Badge variant="success">Clasificado</Badge>
          )}
          <ChevronDown className="h-4 w-4 transition-transform" style={{ color: "var(--text-muted)", transform: abierto ? "rotate(180deg)" : "none" }} />
        </div>
      </button>

      {abierto && (
        <div className="space-y-2 border-t px-4 py-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Concepto predominante
          </p>
          <ConceptoRow c={p.predominante} empresaId={empresaId} onValidado={onValidado} />

          {p.secundarios.length > 0 && (
            <>
              <p className="pt-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                Otros conceptos ({p.secundarios.length})
              </p>
              {p.secundarios.map((c) => (
                <ConceptoRow key={c.concepto} c={c} empresaId={empresaId} onValidado={onValidado} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function Formulario300Page() {
  const presets = useMemo(buildPresets, []);
  const [desde, setDesde] = useState(presets[2].desde);
  const [hasta, setHasta] = useState(presets[2].hasta);
  const [empresaId, setEmpresaId] = useState<number | null>(null);
  const qc = useQueryClient();

  const presetActivo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id ?? "personalizado";

  const { data: empresas } = useQuery({ queryKey: ["admin-empresas"], queryFn: api.adminEmpresas });
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["f300-proveedores", desde, hasta, empresaId],
    queryFn: () => api.f300Proveedores(desde, hasta, empresaId, 0),
    enabled: empresaId != null,
  });

  const opcionesEmpresa = (empresas ?? []).filter((e) => e.activa).map((e) => ({ value: String(e.id), label: e.nombre }));
  const onValidado = () => { refetch(); qc.invalidateQueries({ queryKey: ["f300-proveedores"] }); };

  const totalPendientes = (data?.proveedores ?? []).reduce((s, p) => s + p.pendientes, 0);
  const totalProveedores = data?.proveedores.length ?? 0;

  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ backgroundColor: "var(--brand-muted)" }}>
          <ScrollText className="h-5 w-5" style={{ color: "var(--brand)" }} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Formulario 300</h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-secondary)" }}>
            Clasifica las operaciones a tarifa 0% por proveedor: exento, excluido, no gravado o gravado.
          </p>
        </div>
      </div>

      <div className="mb-6 rounded-xl border p-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <div className="mb-2 flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <CalendarDays className="h-4 w-4" style={{ color: "var(--brand)" }} /> Periodo
        </div>
        <div className="flex flex-wrap items-end gap-2">
          {presets.map((p) => {
            const active = presetActivo === p.id;
            return (
              <button key={p.id} type="button" onClick={() => { setDesde(p.desde); setHasta(p.hasta); }}
                className="rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors"
                style={{ backgroundColor: active ? "var(--brand)" : "var(--bg-elevated)", color: active ? "#fff" : "var(--text-secondary)", border: `1px solid ${active ? "var(--brand)" : "var(--border-soft)"}` }}>
                {p.label}
              </button>
            );
          })}
          <div className="ml-1 flex flex-wrap items-end gap-2">
            <DatePicker label="Desde" value={desde} onChange={setDesde} max={hasta} />
            <span className="pb-2 text-xs" style={{ color: "var(--text-muted)" }}>hasta</span>
            <DatePicker label="Hasta" value={hasta} onChange={setHasta} min={desde} />
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3" style={{ borderColor: "var(--border-soft)" }}>
          <Building2 className="h-4 w-4 shrink-0" style={{ color: "var(--brand)" }} />
          <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Empresa</span>
          <Combobox
            className="w-full sm:w-80"
            options={opcionesEmpresa}
            value={empresaId == null ? "" : String(empresaId)}
            onChange={(v) => setEmpresaId(v === "" ? null : Number(v))}
            placeholder="Elegí una empresa..."
          />
        </div>
      </div>

      {empresaId == null ? (
        <div className="rounded-xl border px-4 py-16 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <Building2 className="mx-auto mb-3 h-8 w-8" style={{ color: "var(--text-muted)" }} />
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Elegí una empresa</p>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
            La clasificación se hace empresa por empresa.
          </p>
        </div>
      ) : isLoading ? (
        <div className="py-20 text-center"><Loader2 className="mx-auto h-7 w-7 animate-spin" style={{ color: "var(--brand)" }} /></div>
      ) : totalProveedores === 0 ? (
        <div className="rounded-xl border px-4 py-16 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <Check className="mx-auto mb-3 h-8 w-8" style={{ color: "var(--text-muted)" }} />
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Sin operaciones a tarifa 0% en este periodo</p>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
            Si esperabas ver algo, confirmá que ya trajiste la información de la DIAN en Analítica para este periodo.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3 text-sm" style={{ color: "var(--text-secondary)" }}>
            <span><strong style={{ color: "var(--text-primary)" }}>{totalProveedores}</strong> proveedor(es)</span>
            <span>·</span>
            {totalPendientes > 0 ? (
              <span className="flex items-center gap-1" style={{ color: "#d97706" }}>
                <AlertTriangle className="h-3.5 w-3.5" /> {totalPendientes} concepto(s) por clasificar
              </span>
            ) : (
              <span className="flex items-center gap-1" style={{ color: "#059669" }}>
                <Check className="h-3.5 w-3.5" /> Todo clasificado
              </span>
            )}
          </div>
          <div className="space-y-3">
            {data?.proveedores.map((p) => (
              <ProveedorCard key={p.nit} p={p} empresaId={empresaId} onValidado={onValidado} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
