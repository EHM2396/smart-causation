"use client";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmt } from "@/lib/utils";
import { DatePicker } from "@/components/ui/date-picker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { FileSpreadsheet, Users, DollarSign, Download, Loader2, ChevronRight, CalendarDays } from "lucide-react";

function localYMD(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function buildPresets() {
  const now = new Date();
  const y = now.getFullYear(), m = now.getMonth();
  const lunes = new Date(now); lunes.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  return [
    { id: "semana", label: "Esta semana", desde: localYMD(lunes), hasta: localYMD(now) },
    { id: "mes", label: "Este mes", desde: localYMD(new Date(y, m, 1)), hasta: localYMD(now) },
    { id: "anio", label: "Este año", desde: localYMD(new Date(y, 0, 1)), hasta: localYMD(now) },
  ];
}

function Kpi({ icon: Icon, label, value, accent }: { icon: React.ElementType; label: string; value: string; accent: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl px-4 py-3.5" style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-soft)", boxShadow: "var(--shadow-sm)" }}>
      <div className="absolute top-0 left-0 right-0 h-[3px]" style={{ backgroundColor: accent }} />
      <div className="mt-1 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{label}</p>
          <p className="mt-1 truncate text-xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{value}</p>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ backgroundColor: accent + "18" }}>
          <Icon className="h-4 w-4" style={{ color: accent }} />
        </div>
      </div>
    </div>
  );
}

type Fila = { nombre: string; causaciones: number; monto: number };

