"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import {
  AlertTriangle, Search, Download, Loader2, ShieldCheck, KeyRound, CalendarDays, X,
  ShoppingCart, TrendingUp, FileMinus2, ArrowRight, CheckCircle2, FileCheck2,
} from "lucide-react";
import type { DocTipo } from "@/stores/wizard";
import type { Factura } from "@/lib/types";

// YYYY-MM-DD (input date) → DD/MM/YYYY (formato que espera el portal DIAN)
function isoToDian(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  const [, y, mo, d] = m;
  return `${d}/${mo}/${y}`;
}
function hoyISO(offsetDias = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDias);
  return d.toISOString().slice(0, 10);
}
function localYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function buildPresets() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  return [
    { id: "este", label: "Este mes", desde: localYMD(new Date(y, m, 1)), hasta: localYMD(now) },
    { id: "pasado", label: "Mes pasado", desde: localYMD(new Date(y, m - 1, 1)), hasta: localYMD(new Date(y, m, 0)) },
    { id: "3m", label: "Últimos 3 meses", desde: localYMD(new Date(y, m - 2, 1)), hasta: localYMD(now) },
    { id: "anio", label: "Último año", desde: localYMD(new Date(y - 1, m, 1)), hasta: localYMD(now) },
  ];
}
function limpiarError(raw: string): string {
  const jsonPart = raw.replace(/^API\s+\d+:\s*/, "");
  try {
    const parsed = JSON.parse(jsonPart);
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch { /* no era JSON */ }
  return jsonPart || raw;
}

type Bucket = "compras" | "nc" | "ventas" | "nc_ventas" | "soporte" | "nc_soporte";

const DESTINOS: { tipo: Bucket; ruta: string; label: string; icon: typeof ShoppingCart; color: string }[] = [
  { tipo: "compras",    ruta: "/causacion",           label: "Causación Compras", icon: ShoppingCart, color: "#4F46E5" },
  { tipo: "nc",         ruta: "/causacion-nc",         label: "NC Compras",        icon: FileMinus2,   color: "#7c3aed" },
  { tipo: "ventas",     ruta: "/causacion-ventas",     label: "Causación Ventas",  icon: TrendingUp,   color: "#0ea5a4" },
  { tipo: "nc_ventas",  ruta: "/causacion-nc-ventas",  label: "NC Ventas",         icon: FileMinus2,   color: "#d97706" },
  { tipo: "soporte",    ruta: "/causacion-soporte",    label: "Documento Soporte", icon: FileCheck2,   color: "#0284c7" },
  { tipo: "nc_soporte", ruta: "/causacion-nc-soporte", label: "Ajuste Soporte",    icon: FileMinus2,   color: "#9333ea" },
];

export function ImportarDian() {
  const qc = useQueryClient();
  const presets = useMemo(buildPresets, []);
  const [authUrl, setAuthUrl] = useState("");
  const [desde, setDesde] = useState(() => presets[0].desde);
  const [hasta, setHasta] = useState(() => presets[0].hasta);
  const presetActivo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id ?? "personalizado";

  const [consultando, setConsultando] = useState(false);
  const [importando, setImportando] = useState(false);
  const [prog, setProg] = useState({ done: 0, total: 0 });
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<{ compras: number; ventas: number; soporte: number; soporteAjuste: number; idsCompras: string[]; idsVentas: string[]; idsSoporte: string[]; idsSoporteAjuste: string[] } | null>(null);
  const [resumen, setResumen] = useState<Record<Bucket, number> | null>(null);
  const [erroresImport, setErroresImport] = useState(0);

  const consultar = async () => {
    if (!authUrl.trim()) { setError("Pega la URL de AuthToken de la DIAN."); return; }
    setConsultando(true); setError(""); setResultado(null); setResumen(null);
    try {
      const res = await api.dianConsultarTodo({ auth_url: authUrl.trim(), fecha_desde: isoToDian(desde), fecha_hasta: isoToDian(hasta) });
      const idsCompras = res.compras.documents.map((d) => d.id).filter((x): x is string => !!x);
      const idsSoporte = res.soporte.documents.map((d) => d.id).filter((x): x is string => !!x);
      const idsSoporteAjuste = res.soporte_ajuste.documents.map((d) => d.id).filter((x): x is string => !!x);
      const emitidoAparte = new Set([...idsSoporte, ...idsSoporteAjuste]);
      // Los DS y sus ajustes se consultan aparte (tipo 05/95): se quitan de ventas
      // por si aparecieran también en la bandeja de emitidos, para no duplicar.
      const idsVentas = res.ventas.documents.map((d) => d.id).filter((x): x is string => !!x && !emitidoAparte.has(x));
      setResultado({
        compras: res.compras.total, ventas: idsVentas.length,
        soporte: idsSoporte.length, soporteAjuste: idsSoporteAjuste.length,
        idsCompras, idsVentas, idsSoporte, idsSoporteAjuste,
      });
    } catch (e) {
      setError(limpiarError((e as Error).message));
    } finally {
      setConsultando(false);
    }
  };

  const distribuir = async (buckets: Record<Bucket, Factura[]>) => {
    const conteo: Record<Bucket, number> = { compras: 0, nc: 0, ventas: 0, nc_ventas: 0, soporte: 0, nc_soporte: 0 };
    for (const { tipo } of DESTINOS) {
      const nuevas = buckets[tipo] ?? [];
      conteo[tipo] = nuevas.length;
      if (!nuevas.length) continue;
      // Fusionar con lo que ya haya en ese borrador (sin duplicar por numero_dian).
      const completo = await api.getBorradorCompleto(tipo as DocTipo);
      const prev = (completo?.datos ?? {}) as Record<string, unknown>;
      const existentes = (prev.facturas as Factura[]) ?? [];
      const nums = new Set(existentes.map((f) => f.numero_dian));
      const merged = [...existentes, ...nuevas.filter((f) => !nums.has(f.numero_dian))];
      const snapshot = {
        facturas: merged,
        tipoComp: (prev.tipoComp as string) ?? "",
        centroCosto: (prev.centroCosto as string) ?? "",
        facturasYaCausadas: prev.facturasYaCausadas ?? [],
        facturasOmitidas: prev.facturasOmitidas ?? [],
        suggestions: prev.suggestions ?? {},
        paso2: prev.paso2 ?? null,
      };
      await api.guardarBorrador({
        datos: snapshot as unknown as Record<string, unknown>,
        total_facturas: merged.length,
        total_verificadas: 0,
        tipo_comp: snapshot.tipoComp || null,
      }, tipo as DocTipo);
      qc.invalidateQueries({ queryKey: ["borrador", tipo] });
    }
    return conteo;
  };

  const importar = async () => {
    if (!resultado) return;
    const totalDocs = resultado.idsCompras.length + resultado.idsVentas.length + resultado.idsSoporte.length + resultado.idsSoporteAjuste.length;
    if (!totalDocs) { setError("No hay documentos para traer en este rango."); return; }
    setImportando(true); setError(""); setResumen(null); setErroresImport(0);
    setProg({ done: 0, total: totalDocs });
    try {
      const { buckets, errores } = await api.dianImportarTodoStream(
        { auth_url: authUrl.trim(), ids_compras: resultado.idsCompras, ids_ventas: resultado.idsVentas, ids_soporte: resultado.idsSoporte, ids_soporte_ajuste: resultado.idsSoporteAjuste },
        (done, total) => setProg({ done, total }),
      );
      const conteo = await distribuir(buckets);
      setResumen(conteo);
      setErroresImport(errores);
    } catch (e) {
      setError(limpiarError((e as Error).message));
    } finally {
      setImportando(false);
      setProg({ done: 0, total: 0 });
    }
  };

  const pct = prog.total > 0 ? Math.round((prog.done / prog.total) * 100) : 0;

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 lg:py-10 space-y-5">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Importar de la DIAN</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Pega el token una sola vez y trae <strong>todo</strong> del rango: el sistema separa cada documento
          en su módulo — Compras, NC Compras, Ventas, NC Ventas, Documento Soporte y Ajuste Soporte.
        </p>
      </div>

      {/* Aviso de seguridad */}
      <div className="flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}>
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--info-text)" }} />
        <div className="text-xs leading-relaxed" style={{ color: "var(--info-text)" }}>
          Inicia sesión en el portal de la DIAN, copia la <strong>URL de AuthToken</strong> y pégala aquí.
          Con un solo token se traen recibidas (compras), emitidas (ventas) y documentos soporte. Tu token es temporal y no se guarda.
        </div>
      </div>

      {/* URL AuthToken */}
      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <KeyRound className="h-4 w-4" style={{ color: "var(--brand)" }} /> URL AuthToken de la DIAN
        </label>
        <input
          type="text"
          value={authUrl}
          onChange={(e) => setAuthUrl(e.target.value)}
          placeholder="https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=...&rk=...&token=..."
          className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--brand)]"
          style={{ borderColor: "var(--border-strong)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)" }}
        />
      </div>

      {/* Periodo */}
      <div className="space-y-2.5">
        <label className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <CalendarDays className="h-4 w-4" style={{ color: "var(--brand)" }} /> Periodo
        </label>
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => {
            const active = presetActivo === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => { setDesde(p.desde); setHasta(p.hasta); }}
                className="rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors"
                style={{
                  backgroundColor: active ? "var(--brand)" : "var(--bg-elevated)",
                  color: active ? "#fff" : "var(--text-secondary)",
                  border: `1px solid ${active ? "var(--brand)" : "var(--border-soft)"}`,
                }}
              >
                {p.label}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <DatePicker label="Desde" value={desde} onChange={setDesde} max={hasta} />
          <span className="pb-2 text-xs" style={{ color: "var(--text-muted)" }}>hasta</span>
          <DatePicker label="Hasta" value={hasta} onChange={setHasta} min={desde} max={hoyISO(0)} />
        </div>
      </div>

      <Button onClick={consultar} disabled={consultando || importando} size="lg" className="gap-2">
        {consultando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        {consultando ? "Consultando DIAN…" : "Consultar todo"}
      </Button>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)" }} role="alert">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--error-text)" }} />
          <div className="flex-1">
            <p className="text-sm font-semibold" style={{ color: "var(--error-text)" }}>No pudimos consultar la DIAN</p>
            <p className="mt-0.5 text-sm" style={{ color: "var(--error-text)", opacity: 0.9 }}>{error}</p>
          </div>
          <button type="button" onClick={() => setError("")} style={{ color: "var(--error-text)" }}><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Resultado de la consulta */}
      {resultado && !resumen && (
        <div className="rounded-xl border p-4 space-y-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Encontrado en el rango
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg border p-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <div className="flex items-center gap-2"><ShoppingCart className="h-4 w-4" style={{ color: "#4F46E5" }} /><span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Recibidas (compras)</span></div>
              <p className="mt-1 text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{resultado.compras}</p>
            </div>
            <div className="rounded-lg border p-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <div className="flex items-center gap-2"><TrendingUp className="h-4 w-4" style={{ color: "#0ea5a4" }} /><span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Emitidas (ventas)</span></div>
              <p className="mt-1 text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{resultado.ventas}</p>
            </div>
            <div className="rounded-lg border p-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <div className="flex items-center gap-2"><FileCheck2 className="h-4 w-4" style={{ color: "#0284c7" }} /><span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Documento soporte</span></div>
              <p className="mt-1 text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{resultado.soporte + resultado.soporteAjuste}</p>
              {resultado.soporteAjuste > 0 && (
                <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>{resultado.soporte} soporte · {resultado.soporteAjuste} ajuste</p>
              )}
            </div>
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Al traer, cada documento va a su módulo: facturas a Compras/Ventas, notas crédito a NC, y los documentos soporte (y sus ajustes) a Documento Soporte.
          </p>

          {importando && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
                <span>Descargando y clasificando…</span><span>{prog.done}/{prog.total}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full" style={{ backgroundColor: "var(--border-soft)" }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: "var(--brand)" }} />
              </div>
            </div>
          )}

          {(() => {
            const totalDocs = resultado.compras + resultado.ventas + resultado.soporte + resultado.soporteAjuste;
            return (
              <Button onClick={importar} disabled={importando || totalDocs === 0} size="lg" className="gap-2 w-full">
                {importando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                {importando ? "Trayendo…" : `Traer ${totalDocs} y distribuir`}
              </Button>
            );
          })()}
        </div>
      )}

      {/* Resumen tras distribuir */}
      {resumen && (
        <div className="rounded-xl border p-4 space-y-4" style={{ borderColor: "var(--success-border)", backgroundColor: "var(--success-bg)" }}>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5" style={{ color: "var(--success-text)" }} />
            <p className="text-sm font-semibold" style={{ color: "var(--success-text)" }}>Listo — cada documento quedó en su módulo</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {DESTINOS.map(({ tipo, ruta, label, icon: Icon, color }) => (
              <Link
                key={tipo}
                href={ruta}
                className="flex items-center justify-between rounded-lg border p-3 transition-opacity hover:opacity-80"
                style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4" style={{ color }} />
                  <span className="text-sm" style={{ color: "var(--text-primary)" }}>{label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{resumen[tipo]}</span>
                  <ArrowRight className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
                </div>
              </Link>
            ))}
          </div>
          <p className="text-xs" style={{ color: "var(--success-text)", opacity: 0.9 }}>
            Entra a cada módulo (verás la tarjeta “Continuar borrador”) para mapear las cuentas y causar.
            Se fusionaron con lo que ya tenías sin duplicar.
          </p>

          {erroresImport > 0 && (
            <div className="rounded-lg border p-3 space-y-2" style={{ borderColor: "var(--warning-border)", backgroundColor: "var(--warning-bg)" }}>
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--warning-text)" }} />
                <p className="text-xs" style={{ color: "var(--warning-text)" }}>
                  <strong>{erroresImport} documento(s) no se pudieron traer</strong> (fallo de red o descarga).
                  Lo demás ya quedó guardado. Dale <strong>Reintentar</strong> para completar los que faltaron —
                  no se duplican los que ya entraron.
                </p>
              </div>
              <Button onClick={() => { void importar(); }} disabled={importando} size="sm" className="gap-1.5">
                {importando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                {importando ? "Reintentando…" : "Reintentar los que faltaron"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
