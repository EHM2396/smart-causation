"use client";
/**
 * Panel de analítica: cómo van los costos, gastos e ingresos según los
 * documentos electrónicos que la DIAN reporta para la empresa.
 *
 * La fuente es lo que trae el token, NO lo que se alcanzó a causar: un informe
 * tiene que reflejar lo que pasó, no lo que se registró.
 *
 * Es el MISMO panel para el causador y para el administrador — el alcance lo
 * resuelve el backend por el rol (el causador ve sus empresas; el admin, todas
 * las de la cuenta). Así ninguno de los dos ve una versión distinta de la
 * verdad, que es justo lo que se quiere de un informe.
 */
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, ComposedChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  ArrowDownRight, ArrowUpRight, Building2, CalendarCheck, CalendarDays, DownloadCloud,
  FileSpreadsheet, FileStack, FileText, Info, KeyRound, Loader2, Scale, Share2, TriangleAlert,
} from "lucide-react";

import { api } from "@/lib/api";
import { fmt, periodosIVA } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { DatePicker } from "@/components/ui/date-picker";
import type { AnaliticaPorTipo } from "@/lib/types";

// Verde para lo que entra, rosa para lo que sale, índigo para el resultado.
// Se eligieron tonos que se leen igual en tema claro y oscuro.
const COLOR_INGRESOS = "#10b981";
const COLOR_COSTOS = "#f43f5e";
const COLOR_RESULTADO = "#6366f1";

// Un color por documento electrónico. Las notas crédito llevan el tono
// atenuado de su factura, para que se lea que son su contrapartida.
const COLOR_TIPO: Record<string, string> = {
  ventas: "#10b981",
  nc_ventas: "#6ee7b7",
  nd_ventas: "#34d399",
  compras: "#f43f5e",
  nc: "#fda4af",
  nd: "#fb7185",
  soporte: "#f59e0b",
  nc_soporte: "#fcd34d",
};


/** La DIAN espera las fechas como DD/MM/YYYY; los selectores las dan YYYY-MM-DD. */
function aDDMMYYYY(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

/** Cifra corta para los ejes: $1.451.647.645 no cabe, "$1.452 M" sí. */
function fmtCorto(n: number): string {
  const abs = Math.abs(n);
  const signo = n < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${signo}$${(abs / 1_000_000_000).toFixed(1)} MM`;
  if (abs >= 1_000_000) return `${signo}$${Math.round(abs / 1_000_000)} M`;
  if (abs >= 1_000) return `${signo}$${Math.round(abs / 1_000)} k`;
  return `${signo}$${abs}`;
}

/** "2026-08-01" → "1 ago 2026" */
function fechaCorta(iso: string): string {
  const [y, m, d] = iso.split("-");
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${Number(d)} ${meses[Number(m) - 1] ?? m} ${y}`;
}

/** "2026-09" → "Sep 2026" */
function mesLegible(iso: string): string {
  const [y, m] = iso.split("-");
  const nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  return `${nombres[Number(m) - 1] ?? m} ${y}`;
}

function Panel({ titulo, hint, children, alto = 300 }: {
  titulo: string; hint?: string; children: React.ReactNode; alto?: number;
}) {
  return (
    <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-card)" }}>
      <div className="border-b px-4 py-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{titulo}</span>
        {hint && <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>· {hint}</span>}
      </div>
      <div className="p-4" style={{ height: alto }}>{children}</div>
    </div>
  );
}

function Kpi({ icon: Icon, label, value, accent, nota }: {
  icon: React.ElementType; label: string; value: string; accent: string; nota?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl px-4 py-3.5" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-soft)", boxShadow: "var(--shadow-sm)" }}>
      <div className="absolute top-0 left-0 right-0 h-[3px]" style={{ backgroundColor: accent }} />
      <div className="mt-1 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{label}</p>
          <p className="mt-1 truncate text-xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{value}</p>
          {nota && <p className="mt-0.5 truncate text-xs" style={{ color: "var(--text-muted)" }}>{nota}</p>}
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ backgroundColor: accent + "18" }}>
          <Icon className="h-4 w-4" style={{ color: accent }} />
        </div>
      </div>
    </div>
  );
}

