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
  FileSpreadsheet, FileStack, FileText, Info, KeyRound, Loader2, Percent, Receipt,
  Scale, TriangleAlert,
} from "lucide-react";

import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { fmt, periodosIVA, localYMD, MAX_MESES_CONSULTA, limiteHasta, AVISO_TOPE_CALENDARIO, type PeriodoPreset } from "@/lib/utils";
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

/** Botones de periodo rápido (Este mes / Último bimestre / Último cuatrimestre). */
function PresetsPeriodo({ presets, desde, hasta, onElegir }: {
  presets: PeriodoPreset[]; desde: string; hasta: string; onElegir: (p: PeriodoPreset) => void;
}) {
  const activo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id;
  return (
    <>
      {presets.map((p) => {
        const active = activo === p.id;
        return (
          <button key={p.id} type="button" onClick={() => onElegir(p)}
            className="rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors"
            style={{ backgroundColor: active ? "var(--brand)" : "var(--bg-elevated)", color: active ? "#fff" : "var(--text-secondary)", border: `1px solid ${active ? "var(--brand)" : "var(--border-soft)"}` }}>
            {p.label}
          </button>
        );
      })}
    </>
  );
}

/** Encabezado de cada paso: número + título + explicación corta. */
function EncabezadoPaso({ numero, icon: Icon, titulo, descripcion }: {
  numero: number; icon: React.ElementType; titulo: string; descripcion: string;
}) {
  return (
    <div className="mb-3 flex items-start gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
        style={{ backgroundColor: "var(--brand)" }}>
        {numero}
      </span>
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          <Icon className="h-4 w-4" style={{ color: "var(--brand)" }} /> {titulo}
        </p>
        <p className="mt-0.5 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>{descripcion}</p>
      </div>
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
  // undefined = todavía no se ha tocado el selector: se usa la empresa por defecto.
  const [empresaElegida, setEmpresaId] = useState<number | null | undefined>(undefined);
  const empresaActiva = useAuthStore((s) => s.empresaId);
  const [token, setToken] = useState("");
  const [trayendo, setTrayendo] = useState(false);
  const [progreso, setProgreso] = useState({ done: 0, total: 0 });
  const [resultado, setResultado] = useState<{ guardados: number; errores: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [descargando, setDescargando] = useState<"xlsx" | "pdf" | null>(null);
  const [reprocesando, setReprocesando] = useState(false);
  const [reprocesadoResult, setReprocesadoResult] = useState<{ actualizados: number } | null>(null);
  const queryClient = useQueryClient();

  // Periodo a TRAER de la DIAN, aparte del filtro del informe: el informe lee lo
  // ya guardado y puede abarcar el año entero; la descarga con el token se
  // limita a 4 meses por vez (igual que el importador DIAN). Arranca en
  // "Este mes" (del 1 a hoy), como el importador.
  const [traerDesde, setTraerDesde] = useState(presets[0].desde);
  const [traerHasta, setTraerHasta] = useState(presets[0].hasta);
  const hoy = localYMD(new Date());
  const topeHasta = (d: string) => (limiteHasta(d) < hoy ? limiteHasta(d) : hoy);
  const cambiarTraerDesde = (v: string) => {
    setTraerDesde(v);
    if (traerHasta > topeHasta(v)) setTraerHasta(topeHasta(v));
  };
  const rangoExcedido = traerHasta > limiteHasta(traerDesde);

  const { data: empresas } = useQuery({ queryKey: ["analitica-empresas"], queryFn: api.analiticaEmpresas });

  // El admin elige UNA empresa: costos e ingresos de compañías distintas sumados
  // en un mismo número no representan nada. El causador sí puede ver el conjunto
  // de las suyas.
  const exigeEmpresa = contexto === "admin" && (empresas?.length ?? 0) > 1;

  // Empresa por defecto, para que el campo del enlace DIAN no quede bloqueado
  // sin explicación: si es un causador, la que ya tiene activa en el menú
  // lateral; si hay una sola, esa. El admin con varias sí tiene que elegir.
  const empresaPorDefecto =
    contexto === "causador" && empresas?.some((e) => e.id === empresaActiva) ? empresaActiva
    : empresas?.length === 1 ? empresas[0].id
    : null;
  const empresaId = empresaElegida === undefined ? empresaPorDefecto : empresaElegida;
  const nombreEmpresa = empresas?.find((e) => e.id === empresaId)?.nombre;
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

  // Fase 3 del módulo de IVA: se recalcula solo con el mismo periodo/empresa
  // de arriba — no hay botón aparte, es justo lo que Andrés pidió ("después
  // de seleccionar el período, recalcular automáticamente").
  const { data: balance, isLoading: cargandoBalance } = useQuery({
    queryKey: ["analitica-balance-iva", desde, hasta, empresaId],
    queryFn: () => api.analiticaBalanceIva(desde, hasta, empresaId),
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
    if (rangoExcedido) {
      setError(`El periodo no puede ser mayor a ${MAX_MESES_CONSULTA} meses. Acorta las fechas o trae por partes con el mismo token.`);
      return;
    }
    setError(null);
    setTrayendo(true);
    setProgreso({ done: 0, total: 0 });
    try {
      const r = await api.analiticaSincronizar(
        {
          auth_url: token.trim(),
          empresa_id: empresaId,
          fecha_desde: aDDMMYYYY(traerDesde),
          fecha_hasta: aDDMMYYYY(traerHasta),
        },
        (done, total) => setProgreso({ done, total }),
      );
      setResultado(r);
      setToken("");
      setDesde(traerDesde);
      setHasta(traerHasta);
      await queryClient.invalidateQueries({ queryKey: ["analitica"] });
      await queryClient.invalidateQueries({ queryKey: ["analitica-empresas"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo traer la información de la DIAN.");
    } finally {
      setTrayendo(false);
    }
  };

  const reprocesar = async () => {
    setReprocesando(true);
    setReprocesadoResult(null);
    try {
      const r = await api.analiticaReprocesarXml(empresaId ?? undefined);
      setReprocesadoResult({ actualizados: r.actualizados });
      await queryClient.invalidateQueries({ queryKey: ["analitica"] });
      await queryClient.invalidateQueries({ queryKey: ["analitica-balance-iva"] });
    } catch {
      // silencioso: el botón simplemente deja de girar
    } finally {
      setReprocesando(false);
    }
  };

  const sinc = data?.ultima_sincronizacion ?? null;
  // ¿El rango que se está mirando cae dentro de lo que se trajo? Si no, las
  // cifras van a salir cortas y hay que avisarlo, no dejar que se interprete
  // como que no hubo movimiento.
  // Se mira la suma de todas las traídas (un año se baja por partes de 4 meses).
  const cobertura = data?.cobertura_dian ?? (sinc ? [{ desde: sinc.desde, hasta: sinc.hasta }] : []);
  const cubrePeriodo = !sinc || cobertura.some((c) => c.desde <= desde && c.hasta >= hasta);

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

  // El balance de IVA en gráfico, mismos colores que sus KPI.
  const datosBalanceIva = [
    { nombre: "IVA generado", valor: balance?.iva_generado ?? 0, color: COLOR_INGRESOS },
    { nombre: "IVA descontable", valor: balance?.iva_descontable ?? 0, color: "#3b82f6" },
    { nombre: "Balance analítico de IVA", valor: balance?.balance_analitico_iva ?? 0, color: COLOR_RESULTADO },
  ];

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

      {/* ── Empresa: aplica a la descarga y al informe ─────────────────── */}
      {(empresas?.length ?? 0) > 1 && (
        <div className="mb-6 flex flex-wrap items-center gap-2 rounded-xl border p-4"
          style={{
            borderColor: empresaId == null && exigeEmpresa ? "rgba(245,158,11,0.5)" : "var(--border-soft)",
            backgroundColor: "var(--bg-surface)",
          }}>
          <Building2 className="h-4 w-4 shrink-0" style={{ color: "var(--brand)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Empresa</span>
          <Combobox
            className="w-full sm:w-80"
            options={opcionesEmpresa}
            value={empresaId === null ? "" : String(empresaId)}
            onChange={(v) => setEmpresaId(v === "" ? null : Number(v))}
            placeholder={exigeEmpresa ? "Elige una empresa..." : "Todas las empresas"}
            clearable={!exigeEmpresa}
          />
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {empresas?.length} disponibles
          </span>
        </div>
      )}

      {/* ── Paso 1: descargar de la DIAN ────────────────────────────────── */}
      <div className="mb-6 rounded-xl border p-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <EncabezadoPaso numero={1} icon={KeyRound} titulo="Descargar documentos de la DIAN"
          descripcion="Trae las facturas y notas que la DIAN tiene de la empresa. Solo hace falta cuando quieras actualizar la información; lo que descargues se suma a lo que ya estaba." />

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
                  {nombreEmpresa ? `${nombreEmpresa}: ya descargado` : "Ya descargado"}{" "}
                  {cobertura.map((c) => `del ${fechaCorta(c.desde)} al ${fechaCorta(c.hasta)}`).join(" · ")}
                </span>
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Última descarga: {sinc.documentos} documento(s) el{" "}
                  {new Date(sinc.ejecutado_at).toLocaleString("es-CO", {
                    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </>
            ) : (
              <span className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                <TriangleAlert className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
                Todavía no se ha descargado información de la DIAN para {nombreEmpresa ?? "esta empresa"}.
              </span>
            )}
          </div>
        )}

        <div className="mb-3 space-y-2">
          <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>¿Qué fechas quieres descargar?</p>
          <div className="flex flex-wrap items-end gap-2">
            <PresetsPeriodo presets={presets} desde={traerDesde} hasta={traerHasta}
              onElegir={(p) => { setTraerDesde(p.desde); setTraerHasta(p.hasta); }} />
            <div className="ml-1 flex flex-wrap items-end gap-2">
              <DatePicker label="Desde" value={traerDesde} onChange={cambiarTraerDesde} max={traerHasta} />
              <span className="pb-2 text-xs" style={{ color: "var(--text-muted)" }}>hasta</span>
              <DatePicker label="Hasta" value={traerHasta} onChange={setTraerHasta} min={traerDesde}
                max={topeHasta(traerDesde)} hint={AVISO_TOPE_CALENDARIO} />
            </div>
          </div>
          <div className="flex items-start gap-2 rounded-lg border px-3 py-2"
            style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}>
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "var(--info-text)" }} />
            <p className="text-xs leading-relaxed" style={{ color: "var(--info-text)" }}>
              <strong>Máximo {MAX_MESES_CONSULTA} meses por descarga.</strong> Para un periodo más largo, descárgalo
              por partes con el mismo enlace. Cada documento se descarga uno a uno, así que un rango largo puede tardar varios minutos.
            </p>
          </div>
        </div>

        {empresaId == null && (
          <div className="mb-3 flex items-start gap-2 rounded-lg border px-3 py-2"
            style={{ borderColor: "rgba(245,158,11,0.4)", backgroundColor: "rgba(245,158,11,0.08)" }}>
            <Building2 className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "#d97706" }} />
            <p className="text-xs leading-relaxed" style={{ color: "#d97706" }}>
              {(empresas?.length ?? 0) === 0
                ? "No tienes empresas disponibles para descargar información de la DIAN."
                : <><strong>Primero elige la empresa arriba</strong> para poder pegar el enlace de la DIAN. El enlace tiene que ser el de esa empresa.</>}
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            disabled={trayendo || empresaId == null}
            placeholder={empresaId == null
              ? "Elige primero una empresa para pegar el enlace"
              : "Pega aquí el enlace de la DIAN: https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=..."}
            className="h-10 min-w-0 flex-1 rounded-lg border px-3 text-sm focus:outline-none focus:ring-2 disabled:opacity-40"
            style={{
              borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)",
              color: "var(--text-primary)", outlineColor: "var(--ring)",
            }}
          />
          <Button onClick={traer} disabled={trayendo || empresaId == null || !token.trim()} className="gap-1.5">
            {trayendo ? <Loader2 className="h-4 w-4 animate-spin" /> : <DownloadCloud className="h-4 w-4" />}
            {trayendo ? "Descargando..." : "Descargar de la DIAN"}
          </Button>
          <Button onClick={reprocesar} disabled={reprocesando || trayendo || empresaId == null}
            variant="outline" className="gap-1.5" title="Actualiza los datos guardados con el parser más reciente sin ir a la DIAN. Útil para corregir IVA en facturas AIU.">
            {reprocesando ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileStack className="h-4 w-4" />}
            {reprocesando ? "Reprocesando..." : "Reprocesar XML guardado"}
          </Button>
        </div>

        {reprocesadoResult && !reprocesando && (
          <p className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
            Reprocesado: {reprocesadoResult.actualizados} documento(s) actualizados con el parser más reciente.
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
            Listo: {resultado.guardados} documento(s) guardado(s). El informe de abajo ya muestra esas fechas.
            {resultado.errores > 0 && (
              <> {resultado.errores} no se pudieron descargar: vuelve a descargar el mismo
              periodo y se completan los que faltaron, sin duplicar lo que ya está.</>
            )}
          </p>
        )}
      </div>

      {/* ── Paso 2: ver el informe ──────────────────────────────────────────
          Lee lo YA descargado; no va a la DIAN, por eso no tiene tope de meses. */}
      <div className="mb-6 rounded-xl border p-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
        <EncabezadoPaso numero={2} icon={CalendarDays} titulo="Ver el informe"
          descripcion="Elige qué fechas ver en las gráficas y en el PDF o Excel. Se calcula con lo que ya descargaste de la DIAN, por fecha de emisión del documento." />
        <div className="flex flex-wrap items-end gap-2">
          <PresetsPeriodo presets={presets} desde={desde} hasta={hasta}
            onElegir={(p) => { setDesde(p.desde); setHasta(p.hasta); }} />
          <div className="ml-1 flex flex-wrap items-end gap-2">
            <DatePicker label="Desde" value={desde} onChange={setDesde} max={hasta} />
            <span className="pb-2 text-xs" style={{ color: "var(--text-muted)" }}>hasta</span>
            <DatePicker label="Hasta" value={hasta} onChange={setHasta} min={desde} />
          </div>
          {/* Lo que se exporta es justamente el periodo elegido aquí. */}
          <div className="ml-auto flex items-center gap-2">
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
        </div>
        {sinc && !cubrePeriodo && (
          <p className="mt-3 flex items-center gap-1.5 text-xs font-medium" style={{ color: COLOR_COSTOS }}>
            <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
            Parte de estas fechas todavía no se ha descargado de la DIAN, así que las cifras pueden salir incompletas. Descárgalas en el paso 1.
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
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Elige una empresa para ver su analítica</p>
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
              ? "Ya se descargó información de la DIAN, pero no hay documentos emitidos en estas fechas. Prueba con otras en el paso 2."
              : "Descarga primero los documentos de la DIAN en el paso 1 para ver el informe."}
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

          {/* ── Balance de IVA (Fase 3) ──────────────────────────────────
              Nunca "saldo a pagar" ni "saldo a favor" — el Formulario 300
              depende de otros conceptos de la liquidación que este número
              no cubre. Se recalcula solo con el mismo periodo de arriba. */}
          <div className="mb-4 overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-card)" }}>
            <div className="border-b px-4 py-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Analítica de IVA</span>
              <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>· generado contra descontable del periodo</span>
            </div>
            <div className="p-4">
              {cargandoBalance ? (
                <div className="py-6 text-center"><Loader2 className="mx-auto h-6 w-6 animate-spin" style={{ color: "var(--brand)" }} /></div>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <Kpi icon={ArrowUpRight} label="IVA generado" value={fmt(balance?.iva_generado ?? 0)} accent={COLOR_INGRESOS}
                      nota={`${balance?.documentos_ventas ?? 0} documento(s) de venta`} />
                    <Kpi icon={Percent} label="IVA descontable" value={fmt(balance?.iva_descontable ?? 0)} accent="#3b82f6"
                      nota={`de ${fmt(balance?.iva_facturado_compras ?? 0)} facturado en compras`} />
                    <Kpi icon={Scale} label="Balance analítico de IVA" value={fmt(balance?.balance_analitico_iva ?? 0)} accent={COLOR_RESULTADO}
                      nota={`${balance?.documentos_compras ?? 0} documento(s) de compra`} />
                  </div>

                  {/* El mismo balance, en gráfico — no solo en número. */}
                  <div className="mt-4" style={{ height: 180 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={datosBalanceIva} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" horizontal={false} />
                        <XAxis type="number" tickFormatter={fmtCorto} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                        <YAxis type="category" dataKey="nombre" width={150} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                        <Tooltip content={<TooltipCifras />} cursor={{ fill: "var(--bg-elevated)", opacity: 0.5 }} />
                        <Bar dataKey="valor" name="Monto" radius={[0, 4, 4, 0]} maxBarSize={28}>
                          {datosBalanceIva.map((d) => <Cell key={d.nombre} fill={d.color} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </>
              )}
              <p className="mt-3 flex items-start gap-1.5 text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
                <Receipt className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                IVA generado − IVA descontable = Balance analítico de IVA. No es el saldo fiscal
                final del Formulario 300 — ese depende de otros conceptos de la liquidación. El IVA
                descontable solo cuenta lo ya clasificado (o sugerido) como tal en Formulario 300 ·
                Compras; lo que sigue pendiente de confirmar no suma acá.
              </p>
            </div>
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
