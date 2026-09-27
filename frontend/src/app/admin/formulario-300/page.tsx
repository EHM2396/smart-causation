"use client";
/**
 * Clasificación tributaria de operaciones a tarifa 0%, para armar el
 * Formulario 300 más adelante.
 *
 * Principio de la pantalla, confirmado con el analista de impuestos (Andrés):
 * "resumen primero, detalle bajo demanda". El eje es el PROVEEDOR —el NIT
 * predice el tratamiento mejor que el texto de la descripción, un mismo
 * proveedor de maquinaria factura acarreos gravados aunque diga
 * "transporte"— y dentro de cada uno se ve primero el concepto de mayor peso
 * económico, con los secundarios disponibles pero sin invadir la pantalla.
 *
 * Fase 1 del módulo de IVA (versión simplificada): dos flujos separados —
 * Ventas (exento y excluido SIEMPRE distintos) y Compras (exento+excluido+no
 * gravado se muestran agrupados, pero el detalle sigue guardado aparte por
 * dentro)— y clasificación de un clic: los botones de tratamiento están
 * siempre visibles en la fila, sin diálogo intermedio. Selección múltiple
 * para clasificar varios conceptos de una sola vez. Nunca "aplicar a todo el
 * proveedor": un mismo proveedor puede vender bienes y servicios con
 * tratamientos distintos.
 *
 * Fase 2: en Compras se confirma también si el IVA facturado es descontable.
 * El módulo sigue filtrando a tarifa 0%: los ítems gravados (5%/19%) ya
 * tienen tratamiento definido por su tarifa y no necesitan revisión manual —
 * el balance_iva() del backend los toma directamente usando la sugerencia
 * automática (gravado → descontable). Aquí solo aparece lo ambiguo: los
 * ítems al 0% que necesitan separarse en exento / excluido / no gravado.
 *
 * Solo para el administrador de la cuenta por ahora (lo exige el backend):
 * es donde se toman decisiones de clasificación que se comparten con toda la
 * firma, y conviene que pase por quien lleva impuestos antes de abrirlo a
 * todos los causadores.
 */
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Building2, CalendarDays, Check, ChevronDown, Download,
  FileSpreadsheet, Loader2, ReceiptText, ScrollText, ShoppingCart, TriangleAlert, X,
} from "lucide-react";

import { api } from "@/lib/api";
import { fmt, periodosIVA } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { DatePicker } from "@/components/ui/date-picker";
import type { CatReporte, ConceptoF300, IvaDescontable, OrigenF300, ProveedorF300, ReporteF300, TipoItem, TratamientoIVA } from "@/lib/types";
import { CAT_REPORTE_LABEL, IVA_DESCONTABLE_LABEL, TIPO_DOC_LABEL, TIPO_ITEM_LABEL, TRATAMIENTO_LABEL } from "@/lib/types";

// En ventas, cada tratamiento es su propio botón — exento y excluido nunca se
// confunden. En compras se agrupan visualmente exento+excluido+no gravado
// (así lo pide la presentación principal del Formulario 300), pero cada uno
// sigue siendo un botón propio: el detalle se conserva igual por dentro.
const OPCIONES_VENTAS: TratamientoIVA[] = [
  "gravado_5", "gravado_general", "exento", "excluido", "no_gravado",
];
const OPCIONES_COMPRAS_GRAVADO: TratamientoIVA[] = ["gravado_5", "gravado_general"];
const OPCIONES_COMPRAS_AGRUPADO: TratamientoIVA[] = ["exento", "excluido", "no_gravado"];

function claveConcepto(c: ConceptoF300): string {
  return `${c.nit_proveedor}::${c.concepto}`;
}

function badgeEstado(estado: ConceptoF300["estado"]) {
  switch (estado) {
    case "validada": return <Badge variant="success">Validada</Badge>;
    case "sugerida": return <Badge variant="info">Sugerida</Badge>;
    case "manual": return <Badge variant="purple">Manual</Badge>;
    default: return <Badge variant="warning">Pendiente</Badge>;
  }
}

