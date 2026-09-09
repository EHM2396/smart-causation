"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminUsuario, AdminLimite } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DataTableShell, SortableTh, useDataTable } from "@/components/ui/data-table";
import { Users, Building2, Gauge, Tag, Loader2, Pencil, AlertTriangle } from "lucide-react";

function limiteTexto(l?: AdminLimite): string {
  if (!l) return "—";
  if (l.ilimitado) return `${l.actuales ?? ""}`.trim() || "∞";
  return `${l.actuales ?? 0} / ${l.max}`;
}
function limiteAlcanzado(l?: AdminLimite): boolean {
  return !!l && !l.ilimitado && typeof l.max === "number" && (l.actuales ?? 0) >= l.max;
}
function errDetalle(e: unknown): string {
  const raw = (e as Error).message ?? "";
  const j = raw.replace(/^API\s+\d+:\s*/, "");
  try { const p = JSON.parse(j); if (typeof p?.detail === "string") return p.detail; } catch {}
  return j || "Ocurrió un error";
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

export default function AdminUsuariosPage() {
  const qc = useQueryClient();
  const { data: cuenta } = useQuery({ queryKey: ["admin-cuenta"], queryFn: api.adminCuenta });
  const { data: usuarios = [] } = useQuery({ queryKey: ["admin-usuarios"], queryFn: api.adminUsuarios });
  const [dlg, setDlg] = useState<null | { mode: "crear" } | { mode: "editar"; u: AdminUsuario }>(null);

  const dt = useDataTable<AdminUsuario>(
    usuarios,
    (u, q) => u.nombre.toLowerCase().includes(q) || u.email.toLowerCase().includes(q),
    { sortFns: { nombre: (a, b) => a.nombre.localeCompare(b.nombre) }, defaultSort: { col: "nombre", dir: "asc" } }
  );

  const consumo = cuenta?.consumo;
  const causTxt = consumo ? (consumo.ilimitado ? "∞" : `${consumo.usadas_mes} / ${consumo.cupo_mes}`) : "—";
  const topeUsuarios = limiteAlcanzado(cuenta?.limite_usuarios);

  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Usuarios</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Crea usuarios causadores y reparte entre ellos las causaciones y empresas que permite tu plan.
        </p>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi icon={Tag} label="Plan" value={consumo?.plan ?? "—"} accent="#4F46E5" />
        <Kpi icon={Users} label="Usuarios" value={limiteTexto(cuenta?.limite_usuarios)} accent="#7c3aed" />
        <Kpi icon={Building2} label="Empresas" value={limiteTexto(cuenta?.limite_empresas)} accent="#0ea5e9" />
        <Kpi icon={Gauge} label="Causaciones / mes" value={causTxt} accent="#059669" />
      </div>

      {topeUsuarios && (
        <div className="mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning-border)", color: "var(--warning-text)" }}>
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Alcanzaste el máximo de usuarios de tu plan. Desactiva alguno o mejora tu plan para agregar más.
        </div>
      )}

      <DataTableShell
        title="Usuarios causadores"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        onAdd={topeUsuarios ? undefined : () => setDlg({ mode: "crear" })}
        addLabel="Nuevo usuario"
        searchPlaceholder="Buscar por nombre o email..."
      >
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <SortableTh label="Usuario" col="nombre" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Causaciones/mes</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Empresas</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Estado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {dt.rows.map((u, idx) => (
              <tr key={u.id} className="tr-row" style={{ borderBottom: idx < dt.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}>
                <td className="px-4 py-3">
                  <p className="font-medium" style={{ color: "var(--text-primary)" }}>{u.nombre}</p>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>{u.email}</p>
                </td>
                <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{u.cupo_mes ?? "Sin tope"}</td>
                <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                  {u.empresas_creadas} / {u.max_empresas ?? "∞"}
                </td>
                <td className="px-4 py-3"><Badge variant={u.activo ? "success" : "default"}>{u.activo ? "Activo" : "Inactivo"}</Badge></td>
                <td className="px-4 py-3 text-right">
                  <Button variant="outline" size="sm" onClick={() => setDlg({ mode: "editar", u })} className="gap-1">
                    <Pencil className="h-3.5 w-3.5" /> Editar
                  </Button>
                </td>
              </tr>
            ))}
            {dt.rows.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Aún no has creado usuarios.</td></tr>
            )}
          </tbody>
        </table>
      </DataTableShell>

      {dlg && (
        <UsuarioDialog
          mode={dlg.mode}
          usuario={dlg.mode === "editar" ? dlg.u : undefined}
          planEmpresas={cuenta?.limite_empresas?.ilimitado ? null : (cuenta?.limite_empresas?.max ?? null)}
          planCausaciones={cuenta?.consumo?.ilimitado ? null : (cuenta?.consumo?.cupo_mes ?? null)}
          onClose={() => setDlg(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["admin-usuarios"] });
            qc.invalidateQueries({ queryKey: ["admin-cuenta"] });
            setDlg(null);
          }}
        />
      )}
    </div>
  );
}