/** Tooltip con los mismos colores y formato de moneda del resto de la app. */
function TooltipCifras({ active, payload, label }: {
  active?: boolean; payload?: { name?: string; value?: number; color?: string }[]; label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border px-3 py-2 text-xs shadow-lg" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
      {label && <p className="mb-1 font-semibold" style={{ color: "var(--text-primary)" }}>{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="flex items-center gap-1.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
          {p.name}: <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{fmt(p.value ?? 0)}</span>
        </p>
      ))}
    </div>
  );
}

function SinDatos({ mensaje }: { mensaje: string }) {
  return (
    <div className="flex h-full items-center justify-center text-center text-sm" style={{ color: "var(--text-muted)" }}>
      {mensaje}
    </div>
  );
}

export function AnaliticaPanel({ contexto }: { contexto: "causador" | "admin" }) {
  const presets = useMemo(periodosIVA, []);
  const [desde, setDesde] = useState(presets[2].desde);
  const [hasta, setHasta] = useState(presets[2].hasta);
  const [empresaId, setEmpresaId] = useState<number | null>(null);
  const [token, setToken] = useState("");
  const [trayendo, setTrayendo] = useState(false);
  const [progreso, setProgreso] = useState({ done: 0, total: 0 });
  const [resultado, setResultado] = useState<{ guardados: number; errores: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [descargando, setDescargando] = useState<"xlsx" | "pdf" | null>(null);
  const queryClient = useQueryClient();

  const presetActivo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id ?? "personalizado";

  const { data: empresas } = useQuery({ queryKey: ["analitica-empresas"], queryFn: api.analiticaEmpresas });

  // El admin elige UNA empresa: costos e ingresos de compañías distintas sumados
  // en un mismo número no representan nada. El causador sí puede ver el conjunto
  // de las suyas.
  const exigeEmpresa = contexto === "admin" && (empresas?.length ?? 0) > 1;
  const faltaElegir = exigeEmpresa && empresaId === null;

  const opcionesEmpresa = useMemo(() => {
    const opts = (empresas ?? []).map((e) => ({ value: String(e.id), label: e.nombre }));
    return exigeEmpresa ? opts : [{ value: "", label: "Todas las empresas" }, ...opts];
  }, [empresas, exigeEmpresa]);

  const { data, isLoading } = useQuery({
    queryKey: ["analitica", desde, hasta, empresaId],
    queryFn: () => api.analiticaResumen(desde, hasta, empresaId),
    // Mientras se trae de la DIAN NO se consulta: los documentos se van
    // guardando de a uno, y refrescar en medio mostraría cifras a medio armar
    // que parecen definitivas. Se vuelve a consultar cuando termina.
    enabled: !faltaElegir && !trayendo,
    refetchOnWindowFocus: !trayendo,
  });

  // Cerrar o recargar la pestaña SÍ corta la descarga a mitad (se pierde la
  // conexión con el servidor). Lo ya guardado se conserva y volver a traer el
  // mismo periodo completa lo que falte, pero conviene avisar antes.
  useEffect(() => {
    if (!trayendo) return;
    const avisar = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [trayendo]);

  // ── Traer de la DIAN ──────────────────────────────────────────────────────
  const traer = async () => {
    if (empresaId == null || !token.trim()) return;
    setError(null);
    setTrayendo(true);
    setProgreso({ done: 0, total: 0 });
    try {
      const r = await api.analiticaSincronizar(
        {
          auth_url: token.trim(),
          empresa_id: empresaId,
          fecha_desde: aDDMMYYYY(desde),
          fecha_hasta: aDDMMYYYY(hasta),
        },
        (done, total) => setProgreso({ done, total }),
      );
      setResultado(r);
      setToken("");
      await queryClient.invalidateQueries({ queryKey: ["analitica"] });
      await queryClient.invalidateQueries({ queryKey: ["analitica-empresas"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo traer la información de la DIAN.");
    } finally {
      setTrayendo(false);
    }
  };

  const sinc = data?.ultima_sincronizacion ?? null;
  // ¿El rango que se está mirando cae dentro de lo que se trajo? Si no, las
  // cifras van a salir cortas y hay que avisarlo, no dejar que se interprete
  // como que no hubo movimiento.
  const cubrePeriodo = !sinc || (sinc.desde <= desde && sinc.hasta >= hasta);

  const descargar = async (formato: "xlsx" | "pdf") => {
    setDescargando(formato);
    try {
      const blob = formato === "pdf"
        ? await api.analiticaInformePdf(desde, hasta, empresaId)
        : await api.analiticaInformeXlsx(desde, hasta, empresaId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ciolix_analitica_${desde}_a_${hasta}.${formato}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDescargando(null);
    }
  };

  const ocupado = descargando !== null || trayendo;
  const k = data?.kpis;
  const margen = k && k.ingresos > 0 ? (k.resultado / k.ingresos) * 100 : null;

  const serie = (data?.serie_mensual ?? []).map((m) => ({ ...m, mesLabel: mesLegible(m.mes) }));
  const porTipo = data?.por_tipo ?? [];

  // Monto con su signo real: las notas crédito se dibujan hacia abajo, que es
  // lo que de verdad le hacen a la cifra.
  const tipoConSigno = porTipo.map((t: AnaliticaPorTipo) => ({
    ...t, montoNeto: t.monto * t.signo,
  }));
  const hayDatos = (k?.documentos ?? 0) > 0;

  // Recharts entrega la fila original dentro de `payload`, y tipa el evento de
  // forma genérica; de ahí el acceso defensivo.
  const filtrarPorBarra = (barra: unknown) => {
    const id = (barra as { payload?: { empresa_id?: number | null } })?.payload?.empresa_id;
    if (id != null) setEmpresaId(id);
  };

  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Analítica</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          {contexto === "admin"
            ? "Cómo van los costos, gastos e ingresos de cada empresa de la cuenta, según lo que reporta la DIAN."
            : "Cómo van tus costos, gastos e ingresos, según lo que reporta la DIAN."}
        </p>
        </div>
      </div>

      {/* ── Filtros ─────────────────────────────────────────────────────── */}
      <div className="mb-6 rounded-xl border p-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            <CalendarDays className="h-4 w-4" style={{ color: "var(--brand)" }} /> Periodo
          </span>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            por fecha de emisión del documento
          </span>
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

        {(empresas?.length ?? 0) > 1 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3" style={{ borderColor: "var(--border-soft)" }}>
            <Building2 className="h-4 w-4 shrink-0" style={{ color: "var(--brand)" }} />
            <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Empresa</span>
            <Combobox
              className="w-full sm:w-80"
              options={opcionesEmpresa}
              value={empresaId === null ? "" : String(empresaId)}
              onChange={(v) => setEmpresaId(v === "" ? null : Number(v))}
              placeholder={exigeEmpresa ? "Elegí una empresa..." : "Todas las empresas"}
              clearable={!exigeEmpresa}
            />
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {empresas?.length} disponibles
            </span>
          </div>
        )}
      </div>

      {/* ── Exportar ─────────────────────────────────────────────────────
          Entre el periodo y la traída a propósito: lo que se exporta es
          justamente el periodo elegido arriba. */}
      <div className="mb-6 flex flex-wrap items-center gap-2 rounded-xl border px-4 py-3"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <Share2 className="h-4 w-4" style={{ color: "var(--brand)" }} /> Exportar informe
        </span>
        <span className="mr-auto text-xs" style={{ color: "var(--text-muted)" }}>
          del periodo seleccionado
        </span>
        <Button onClick={() => descargar("pdf")} disabled={ocupado || !hayDatos}
          variant="outline" className="gap-1.5">
          {descargando === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
          PDF
        </Button>
        <Button onClick={() => descargar("xlsx")} disabled={ocupado || !hayDatos}
          variant="outline" className="gap-1.5">
          {descargando === "xlsx" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          Excel
        </Button>
      </div>

      {/* ── Traer de la DIAN ────────────────────────────────────────────── */}
      <div className="mb-6 rounded-xl border p-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            <KeyRound className="h-4 w-4" style={{ color: "var(--brand)" }} /> Información de la DIAN
          </span>
        </div>

        {/* Qué periodo está cargado. Es lo primero que hay que poder responder:
            sin esto, un informe vacío no distingue "falta traer" de "no hubo
            documentos", y no se sabe si hay que volver a pegar el token. */}
        {empresaId != null && (
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg px-3 py-2.5"
            style={{
              backgroundColor: sinc ? "color-mix(in srgb, var(--brand) 10%, transparent)" : "var(--bg-elevated)",
              border: `1px solid ${sinc ? "color-mix(in srgb, var(--brand) 35%, transparent)" : "var(--border-soft)"}`,
            }}>
            {sinc ? (
              <>
                <span className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  <CalendarCheck className="h-4 w-4" style={{ color: "var(--brand)" }} />
                  Datos cargados del {fechaCorta(sinc.desde)} al {fechaCorta(sinc.hasta)}
                </span>
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  {sinc.documentos} documento(s) · traídos el{" "}
                  {new Date(sinc.ejecutado_at).toLocaleString("es-CO", {
                    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
                  })}
                </span>
                {!cubrePeriodo && (
                  <span className="flex items-center gap-1 text-xs font-medium" style={{ color: COLOR_COSTOS }}>
                    <TriangleAlert className="h-3.5 w-3.5" />
                    El periodo que estás viendo no está cubierto: volvé a traer con el token.
                  </span>
                )}
              </>
            ) : (
              <span className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                <TriangleAlert className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
                Todavía no se ha traído información de la DIAN para esta empresa.
              </span>
            )}
          </div>
        )}

        <p className="mb-3 text-xs" style={{ color: "var(--text-secondary)" }}>
          Pegá el enlace de la DIAN de la empresa seleccionada y traé los documentos del periodo.
          Se descarga cada documento, así que un rango largo puede tardar varios minutos.
        </p>

        <div className="flex flex-wrap items-center gap-2">
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            disabled={trayendo || empresaId == null}
            placeholder="https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=...&rk=...&token=..."
            className="h-10 min-w-0 flex-1 rounded-lg border px-3 text-sm focus:outline-none focus:ring-2 disabled:opacity-40"
            style={{
              borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)",
              color: "var(--text-primary)", outlineColor: "var(--ring)",
            }}
          />
          <Button onClick={traer} disabled={trayendo || empresaId == null || !token.trim()} className="gap-1.5">
            {trayendo ? <Loader2 className="h-4 w-4 animate-spin" /> : <DownloadCloud className="h-4 w-4" />}
            {trayendo ? "Trayendo..." : "Traer de la DIAN"}
          </Button>
        </div>

        {empresaId == null && (
          <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
            Elegí primero una empresa: el enlace debe ser el de esa empresa.
          </p>
        )}

        {trayendo && progreso.total > 0 && (
          <div className="mt-3">
            <div className="mb-1 flex justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
              <span>Descargando documentos...</span>
              <span className="tabular-nums">{progreso.done} de {progreso.total}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--bg-elevated)" }}>
              <div className="h-full rounded-full transition-all"
                style={{ width: `${Math.round((progreso.done / progreso.total) * 100)}%`, backgroundColor: "var(--brand)" }} />
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3 flex gap-2 rounded-lg border px-3 py-2" style={{ borderColor: "#f43f5e55", backgroundColor: "#f43f5e14" }}>
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" style={{ color: COLOR_COSTOS }} />
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-primary)" }}>{error}</p>
          </div>
        )}

        {resultado && !trayendo && !error && (
          <p className="mt-3 text-xs" style={{ color: "var(--text-secondary)" }}>
            Listo: {resultado.guardados} documento(s) guardado(s).
            {resultado.errores > 0 && (
              <> {resultado.errores} no se pudieron descargar — volvé a traer el mismo
              periodo y se completan los que faltaron, sin duplicar lo que ya está.</>
            )}
          </p>
        )}
      </div>

      {trayendo ? (
        <div className="rounded-xl border px-4 py-16 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin" style={{ color: "var(--brand)" }} />
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            Trayendo la información de la DIAN
          </p>
          <p className="mx-auto mt-1 max-w-md text-sm" style={{ color: "var(--text-muted)" }}>
            El informe se muestra cuando termine la descarga, para que no veas cifras a medio armar.
            No cierres esta pestaña.
          </p>
        </div>
      ) : faltaElegir ? (
        <div className="rounded-xl border px-4 py-16 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <Building2 className="mx-auto mb-3 h-8 w-8" style={{ color: "var(--text-muted)" }} />
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Elegí una empresa para ver su analítica</p>
          <p className="mx-auto mt-1 max-w-md text-sm" style={{ color: "var(--text-muted)" }}>
            Los costos y los ingresos son de cada empresa por separado: sumarlos entre compañías
            distintas daría una cifra que no corresponde a ninguna.
          </p>
        </div>
      ) : isLoading ? (
        <div className="py-20 text-center"><Loader2 className="mx-auto h-7 w-7 animate-spin" style={{ color: "var(--brand)" }} /></div>
      ) : !hayDatos ? (
        <div className="rounded-xl border px-4 py-16 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <FileStack className="mx-auto mb-3 h-8 w-8" style={{ color: "var(--text-muted)" }} />
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>No hay documentos de la DIAN en este periodo</p>
          <p className="mx-auto mt-1 max-w-md text-sm" style={{ color: "var(--text-muted)" }}>
            {sinc
              ? "Ya se trajo información de la DIAN, pero no hay documentos emitidos en este rango. Probá con otras fechas."
              : "Pegá arriba el enlace de la DIAN y traé los documentos del periodo para ver el informe."}
          </p>
        </div>
      ) : (
        <>
          {/* ── KPIs ──────────────────────────────────────────────────── */}
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi icon={ArrowUpRight} label="Ingresos" value={fmt(k?.ingresos ?? 0)} accent={COLOR_INGRESOS}
              nota="Ventas menos notas crédito" />
            <Kpi icon={ArrowDownRight} label="Costos y gastos" value={fmt(k?.costos_gastos ?? 0)} accent={COLOR_COSTOS}
              nota="Compras y documento soporte, menos notas" />
            <Kpi icon={Scale} label="Resultado" value={fmt(k?.resultado ?? 0)} accent={COLOR_RESULTADO}
              nota={margen !== null ? `Margen ${margen.toFixed(1)}% sobre ingresos` : "Sin ingresos en el periodo"} />
            <Kpi icon={FileStack} label="Documentos" value={String(k?.documentos ?? 0)} accent="#7c3aed"
              nota={data?.alcance === "cuenta" ? `${data.empresas} empresas` : "Empresa seleccionada"} />
          </div>

          {/* ── Evolución + composición ───────────────────────────────── */}
          <div className="mb-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="xl:col-span-2">
              <Panel titulo="Evolución mensual" hint="ingresos contra costos y gastos, con el resultado de cada mes" alto={330}>
                {serie.length === 0 ? <SinDatos mensaje="Sin movimientos en el periodo." /> : (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={serie} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" vertical={false} />
                      <XAxis dataKey="mesLabel" tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                      <YAxis tickFormatter={fmtCorto} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} width={64} />
                      <Tooltip content={<TooltipCifras />} cursor={{ fill: "var(--bg-elevated)", opacity: 0.5 }} />
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="circle" />
                      <Bar dataKey="ingresos" name="Ingresos" fill={COLOR_INGRESOS} radius={[4, 4, 0, 0]} maxBarSize={44} />
                      <Bar dataKey="costos_gastos" name="Costos y gastos" fill={COLOR_COSTOS} radius={[4, 4, 0, 0]} maxBarSize={44} />
                      <Line type="monotone" dataKey="resultado" name="Resultado" stroke={COLOR_RESULTADO} strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </Panel>
            </div>

            <Panel titulo="Documentos por tipo" hint="cuántos de cada uno" alto={330}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={porTipo} dataKey="documentos" nameKey="label" cx="50%" cy="45%"
                    innerRadius={52} outerRadius={82} paddingAngle={2} strokeWidth={0}>
                    {porTipo.map((t) => <Cell key={t.tipo} fill={COLOR_TIPO[t.tipo] ?? "#94a3b8"} />)}
                  </Pie>
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload as AnaliticaPorTipo;
                      return (
                        <div className="rounded-lg border px-3 py-2 text-xs shadow-lg" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
                          <p className="font-semibold" style={{ color: "var(--text-primary)" }}>{d.label}</p>
                          <p style={{ color: "var(--text-secondary)" }}>{d.documentos} documentos</p>
                          <p className="tabular-nums" style={{ color: "var(--text-secondary)" }}>
                            {d.signo === -1 ? "Resta " : ""}{fmt(d.monto)}
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
                </PieChart>
              </ResponsiveContainer>
            </Panel>
          </div>

          {/* ── Efecto de cada documento ──────────────────────────────── */}
          <div className="mb-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Panel titulo="Efecto de cada documento" hint="las notas crédito van hacia abajo porque restan" alto={300}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={tipoConSigno} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" horizontal={false} />
                  <XAxis type="number" tickFormatter={fmtCorto} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                  <Tooltip
                    cursor={{ fill: "var(--bg-elevated)", opacity: 0.5 }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload as AnaliticaPorTipo & { montoNeto: number };
                      return (
                        <div className="rounded-lg border px-3 py-2 text-xs shadow-lg" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
                          <p className="font-semibold" style={{ color: "var(--text-primary)" }}>{d.label}</p>
                          <p className="tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(d.montoNeto)}</p>
                          <p style={{ color: "var(--text-muted)" }}>{d.documentos} documentos · {d.naturaleza === "ingresos" ? "ingresos" : "costos y gastos"}</p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="montoNeto" radius={[0, 4, 4, 0]} maxBarSize={26}>
                    {tipoConSigno.map((t) => <Cell key={t.tipo} fill={COLOR_TIPO[t.tipo] ?? "#94a3b8"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Panel>

            {data && data.por_empresa.length > 1 ? (
              <Panel titulo="Por empresa" hint="tocá una barra para filtrar el panel" alto={300}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.por_empresa.slice(0, 8)} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" vertical={false} />
                    <XAxis dataKey="nombre" tick={{ fontSize: 10, fill: "var(--text-muted)" }} tickLine={false} axisLine={false}
                      interval={0} angle={-18} textAnchor="end" height={54} />
                    <YAxis tickFormatter={fmtCorto} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} width={64} />
                    <Tooltip content={<TooltipCifras />} cursor={{ fill: "var(--bg-elevated)", opacity: 0.5 }} />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 4 }} iconType="circle" />
                    <Bar dataKey="ingresos" name="Ingresos" fill={COLOR_INGRESOS} radius={[4, 4, 0, 0]} maxBarSize={30}
                      onClick={filtrarPorBarra} style={{ cursor: "pointer" }} />
                    <Bar dataKey="costos_gastos" name="Costos y gastos" fill={COLOR_COSTOS} radius={[4, 4, 0, 0]} maxBarSize={30}
                      onClick={filtrarPorBarra} style={{ cursor: "pointer" }} />
                  </BarChart>
                </ResponsiveContainer>
              </Panel>
            ) : (
              <Panel titulo="Terceros con mayor peso" hint="en costos y gastos del periodo" alto={300}>
                {(data?.por_tercero ?? []).length === 0 ? <SinDatos mensaje="Sin costos ni gastos en el periodo." /> : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data?.por_tercero.slice(0, 8)} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" horizontal={false} />
                      <XAxis type="number" tickFormatter={fmtCorto} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                      <YAxis type="category" dataKey="nombre" width={150} tick={{ fontSize: 10, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                      <Tooltip content={<TooltipCifras />} cursor={{ fill: "var(--bg-elevated)", opacity: 0.5 }} />
                      <Bar dataKey="monto" name="Costos y gastos" fill={COLOR_COSTOS} radius={[0, 4, 4, 0]} maxBarSize={22} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </Panel>
            )}
          </div>

          {/* ── Cómo se calcula ───────────────────────────────────────── */}
          <div className="flex gap-2.5 rounded-xl border px-4 py-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
            <Info className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--brand)" }} />
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Las cifras salen de lo que la DIAN reporta con tu token, <strong>se haya causado o no</strong>,
              clasificado por tipo de documento. Los <strong>ingresos</strong> son las facturas de venta
              menos sus notas crédito, más sus notas débito. Los <strong>costos y gastos</strong> son las
              facturas de compra y los documentos soporte —la legalización de costo con personas naturales
              no obligadas a facturar— con el mismo ajuste por notas. Se usa la <strong>base gravable</strong>,
              sin IVA, porque el IVA descontable no es un costo sino un saldo a favor.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
