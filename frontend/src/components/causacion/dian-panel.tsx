"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { AlertTriangle, Search, Download, Loader2, ShieldCheck, KeyRound, CheckSquare, Square, CalendarDays, X } from "lucide-react";
import type { DianDocumento, Factura } from "@/lib/types";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ¿El error es transitorio (red/DNS/DIAN caída) y conviene reintentar? El API
// devuelve 502/503/504 para esos casos; el fetch lanza "Failed to fetch" si no
// hay red. Un 400 (token/sesión) NO se reintenta.
function esErrorTransitorio(msg: string): boolean {
  return /API 50[234]/.test(msg) || /Failed to fetch/i.test(msg) || /NetworkError/i.test(msg) || /red temporal/i.test(msg);
}

// Extrae un mensaje legible de un error del API (formato `API 400: {"detail":"..."}`).
function limpiarError(raw: string): string {
  const jsonPart = raw.replace(/^API\s+\d+:\s*/, "");
  try {
    const parsed = JSON.parse(jsonPart);
    if (typeof parsed?.detail === "string") return parsed.detail;
    if (Array.isArray(parsed?.detail)) {
      return parsed.detail.map((d: { msg?: string }) => d?.msg).filter(Boolean).join(" · ") || jsonPart;
    }
  } catch { /* no era JSON */ }
  return jsonPart || raw;
}

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

// YYYY-MM-DD a partir de una fecha LOCAL (evita el corrimiento de día de toISOString)
function localYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Presets de rango de fechas basados en meses calendario.
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

interface Props {
  /** Recibe las facturas ya parseadas (mismo shape que la carga manual). */
  onImportadas: (facturas: Factura[]) => void | Promise<void>;
}