function BotonTratamiento({
  t, activo, guardando, disabled, onClick,
}: { t: TratamientoIVA; activo: boolean; guardando: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
      style={{
        backgroundColor: activo ? "var(--brand)" : "var(--bg-elevated)",
        color: activo ? "#fff" : "var(--text-secondary)",
        border: `1px solid ${activo ? "var(--brand)" : "var(--border-soft)"}`,
      }}>
      {guardando ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
      {TRATAMIENTO_LABEL[t]}
    </button>
  );
}

function ConceptoRow({
  c, empresaId, origen, seleccionado, onToggleSeleccion, onValidado,
}: {
  c: ConceptoF300; empresaId: number; origen: OrigenF300;
  seleccionado: boolean; onToggleSeleccion: () => void; onValidado: () => void;
}) {
  const [soloEsteProveedor, setSoloEsteProveedor] = useState(true);
  const [guardando, setGuardando] = useState<TratamientoIVA | "tipo_item" | "iva_descontable" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clasificar = async (tratamiento: TratamientoIVA) => {
    setGuardando(tratamiento);
    setError(null);
    try {
      await api.f300Clasificar({
        empresa_id: empresaId,
        concepto: c.concepto,
        tratamiento,
        nit_tercero: soloEsteProveedor ? c.nit_proveedor : null,
        referencia: c.referencia,
      });
      onValidado();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar la clasificación.");
    } finally {
      setGuardando(null);
    }
  };

  const confirmarTipoItem = async (tipo: TipoItem) => {
    if (!c.tratamiento) return; // sin tratamiento todavía no hay nada que guardar
    setGuardando("tipo_item");
    setError(null);
    try {
      await api.f300Clasificar({
        empresa_id: empresaId,
        concepto: c.concepto,
        tratamiento: c.tratamiento,
        nit_tercero: soloEsteProveedor ? c.nit_proveedor : null,
        referencia: c.referencia,
        tipo_item: tipo,
      });
      onValidado();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el tipo de ítem.");
    } finally {
      setGuardando(null);
    }
  };

  const confirmarIvaDescontable = async (valor: IvaDescontable | null) => {
    if (!c.tratamiento) return; // sin tratamiento todavía no hay nada que guardar
    setGuardando("iva_descontable");
    setError(null);
    try {
      await api.f300Clasificar({
        empresa_id: empresaId,
        concepto: c.concepto,
        tratamiento: c.tratamiento,
        nit_tercero: soloEsteProveedor ? c.nit_proveedor : null,
        referencia: c.referencia,
        iva_descontable: valor,
      });
      onValidado();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el IVA descontable.");
    } finally {
      setGuardando(null);
    }
  };

  const opcionesPrincipales = origen === "ventas" ? OPCIONES_VENTAS : OPCIONES_COMPRAS_GRAVADO;

  return (
    <div className="rounded-lg border px-3 py-2.5" style={{ borderColor: seleccionado ? "var(--brand)" : "var(--border-soft)" }}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <input type="checkbox" checked={seleccionado} onChange={onToggleSeleccion}
            className="mt-0.5 h-3.5 w-3.5 shrink-0" title="Seleccionar para clasificar junto con otros" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.concepto}</p>
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
              {fmt(c.base_acumulada)} · {c.documentos} documento(s) · {c.participacion}% del proveedor
              {c.referencia && <> · ref. {c.referencia}</>}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {badgeEstado(c.estado)}
          {c.es_excepcion && (
            <span title="Difiere de la clasificación general de la firma">
              <TriangleAlert className="h-3.5 w-3.5" style={{ color: "#d97706" }} />
            </span>
          )}
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        {opcionesPrincipales.map((t) => (
          <BotonTratamiento key={t} t={t} activo={c.tratamiento === t}
            guardando={guardando === t} disabled={guardando !== null}
            onClick={() => clasificar(t)} />
        ))}
        {origen === "compras" && (
          <span className="ml-1 flex items-center gap-1.5 rounded-full border px-1.5 py-1"
            style={{ borderColor: "var(--border-soft)" }} title="Se agrupan en el Formulario 300, pero cada uno se guarda por separado">
            {OPCIONES_COMPRAS_AGRUPADO.map((t) => (
              <BotonTratamiento key={t} t={t} activo={c.tratamiento === t}
                guardando={guardando === t} disabled={guardando !== null}
                onClick={() => clasificar(t)} />
            ))}
          </span>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>Bien / servicio:</span>
        {(["bien", "servicio"] as TipoItem[]).map((tipo) => {
          const activo = c.tipo_item === tipo;
          return (
            <button key={tipo} type="button" onClick={() => confirmarTipoItem(tipo)}
              disabled={guardando !== null || !c.tratamiento}
              title={!c.tratamiento ? "Clasificá primero el tratamiento de IVA" : undefined}
              className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors disabled:opacity-50"
              style={{
                backgroundColor: activo ? "var(--brand-muted)" : "transparent",
                color: activo ? "var(--brand)" : "var(--text-muted)",
                border: `1px dashed ${activo ? "var(--brand)" : "var(--border-soft)"}`,
              }}>
              {guardando === "tipo_item" ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              {TIPO_ITEM_LABEL[tipo]}
            </button>
          );
        })}
        {c.tipo_item && !c.tipo_item_confirmado && (
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>(sugerido, sin confirmar)</span>
        )}
      </div>

      {origen === "compras" && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>IVA:</span>
          {(["descontable", "no_descontable"] as IvaDescontable[]).map((valor) => {
            const activo = c.iva_descontable === valor;
            return (
              <button key={valor} type="button" onClick={() => confirmarIvaDescontable(valor)}
                disabled={guardando !== null || !c.tratamiento}
                title={!c.tratamiento ? "Clasificá primero el tratamiento de IVA" : undefined}
                className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors disabled:opacity-50"
                style={{
                  backgroundColor: activo ? "var(--brand-muted)" : "transparent",
                  color: activo ? "var(--brand)" : "var(--text-muted)",
                  border: `1px dashed ${activo ? "var(--brand)" : "var(--border-soft)"}`,
                }}>
                {guardando === "iva_descontable" ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                {IVA_DESCONTABLE_LABEL[valor]}
              </button>
            );
          })}
          {c.iva_descontable && (
            <button type="button" onClick={() => confirmarIvaDescontable(null)}
              disabled={guardando !== null || !c.tratamiento}
              className="text-[11px] underline decoration-dotted" style={{ color: "var(--text-muted)" }}>
              volver a pendiente
            </button>
          )}
          {c.iva_descontable && !c.iva_descontable_confirmado && (
            <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>(sugerido, sin confirmar)</span>
          )}
        </div>
      )}

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
  );
}

function ProveedorCard({
  p, empresaId, origen, seleccionados, onToggleSeleccion, onValidado,
}: {
  p: ProveedorF300; empresaId: number; origen: OrigenF300;
  seleccionados: Set<string>; onToggleSeleccion: (c: ConceptoF300) => void; onValidado: () => void;
}) {
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
          {p.tipos_documento.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {p.tipos_documento.map((t) => (
                <span key={t} className="rounded px-1.5 py-0.5 text-[10px] font-medium"
                  style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border-soft)" }}>
                  {TIPO_DOC_LABEL[t] ?? t}
                </span>
              ))}
            </div>
          )}
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
          <ConceptoRow c={p.predominante} empresaId={empresaId} origen={origen} onValidado={onValidado}
            seleccionado={seleccionados.has(claveConcepto(p.predominante))}
            onToggleSeleccion={() => onToggleSeleccion(p.predominante)} />

          {p.secundarios.length > 0 && (
            <>
              <p className="pt-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                Otros conceptos ({p.secundarios.length})
              </p>
              {p.secundarios.map((c) => (
                <ConceptoRow key={c.concepto} c={c} empresaId={empresaId} origen={origen} onValidado={onValidado}
                  seleccionado={seleccionados.has(claveConcepto(c))}
                  onToggleSeleccion={() => onToggleSeleccion(c)} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Barra flotante para clasificar de una sola vez varios conceptos ya
 * seleccionados — nunca "todo el proveedor", solo lo que el contador marcó a
 * mano (conceptos iguales repetidos entre proveedores, por ejemplo). */
function BarraSeleccion({
  seleccion, origen, empresaId, onLimpiar, onAplicado,
}: {
  seleccion: ConceptoF300[]; origen: OrigenF300; empresaId: number;
  onLimpiar: () => void; onAplicado: () => void;
}) {
  const [aplicando, setAplicando] = useState<TratamientoIVA | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (seleccion.length === 0) return null;

  const opciones = origen === "ventas"
    ? OPCIONES_VENTAS
    : [...OPCIONES_COMPRAS_GRAVADO, ...OPCIONES_COMPRAS_AGRUPADO];

  const aplicar = async (tratamiento: TratamientoIVA) => {
    setAplicando(tratamiento);
    setError(null);
    try {
      await Promise.all(seleccion.map((c) => api.f300Clasificar({
        empresa_id: empresaId, concepto: c.concepto, tratamiento,
        nit_tercero: c.nit_proveedor, referencia: c.referencia,
      })));
      onAplicado();
      onLimpiar();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo aplicar a toda la selección.");
    } finally {
      setAplicando(null);
    }
  };

  return (
    <div className="sticky bottom-4 z-10 mx-auto mt-4 flex max-w-3xl flex-wrap items-center gap-2 rounded-xl border px-4 py-3 shadow-lg"
      style={{ borderColor: "var(--brand)", backgroundColor: "var(--bg-surface)" }}>
      <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
        {seleccion.length} concepto(s) seleccionado(s)
      </span>
      <div className="flex flex-wrap items-center gap-1.5">
        {opciones.map((t) => (
          <BotonTratamiento key={t} t={t} activo={false} guardando={aplicando === t}
            disabled={aplicando !== null} onClick={() => aplicar(t)} />
        ))}
      </div>
      {error && <span className="text-xs" style={{ color: "#dc2626" }}>{error}</span>}
      <button type="button" onClick={onLimpiar} disabled={aplicando !== null}
        className="ml-auto flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
        <X className="h-3.5 w-3.5" /> Limpiar
      </button>
    </div>
  );
}

const CATS_ORDEN: CatReporte[] = ["gravado_general", "gravado_5", "exento", "excluido", "no_gravado", "pendiente"];
const COLOR_IVA_GENERADO = "#10B981";
const COLOR_IVA_DESCONTABLE = "#F43F5E";
const COLOR_TRIBUTO = "#F59E0B";

function TributosAdicionalesSection({
  desde, hasta, empresaId,
}: { desde: string; hasta: string; empresaId: number | null }) {
  const [expandidos, setExpandidos] = useState<Record<string, boolean>>({});

  const { data, isLoading } = useQuery<import("@/lib/types").TributosAdicionalesResumen>({
    queryKey: ["f300-tributos", desde, hasta, empresaId],
    queryFn: () => api.f300TributosAdicionales(desde, hasta, empresaId),
    enabled: empresaId != null,
  });

  if (isLoading) return (
    <div className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)" }}>
      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cargando tributos adicionales…
    </div>
  );

  if (!data) return null;

  const tieneCompras = data.compras.length > 0;
  const tieneVentas = data.ventas.length > 0;
  if (!tieneCompras && !tieneVentas) return null;

  const toggle = (key: string) => setExpandidos((prev) => ({ ...prev, [key]: !prev[key] }));

  function TributoBloque({ tributos, total, lado }: {
    tributos: import("@/lib/types").TributoAdicional[];
    total: number;
    lado: "compras" | "ventas";
  }) {
    return (
      <div className="space-y-1">
        {tributos.map((t) => {
          const key = `${lado}-${t.cod_dian}`;
          const abierto = !!expandidos[key];
          return (
            <div key={key}>
              <button type="button" onClick={() => toggle(key)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-opacity-60"
                style={{ backgroundColor: abierto ? "var(--bg-elevated)" : "transparent" }}>
                <ChevronDown className="h-3.5 w-3.5 shrink-0 transition-transform"
                  style={{ color: "var(--text-muted)", transform: abierto ? "rotate(180deg)" : "rotate(-90deg)" }} />
                <span className="flex-1 text-sm" style={{ color: "var(--text-secondary)" }}>
                  {t.nombre}
                  {!t.conocido && (
                    <span className="ml-2 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700">
                      no parametrizado
                    </span>
                  )}
                </span>
                <span className="text-sm font-semibold tabular-nums" style={{ color: COLOR_TRIBUTO }}>
                  {fmt(t.valor_total)}
                </span>
              </button>

              {abierto && (
                <div className="ml-5 mt-0.5 overflow-hidden rounded-lg border"
                  style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
                  <table className="w-full">
                    <thead>
                      <tr className="text-xs" style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border-soft)" }}>
                        <th className="px-3 py-1.5 text-left font-medium">NIT</th>
                        <th className="px-3 py-1.5 text-left font-medium">Nombre</th>
                        <th className="px-3 py-1.5 text-right font-medium">Docs</th>
                        <th className="px-3 py-1.5 text-right font-medium">Valor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {t.por_proveedor.map((p, i) => (
                        <tr key={p.nit} className="border-t text-sm"
                          style={{ borderColor: "var(--border-soft)", backgroundColor: i % 2 === 0 ? "transparent" : "var(--bg-elevated)" }}>
                          <td className="px-3 py-1.5 font-mono text-xs" style={{ color: "var(--text-muted)" }}>{p.nit}</td>
                          <td className="px-3 py-1.5" style={{ color: "var(--text-secondary)" }}>{p.razon_social || "—"}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: "var(--text-muted)" }}>{p.documentos}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums font-medium" style={{ color: "var(--text-secondary)" }}>{fmt(p.valor)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
        <div className="flex items-center justify-between border-t px-3 pt-2"
          style={{ borderColor: "var(--border-soft)" }}>
          <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Total tributos adicionales
          </span>
          <span className="text-sm font-bold tabular-nums" style={{ color: COLOR_TRIBUTO }}>
            {fmt(total)}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
      <div className="flex items-center gap-2 px-4 py-3"
        style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border-soft)" }}>
        <AlertTriangle className="h-4 w-4 shrink-0" style={{ color: COLOR_TRIBUTO }} />
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Impuestos adicionales
        </span>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          INC · IBUA · ICUI · INPP · Bolsas · otros
        </span>
        {data.hay_no_parametrizados && (
          <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            hay tributos sin parametrizar
          </span>
        )}
      </div>
      <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
        {tieneCompras && (
          <div className="px-3 py-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide px-1" style={{ color: COLOR_IVA_DESCONTABLE }}>
              Compras
            </p>
            <TributoBloque tributos={data.compras} total={data.total_compras} lado="compras" />
          </div>
        )}
        {tieneVentas && (
          <div className="px-3 py-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide px-1" style={{ color: COLOR_IVA_GENERADO }}>
              Ventas
            </p>
            <TributoBloque tributos={data.ventas} total={data.total_ventas} lado="ventas" />
          </div>
        )}
      </div>
      <div className="px-4 py-2" style={{ backgroundColor: "var(--bg-elevated)", borderTop: "1px solid var(--border-soft)" }}>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Estos tributos están discriminados en los XML. Ciolix los muestra para que el contador determine su tratamiento: mayor valor del costo/gasto, impuesto recuperable u otro, según la norma aplicable.
        </p>
      </div>
    </div>
  );
}

function KpiCard({ label, valor, color, sub }: { label: string; valor: number; color: string; sub?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border p-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
      <p className="text-xs font-semibold uppercase tracking-wide" style={{ color }}>{label}</p>
      <p className="text-xl font-bold tabular-nums" style={{ color }}>{fmt(valor)}</p>
      {sub && <p className="text-xs" style={{ color: "var(--text-muted)" }}>{sub}</p>}
    </div>
  );
}

function ReporteTab({
  desde, hasta, empresaId,
}: { desde: string; hasta: string; empresaId: number | null }) {
  const [reporteKey, setReporteKey] = useState(0);
  const [descargando, setDescargando] = useState<"excel" | "pdf" | null>(null);
  const [errDescarga, setErrDescarga] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<ReporteF300>({
    queryKey: ["f300-reporte", desde, hasta, empresaId, reporteKey],
    queryFn: () => api.f300Reporte(desde, hasta, empresaId),
    enabled: empresaId != null && reporteKey > 0,
  });

  const descargar = async (formato: "excel" | "pdf") => {
    setDescargando(formato);
    setErrDescarga(null);
    try {
      await api.f300ReporteDescargar(formato, desde, hasta, empresaId);
    } catch (e) {
      setErrDescarga(e instanceof Error ? e.message : "No se pudo descargar el archivo.");
    } finally {
      setDescargando(null);
    }
  };

  if (empresaId == null) {
    return (
      <div className="rounded-xl border px-4 py-16 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <Building2 className="mx-auto mb-3 h-8 w-8" style={{ color: "var(--text-muted)" }} />
        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Elegí una empresa</p>
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>El reporte se genera por empresa.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Encabezado: periodo + botones de acción */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <div className="flex items-center gap-2">
          <CalendarDays className="h-4 w-4 shrink-0" style={{ color: "var(--brand)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {desde} — {hasta}
          </span>
          <span className="rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ backgroundColor: "var(--brand-muted)", color: "var(--brand)" }}>
            Formulario 300
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setReporteKey((k) => k + 1)} disabled={isLoading}
            className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
            style={{ backgroundColor: "var(--brand)", color: "#fff" }}>
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ScrollText className="h-3.5 w-3.5" />}
            {isLoading ? "Generando…" : "Generar"}
          </button>
          {data && (
            <>
              <button type="button" onClick={() => descargar("excel")} disabled={descargando !== null}
                className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
                style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-elevated)" }}>
                {descargando === "excel" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileSpreadsheet className="h-3.5 w-3.5" />}
                Excel
              </button>
              <button type="button" onClick={() => descargar("pdf")} disabled={descargando !== null}
                className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50"
                style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)", backgroundColor: "var(--bg-elevated)" }}>
                {descargando === "pdf" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                PDF
              </button>
            </>
          )}
          {errDescarga && <span className="text-xs" style={{ color: "#dc2626" }}>{errDescarga}</span>}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border px-4 py-3 text-sm"
          style={{ borderColor: "#fca5a5", backgroundColor: "#fef2f2", color: "#dc2626" }}>
          <AlertTriangle className="h-4 w-4 shrink-0" />
          No se pudo generar el reporte. Intentalo de nuevo.
        </div>
      )}

      {!data && !isLoading && !error && reporteKey === 0 && (
        <div className="rounded-xl border px-4 py-16 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <ScrollText className="mx-auto mb-3 h-8 w-8" style={{ color: "var(--text-muted)" }} />
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Hacé clic en "Generar"</p>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
            Consolida ventas y compras del periodo seleccionado con sus devoluciones netas.
          </p>
        </div>
      )}

      {data && (
        <>
          {data.conceptos_pendientes > 0 && (
            <div className="flex items-center gap-2 rounded-lg border px-4 py-3 text-sm"
              style={{ borderColor: "#fbbf24", backgroundColor: "#fffbeb", color: "#92400e" }}>
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {data.conceptos_pendientes} concepto(s) aún sin clasificar — las cifras de exento / excluido pueden estar incompletas.
            </div>
          )}

          {/* KPIs */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <KpiCard label="IVA Generado" valor={data.totales.iva_generado}
              color={COLOR_IVA_GENERADO} sub="ventas del periodo" />
            <KpiCard label="IVA Descontable" valor={data.totales.iva_descontable}
              color={COLOR_IVA_DESCONTABLE} sub="compras del periodo" />
            <KpiCard label="Balance Analítico de IVA" valor={data.totales.balance_analitico_iva}
              color="var(--brand)" sub="generado − descontable" />
          </div>

          {/* VENTAS */}
          <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
            <div className="flex items-center gap-2 px-4 py-3"
              style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border-soft)" }}>
              <ReceiptText className="h-4 w-4" style={{ color: COLOR_IVA_GENERADO }} />
              <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Ventas e ingresos</span>
            </div>
            <div className="overflow-x-auto px-4 py-3">
              <table className="w-full min-w-[420px]">
                <thead>
                  <tr className="border-b text-xs" style={{ color: "var(--text-muted)", borderColor: "var(--border-soft)" }}>
                    <th className="pb-2 text-left font-medium">Tratamiento</th>
                    <th className="pb-2 text-right font-medium">Base gravable</th>
                    <th className="pb-2 text-right font-medium">IVA generado</th>
                  </tr>
                </thead>
                <tbody>
                  {CATS_ORDEN.filter((cat) => data.ventas[cat].base !== 0 || data.ventas[cat].iva !== 0).map((cat) => (
                    <tr key={cat} className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                      <td className="py-2 pr-4 text-sm" style={{ color: "var(--text-secondary)" }}>{CAT_REPORTE_LABEL[cat]}</td>
                      <td className="py-2 text-right text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(data.ventas[cat].base)}</td>
                      <td className="py-2 text-right text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(data.ventas[cat].iva)}</td>
                    </tr>
                  ))}
                  {data.devoluciones.ventas.base > 0 && (
                    <tr className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                      <td className="py-2 pr-4 text-sm italic" style={{ color: COLOR_IVA_DESCONTABLE }}>
                        (−) Devoluciones en ventas
                      </td>
                      <td className="py-2 text-right text-sm tabular-nums italic" style={{ color: COLOR_IVA_DESCONTABLE }}>
                        −{fmt(data.devoluciones.ventas.base)}
                      </td>
                      <td className="py-2 text-right text-sm tabular-nums italic" style={{ color: COLOR_IVA_DESCONTABLE }}>
                        −{fmt(data.devoluciones.ventas.iva)}
                      </td>
                    </tr>
                  )}
                </tbody>
                <tfoot>
                  <tr>
                    <td className="pt-2.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>TOTAL NETO</td>
                    <td className="pt-2.5 text-right text-sm font-semibold tabular-nums" style={{ color: COLOR_IVA_GENERADO }}>
                      {fmt(CATS_ORDEN.reduce((s, c) => s + data.ventas[c].base, 0))}
                    </td>
                    <td className="pt-2.5 text-right text-sm font-semibold tabular-nums" style={{ color: COLOR_IVA_GENERADO }}>
                      {fmt(data.totales.iva_generado)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* COMPRAS */}
          <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
            <div className="flex items-center gap-2 px-4 py-3"
              style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border-soft)" }}>
              <ShoppingCart className="h-4 w-4" style={{ color: COLOR_IVA_DESCONTABLE }} />
              <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Compras y costos</span>
            </div>
            <div className="overflow-x-auto px-4 py-3">
              <table className="w-full min-w-[560px]">
                <thead>
                  <tr className="border-b text-xs" style={{ color: "var(--text-muted)", borderColor: "var(--border-soft)" }}>
                    <th className="pb-2 text-left font-medium">Tratamiento</th>
                    <th className="pb-2 text-right font-medium">Base</th>
                    <th className="pb-2 text-right font-medium">IVA facturado</th>
                    <th className="pb-2 text-right font-medium">IVA descontable</th>
                  </tr>
                </thead>
                <tbody>
                  {CATS_ORDEN.filter((cat) => data.compras[cat].base !== 0 || data.compras[cat].iva_facturado !== 0).map((cat) => (
                    <tr key={cat} className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                      <td className="py-2 pr-4 text-sm" style={{ color: "var(--text-secondary)" }}>{CAT_REPORTE_LABEL[cat]}</td>
                      <td className="py-2 text-right text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(data.compras[cat].base)}</td>
                      <td className="py-2 text-right text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(data.compras[cat].iva_facturado)}</td>
                      <td className="py-2 text-right text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(data.compras[cat].iva_descontable)}</td>
                    </tr>
                  ))}
                  {data.devoluciones.compras.base > 0 && (
                    <tr className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                      <td className="py-2 pr-4 text-sm italic" style={{ color: COLOR_IVA_DESCONTABLE }}>
                        (−) Devoluciones en compras
                      </td>
                      <td className="py-2 text-right text-sm tabular-nums italic" style={{ color: COLOR_IVA_DESCONTABLE }}>
                        −{fmt(data.devoluciones.compras.base)}
                      </td>
                      <td className="py-2 text-right text-sm tabular-nums italic" style={{ color: COLOR_IVA_DESCONTABLE }}>
                        −{fmt(data.devoluciones.compras.iva_facturado)}
                      </td>
                      <td className="py-2 text-right text-sm tabular-nums italic" style={{ color: COLOR_IVA_DESCONTABLE }}>
                        −{fmt(data.devoluciones.compras.iva_descontable)}
                      </td>
                    </tr>
                  )}
                </tbody>
                <tfoot>
                  <tr>
                    <td className="pt-2.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>TOTAL NETO</td>
                    <td className="pt-2.5 text-right text-sm font-semibold tabular-nums" style={{ color: COLOR_IVA_DESCONTABLE }}>
                      {fmt(CATS_ORDEN.reduce((s, c) => s + data.compras[c].base, 0))}
                    </td>
                    <td className="pt-2.5 text-right text-sm font-semibold tabular-nums" style={{ color: COLOR_IVA_DESCONTABLE }}>
                      {fmt(CATS_ORDEN.reduce((s, c) => s + data.compras[c].iva_facturado, 0))}
                    </td>
                    <td className="pt-2.5 text-right text-sm font-semibold tabular-nums" style={{ color: COLOR_IVA_DESCONTABLE }}>
                      {fmt(data.totales.iva_descontable)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* NOTA */}
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Balance analítico de IVA: <strong>{fmt(data.totales.balance_analitico_iva)}</strong> —
            este valor no equivale al saldo a pagar ni al saldo a favor. El Formulario 300 depende
            de otros conceptos de la liquidación que este análisis no cubre.
          </p>

          <TributosAdicionalesSection desde={desde} hasta={hasta} empresaId={empresaId} />
        </>
      )}
    </div>
  );
}

export default function Formulario300Page() {
  const presets = useMemo(periodosIVA, []);
  const [desde, setDesde] = useState(presets[2].desde);
  const [hasta, setHasta] = useState(presets[2].hasta);
  const [empresaId, setEmpresaId] = useState<number | null>(null);
  const [vista, setVista] = useState<"compras" | "ventas" | "reporte">("compras");
  const origen: OrigenF300 = vista === "reporte" ? "compras" : vista;
  const [seleccion, setSeleccion] = useState<Map<string, ConceptoF300>>(new Map());
  const qc = useQueryClient();

  const presetActivo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id ?? "personalizado";

  const { data: empresas } = useQuery({ queryKey: ["admin-empresas"], queryFn: api.adminEmpresas });
  // Ambos flujos (Compras y Ventas) filtran a tarifa 0%: son los únicos ítems
  // que necesitan revisión manual (exento / excluido / no gravado). Los ítems
  // gravados (5%/19%) ya tienen tratamiento definido por su tarifa; el balance
  // de IVA los toma directamente con la sugerencia automática del backend.
  const todasTarifas = false;
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["f300-proveedores", desde, hasta, empresaId, origen],
    queryFn: () => api.f300Proveedores(desde, hasta, empresaId, 0, origen, todasTarifas),
    enabled: empresaId != null && vista !== "reporte",
  });

  const opcionesEmpresa = (empresas ?? []).filter((e) => e.activa).map((e) => ({ value: String(e.id), label: e.nombre }));
  const onValidado = () => { refetch(); qc.invalidateQueries({ queryKey: ["f300-proveedores"] }); };

  const cambiarVista = (v: "compras" | "ventas" | "reporte") => {
    setVista(v);
    if (v !== "reporte") setSeleccion(new Map());
  };

  const toggleSeleccion = (c: ConceptoF300) => {
    setSeleccion((prev) => {
      const next = new Map(prev);
      const clave = claveConcepto(c);
      if (next.has(clave)) next.delete(clave); else next.set(clave, c);
      return next;
    });
  };

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
            Clasifica las operaciones por proveedor —exento, excluido, no gravado o gravado— y, en compras, si el IVA es descontable.
          </p>
        </div>
      </div>

      <div className="mb-4 flex gap-1 rounded-xl border p-1" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", width: "fit-content" }}>
        <button type="button" onClick={() => cambiarVista("compras")}
          className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors"
          style={{ backgroundColor: vista === "compras" ? "var(--brand)" : "transparent", color: vista === "compras" ? "#fff" : "var(--text-secondary)" }}>
          <ShoppingCart className="h-3.5 w-3.5" /> Compras
        </button>
        <button type="button" onClick={() => cambiarVista("ventas")}
          className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors"
          style={{ backgroundColor: vista === "ventas" ? "var(--brand)" : "transparent", color: vista === "ventas" ? "#fff" : "var(--text-secondary)" }}>
          <ReceiptText className="h-3.5 w-3.5" /> Ventas
        </button>
        <button type="button" onClick={() => cambiarVista("reporte")}
          className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors"
          style={{ backgroundColor: vista === "reporte" ? "var(--brand)" : "transparent", color: vista === "reporte" ? "#fff" : "var(--text-secondary)" }}>
          <ScrollText className="h-3.5 w-3.5" /> Reporte
        </button>
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

      {vista === "reporte" ? (
        <ReporteTab desde={desde} hasta={hasta} empresaId={empresaId} />
      ) : empresaId == null ? (
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
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            Sin operaciones de {origen} en este periodo
          </p>
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
              <ProveedorCard key={p.nit} p={p} empresaId={empresaId} origen={origen} onValidado={onValidado}
                seleccionados={new Set(seleccion.keys())} onToggleSeleccion={toggleSeleccion} />
            ))}
          </div>
          <BarraSeleccion seleccion={[...seleccion.values()]} origen={origen} empresaId={empresaId}
            onLimpiar={() => setSeleccion(new Map())} onAplicado={onValidado} />
        </>
      )}
    </div>
  );
}