function TablaResumen({ titulo, filas, onPick }: { titulo: string; filas: Fila[]; onPick?: (idx: number) => void }) {
  const totalC = filas.reduce((s, f) => s + f.causaciones, 0) || 1;
  return (
    <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-card)" }}>
      <div className="border-b px-4 py-3" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{titulo}</span>
        {onPick && <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>· toca un usuario para ver el detalle</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Nombre</th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Causaciones</th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Monto</th>
              {onPick && <th className="w-8" />}
            </tr>
          </thead>
          <tbody>
            {filas.map((f, idx) => (
              <tr key={idx} className="tr-row" style={{ borderBottom: idx < filas.length - 1 ? "1px solid var(--border-soft)" : "none", cursor: onPick ? "pointer" : "default" }}
                onClick={() => onPick?.(idx)}>
                <td className="px-4 py-2.5">
                  <p className="font-medium" style={{ color: "var(--text-primary)" }}>{f.nombre}</p>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--bg-elevated)" }}>
                    <div className="h-full rounded-full" style={{ width: `${Math.round((f.causaciones / totalC) * 100)}%`, backgroundColor: "var(--brand)" }} />
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums" style={{ color: "var(--text-primary)" }}>{f.causaciones}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(f.monto)}</td>
                {onPick && <td className="px-2 text-right"><ChevronRight className="h-4 w-4" style={{ color: "var(--text-muted)" }} /></td>}
              </tr>
            ))}
            {filas.length === 0 && (
              <tr><td colSpan={onPick ? 4 : 3} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin causaciones en este periodo.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function UsuarioDetalleModal({ usuarioId, desde, hasta, onClose }: { usuarioId: number; desde: string; hasta: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({ queryKey: ["admin-usuario-detalle", usuarioId, desde, hasta], queryFn: () => api.adminUsuarioDetalle(usuarioId, desde, hasta) });
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{data?.usuario.nombre ?? "Detalle del usuario"}</DialogTitle>
          <DialogDescription>{data?.usuario.email ?? ""} · causaciones del periodo</DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="py-10 text-center"><Loader2 className="mx-auto h-6 w-6 animate-spin" style={{ color: "var(--brand)" }} /></div>
        ) : (
          <div className="space-y-4 pt-1">
            <div className="grid grid-cols-2 gap-3">
              <Kpi icon={FileSpreadsheet} label="Causaciones" value={String(data?.total ?? 0)} accent="#4F46E5" />
              <Kpi icon={DollarSign} label="Monto" value={fmt(data?.monto ?? 0)} accent="#059669" />
            </div>
            <div>
              <p className="mb-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Por empresa</p>
              <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border-soft)" }}>
                <table className="w-full text-sm">
                  <tbody>
                    {(data?.por_empresa ?? []).map((e, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border-soft)" }}>
                        <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>{e.nombre}</td>
                        <td className="px-3 py-2 text-right font-mono" style={{ color: "var(--text-secondary)" }}>{e.causaciones} · {fmt(e.monto)}</td>
                      </tr>
                    ))}
                    {(data?.por_empresa ?? []).length === 0 && <tr><td className="px-3 py-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin datos.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Causaciones ({data?.detalle.length ?? 0})</p>
              <div className="max-h-64 overflow-y-auto rounded-lg border" style={{ borderColor: "var(--border-soft)" }}>
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border-soft)" }}>
                      {["Fecha", "Empresa", "N° / Proveedor", "Total"].map((h) => (
                        <th key={h} className="px-3 py-2 text-left text-xs font-semibold uppercase" style={{ color: "var(--text-muted)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.detalle ?? []).map((d, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border-soft)" }}>
                        <td className="px-3 py-2 tabular-nums" style={{ color: "var(--text-secondary)" }}>{d.fecha}</td>
                        <td className="px-3 py-2" style={{ color: "var(--text-secondary)" }}>{d.empresa}</td>
                        <td className="px-3 py-2"><span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>{d.numero}</span><span className="ml-1 text-xs" style={{ color: "var(--text-muted)" }}>{d.proveedor}</span></td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmt(d.total)}</td>
                      </tr>
                    ))}
                    {(data?.detalle ?? []).length === 0 && <tr><td colSpan={4} className="px-3 py-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin causaciones.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function AdminDashboardPage() {
  const presets = useMemo(buildPresets, []);
  const [desde, setDesde] = useState(presets[1].desde);
  const [hasta, setHasta] = useState(presets[1].hasta);
  const [descargando, setDescargando] = useState(false);
  const [detalleUid, setDetalleUid] = useState<number | null>(null);

  const presetActivo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id ?? "personalizado";
  const { data } = useQuery({ queryKey: ["admin-dashboard", desde, hasta], queryFn: () => api.adminDashboard(desde, hasta) });

  const descargar = async () => {
    setDescargando(true);
    try {
      const blob = await api.adminInformeXlsx(desde, hasta);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `informe_causaciones_${desde}_a_${hasta}.xlsx`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } finally { setDescargando(false); }
  };

  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Dashboard</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Controla cuánto ha causado cada usuario y de qué empresas, en el periodo que elijas.
          </p>
        </div>
        <Button onClick={descargar} disabled={descargando} variant="outline" className="gap-1.5">
          {descargando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Exportar Excel
        </Button>
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
      </div>

      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Kpi icon={FileSpreadsheet} label="Causaciones (periodo)" value={String(data?.total_causaciones ?? 0)} accent="#4F46E5" />
        <Kpi icon={DollarSign} label="Monto total (periodo)" value={fmt(data?.monto_total ?? 0)} accent="#059669" />
        <Kpi icon={Users} label="Usuarios con causaciones" value={String(data?.por_usuario.length ?? 0)} accent="#7c3aed" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TablaResumen titulo="Por usuario" filas={(data?.por_usuario ?? []).map((f) => ({ nombre: f.nombre, causaciones: f.causaciones, monto: f.monto }))}
          onPick={(idx) => { const uid = data?.por_usuario[idx]?.usuario_id; if (uid != null) setDetalleUid(uid); }} />
        <TablaResumen titulo="Por empresa" filas={(data?.por_empresa ?? []).map((f) => ({ nombre: f.nombre, causaciones: f.causaciones, monto: f.monto }))} />
      </div>

      {detalleUid != null && (
        <UsuarioDetalleModal usuarioId={detalleUid} desde={desde} hasta={hasta} onClose={() => setDetalleUid(null)} />
      )}
    </div>
  );
}