function UsuarioDialog({
  mode, usuario, planEmpresas, planCausaciones, onClose, onSaved,
}: {
  mode: "crear" | "editar";
  usuario?: AdminUsuario;
  planEmpresas: number | null;      // total de empresas del plan (null = ilimitado)
  planCausaciones: number | null;   // total de causaciones/mes del plan (null = ilimitado)
  onClose: () => void;
  onSaved: () => void;
}) {
  const editar = mode === "editar";
  const [email, setEmail] = useState(usuario?.email ?? "");
  const [nombre, setNombre] = useState(usuario?.nombre ?? "");
  const [password, setPassword] = useState("");
  const [activo, setActivo] = useState(usuario?.activo ?? true);
  const [cupoTexto, setCupoTexto] = useState(usuario?.cupo_mes != null ? String(usuario.cupo_mes) : "");
  const [empresasTexto, setEmpresasTexto] = useState(usuario?.max_empresas != null ? String(usuario.max_empresas) : "");
  const [err, setErr] = useState("");

  const aNum = (t: string): number | null => {
    const s = t.trim();
    if (s === "") return null;
    const n = Number(s);
    return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
  };

  const mut = useMutation({
    mutationFn: async () => {
      if (editar && usuario) {
        return api.adminActualizarUsuario(usuario.id, { activo, cupo_mes: aNum(cupoTexto), max_empresas: aNum(empresasTexto) });
      }
      return api.adminCrearUsuario({ email: email.trim(), nombre: nombre.trim(), password, cupo_mes: aNum(cupoTexto), max_empresas: aNum(empresasTexto) });
    },
    onSuccess: onSaved,
    onError: (e) => setErr(errDetalle(e)),
  });

  const submit = () => {
    setErr("");
    if (!editar) {
      if (!email.includes("@")) return setErr("Escribe un correo válido.");
      if (nombre.trim().length < 1) return setErr("Escribe el nombre.");
      if (password.length < 8) return setErr("La contraseña debe tener al menos 8 caracteres.");
    }
    mut.mutate();
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{editar ? "Editar usuario" : "Nuevo usuario"}</DialogTitle>
          <DialogDescription>
            {editar ? "Ajusta cuántas causaciones y empresas puede usar este usuario." : "Crea un usuario causador y asígnale cuántas causaciones y empresas puede usar."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 pt-1">
          {!editar ? (
            <>
              <div className="space-y-1"><Label>Correo</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="usuario@empresa.com" /></div>
              <div className="space-y-1"><Label>Nombre</Label><Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre completo" /></div>
              <div className="space-y-1"><Label>Contraseña</Label><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Mínimo 8 caracteres" /></div>
            </>
          ) : (
            <div className="rounded-lg border px-3 py-2 text-sm" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <span className="font-medium" style={{ color: "var(--text-primary)" }}>{usuario?.nombre}</span>
              <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>{usuario?.email}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Causaciones / mes</Label>
              <Input type="number" min={0} value={cupoTexto} onChange={(e) => setCupoTexto(e.target.value)} placeholder="Sin tope" />
            </div>
            <div className="space-y-1">
              <Label>Máximo de empresas</Label>
              <Input type="number" min={0} value={empresasTexto} onChange={(e) => setEmpresasTexto(e.target.value)} placeholder="Sin tope" />
            </div>
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Tu plan permite en total <strong>{planCausaciones ?? "∞"}</strong> causaciones/mes y <strong>{planEmpresas ?? "∞"}</strong> empresas.
            Repártelas como quieras (puedes darle todo a uno solo). Si lo dejas vacío, el usuario queda limitado
            solo por el total del plan — <strong>nunca puede pasar del total del plan</strong>.
          </p>

          {editar && (
            <label className="flex cursor-pointer items-center gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Usuario activo
            </label>
          )}

          {err && (
            <div className="flex items-start gap-1.5 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error-text)" }}>
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {err}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} disabled={mut.isPending}>Cancelar</Button>
            <Button onClick={submit} disabled={mut.isPending} className="gap-1.5">
              {mut.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {editar ? "Guardar" : "Crear usuario"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