export function DianPanel({ onImportadas }: Props) {
  const presets = useMemo(buildPresets, []);
  const [authUrl, setAuthUrl] = useState("");
  const [desde, setDesde] = useState(() => presets[0].desde); // por defecto: "Este mes"
  const [hasta, setHasta] = useState(() => presets[0].hasta);

  const presetActivo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id ?? "personalizado";
  const aplicarPreset = (p: { desde: string; hasta: string }) => { setDesde(p.desde); setHasta(p.hasta); };

  const [consultando, setConsultando] = useState(false);
  const [importando, setImportando] = useState(false);
  const [prog, setProg] = useState({ done: 0, total: 0 }); // progreso real de descarga
  const [reintentoEn, setReintentoEn] = useState(0); // segundos restantes para el reintento (0 = ninguno)
  const [error, setError] = useState("");

  // Ejecuta `fn` reintentando ante errores transitorios, con cuenta regresiva
  // visible antes de cada reintento. Los errores no-transitorios (token/sesión)
  // se lanzan de inmediato.
  async function conReintentos<T>(fn: () => Promise<T>): Promise<T> {
    const MAX = 2;      // reintentos automáticos
    const ESPERA = 4;   // segundos de espera antes de cada reintento
    let ultimo: unknown;
    for (let intento = 0; intento <= MAX; intento++) {
      try {
        const r = await fn();
        setReintentoEn(0);
        return r;
      } catch (e) {
        ultimo = e;
        if (intento === MAX || !esErrorTransitorio((e as Error).message)) {
          setReintentoEn(0);
          throw e;
        }
        for (let s = ESPERA; s > 0; s--) { setReintentoEn(s); await sleep(1000); }
        setReintentoEn(0);
      }
    }
    throw ultimo;
  }
  const [documentos, setDocumentos] = useState<DianDocumento[] | null>(null);
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());

  // La alerta de error se auto-oculta a los 6s (no se queda para siempre).
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(""), 6000);
    return () => clearTimeout(t);
  }, [error]);

  const idsValidos = useMemo(
    () => (documentos ?? []).map((d) => d.id).filter((x): x is string => !!x),
    [documentos]
  );
  const todosSeleccionados = idsValidos.length > 0 && idsValidos.every((id) => seleccion.has(id));

  const toggle = (id: string) => {
    setSeleccion((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleTodos = () => {
    setSeleccion(todosSeleccionados ? new Set() : new Set(idsValidos));
  };

  const consultar = async () => {
    if (!authUrl.trim()) { setError("Pega la URL de AuthToken de la DIAN."); return; }
    setConsultando(true);
    setError("");
    setDocumentos(null);
    setSeleccion(new Set());
    try {
      const res = await conReintentos(() => api.dianConsultar({
        auth_url: authUrl.trim(),
        fecha_desde: isoToDian(desde),
        fecha_hasta: isoToDian(hasta),
      }));
      setDocumentos(res.documents);
      // Selección por defecto: todas
      setSeleccion(new Set(res.documents.map((d) => d.id).filter((x): x is string => !!x)));
    } catch (e) {
      setError(limpiarError((e as Error).message));
    } finally {
      setConsultando(false);
    }
  };

  const importar = async () => {
    const ids = [...seleccion];
    if (!ids.length) { setError("Selecciona al menos una factura."); return; }
    setImportando(true);
    setError("");
    setProg({ done: 0, total: ids.length });
    try {
      // Progreso REAL: el backend transmite una línea por factura descargada.
      const facturas = await conReintentos(() =>
        api.dianImportarStream({ auth_url: authUrl.trim(), ids }, (done, total) => setProg({ done, total }))
      );
      if (!facturas.length) {
        setError("No se pudo traer ninguna factura (¿ya causadas o de venta?).");
        return;
      }
      await onImportadas(facturas);
    } catch (e) {
      setError(limpiarError((e as Error).message));
    } finally {
      setImportando(false);
      setProg({ done: 0, total: 0 });
    }
  };

  return (
    <div className="space-y-5">
      {/* Aviso de seguridad / cómo funciona */}
      <div
        className="flex items-start gap-3 rounded-xl border p-4"
        style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}
      >
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--info-text)" }} />
        <div className="text-xs leading-relaxed" style={{ color: "var(--info-text)" }}>
          Inicia sesión en el portal de la DIAN, copia la <strong>URL de AuthToken</strong> y pégala aquí.
          El sistema trae tus <strong>facturas recibidas</strong> del rango que elijas — sin descargar archivos.
          Tu token es temporal y no se guarda.
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

      {/* Periodo: presets rápidos + rango personalizado */}
      <div className="space-y-2.5">
        <label className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <CalendarDays className="h-4 w-4" style={{ color: "var(--brand)" }} /> Periodo
        </label>

        {/* Presets */}
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => {
            const active = presetActivo === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => aplicarPreset(p)}
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

        {/* Rango personalizado (mismo date picker que el historial) */}
        <div className="flex flex-wrap items-end gap-2">
          <DatePicker label="Desde" value={desde} onChange={setDesde} max={hasta} />
          <span className="pb-2 text-xs" style={{ color: "var(--text-muted)" }}>hasta</span>
          <DatePicker label="Hasta" value={hasta} onChange={setHasta} min={desde} max={hoyISO(0)} />
        </div>
      </div>

      <Button onClick={consultar} disabled={consultando || importando} size="lg" className="gap-2">
        {consultando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        {consultando ? "Consultando DIAN…" : "Consultar facturas"}
      </Button>

      {/* Reintento en curso — cuenta regresiva visible */}
      {reintentoEn > 0 && (
        <div
          className="flex items-center gap-3 rounded-xl border p-4"
          style={{ borderColor: "var(--warning-border)", backgroundColor: "var(--warning-bg)" }}
          role="status"
        >
          <Loader2 className="h-5 w-5 shrink-0 animate-spin" style={{ color: "var(--warning-text)" }} />
          <div className="flex-1">
            <p className="text-sm font-semibold" style={{ color: "var(--warning-text)" }}>
              Conexión inestable con la DIAN
            </p>
            <p className="mt-0.5 text-sm" style={{ color: "var(--warning-text)", opacity: 0.9 }}>
              Reintentando en {reintentoEn}s…
            </p>
          </div>
        </div>
      )}

      {/* Error — alerta amable */}
      {error && (
        <div
          className="flex items-start gap-3 rounded-xl border p-4"
          style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)" }}
          role="alert"
        >
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: "color-mix(in srgb, var(--error) 15%, transparent)" }}
          >
            <AlertTriangle className="h-5 w-5" style={{ color: "var(--error-text)" }} />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold" style={{ color: "var(--error-text)" }}>
              No pudimos consultar la DIAN
            </p>
            <p className="mt-0.5 text-sm" style={{ color: "var(--error-text)", opacity: 0.9 }}>
              {error}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setError("")}
            className="shrink-0 rounded-md p-1 transition-opacity hover:opacity-70"
            style={{ color: "var(--error-text)" }}
            aria-label="Cerrar aviso"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Resultados */}
      {documentos && (
        <div className="space-y-3">
          {documentos.length === 0 ? (
            <p className="rounded-lg border py-6 text-center text-sm" style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}>
              No se encontraron facturas recibidas en ese rango.
            </p>
          ) : (
            <>
              <div className="flex items-center gap-2 rounded-lg px-3 py-2" style={{ backgroundColor: "var(--success-bg)", border: "1px solid var(--success-border)" }}>
                <CheckSquare className="h-4 w-4 shrink-0" style={{ color: "var(--success-text)" }} />
                <p className="text-sm font-medium" style={{ color: "var(--success-text)" }}>
                  Se encontraron {documentos.length} factura{documentos.length !== 1 ? "s" : ""} recibida{documentos.length !== 1 ? "s" : ""}
                </p>
              </div>

              <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)" }}>
                <div className="flex items-center justify-between px-4 py-2.5" style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border-soft)" }}>
                  <button type="button" onClick={toggleTodos} className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
                    {todosSeleccionados ? <CheckSquare className="h-4 w-4" style={{ color: "var(--brand)" }} /> : <Square className="h-4 w-4" />}
                    {seleccion.size} de {documentos.length} seleccionada{documentos.length !== 1 ? "s" : ""}
                  </button>
                </div>
                <div className="overflow-y-auto" style={{ maxHeight: "320px" }}>
                  {documentos.map((d, i) => {
                    const checked = !!d.id && seleccion.has(d.id);
                    return (
                      <button
                        type="button"
                        key={d.id ?? i}
                        onClick={() => d.id && toggle(d.id)}
                        disabled={!d.id}
                        className="flex w-full items-center gap-3 border-b px-4 py-2.5 text-left last:border-b-0 transition-colors hover:opacity-90 disabled:opacity-40"
                        style={{ borderColor: "var(--border-soft)", backgroundColor: checked ? "color-mix(in srgb, var(--brand) 8%, transparent)" : "var(--bg-surface)" }}
                      >
                        {checked ? <CheckSquare className="h-4 w-4 shrink-0" style={{ color: "var(--brand)" }} /> : <Square className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />}
                        <span className="w-24 shrink-0 truncate font-mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{d.numero}</span>
                        <span className="flex-1 truncate text-sm" style={{ color: "var(--text-secondary)" }}>{d.proveedor || "—"}</span>
                        <span className="shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>{d.fecha}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {importando ? (
                (() => {
                  const total = prog.total || seleccion.size;
                  const pct = total ? Math.round((prog.done / total) * 100) : 0;
                  return (
                    <div className="rounded-xl border p-4 space-y-2" style={{ borderColor: "var(--brand)", backgroundColor: "color-mix(in srgb, var(--brand) 6%, transparent)" }}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="flex items-center gap-2 font-medium" style={{ color: "var(--text-primary)" }}>
                          <Download className="h-4 w-4" style={{ color: "var(--brand)" }} />
                          Descargando {prog.done} de {total} factura{total !== 1 ? "s" : ""} de la DIAN…
                        </span>
                        <span className="font-mono font-semibold tabular-nums" style={{ color: "var(--brand)" }}>{pct}%</span>
                      </div>
                      <div className="h-2.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--bg-elevated)" }}>
                        <div
                          className="h-full rounded-full transition-all duration-300 ease-out"
                          style={{ width: `${pct}%`, background: "linear-gradient(90deg, var(--brand), var(--brand-accent, var(--brand)))" }}
                        />
                      </div>
                    </div>
                  );
                })()
              ) : (
                <Button onClick={importar} disabled={seleccion.size === 0} size="lg" className="w-full gap-2 sm:w-auto">
                  <Download className="h-4 w-4" />
                  {`Traer ${seleccion.size} factura${seleccion.size !== 1 ? "s" : ""} y causar`}
                </Button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
