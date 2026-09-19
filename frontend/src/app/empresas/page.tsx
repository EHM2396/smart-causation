"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminEmpresa } from "@/lib/types";
import { useAuthStore } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DataTableShell, SortableTh, useDataTable } from "@/components/ui/data-table";
import { Building2, Loader2, Pencil, AlertTriangle, Check, Trash2 } from "lucide-react";

function errDetalle(e: unknown): string {
  const raw = (e as Error).message ?? "";
  const j = raw.replace(/^API\s+\d+:\s*/, "");
  try { const p = JSON.parse(j); if (typeof p?.detail === "string") return p.detail; } catch {}
  return j || "Ocurrió un error";
}

export default function MisEmpresasPage() {
  const qc = useQueryClient();
  const empresaId = useAuthStore((s) => s.empresaId);
  const limpiarEmpresa = useAuthStore((s) => s.limpiarEmpresa);
  const { data, isLoading } = useQuery({ queryKey: ["empresas-estado"], queryFn: api.empresasEstado });
  const [dlg, setDlg] = useState<null | { mode: "crear" } | { mode: "editar"; e: AdminEmpresa }>(null);
  const [eliminar, setEliminar] = useState<AdminEmpresa | null>(null);

  const delMut = useMutation({
    mutationFn: (id: number) => api.eliminarEmpresaPropia(id),
    onSuccess: (_r, id) => {
      if (id === empresaId) limpiarEmpresa();   // si borró la empresa activa, vaciar selección
      qc.invalidateQueries({ queryKey: ["empresas-estado"] });
      qc.invalidateQueries({ queryKey: ["mis-empresas"] });
      setEliminar(null);
    },
  });

  const empresas = data?.empresas ?? [];
  const puedeCrear = data?.puede_crear ?? true;

  const dt = useDataTable<AdminEmpresa>(
    empresas,
    (e, q) => e.nombre.toLowerCase().includes(q) || (e.nit ?? "").toLowerCase().includes(q),
    { sortFns: { nombre: (a, b) => a.nombre.localeCompare(b.nombre) }, defaultSort: { col: "nombre", dir: "asc" } }
  );

  const onSaved = () => {
    qc.invalidateQueries({ queryKey: ["empresas-estado"] });
    qc.invalidateQueries({ queryKey: ["mis-empresas"] });
    setDlg(null);
  };

  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Mis empresas</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Crea y edita las empresas con las que trabajas. Cambia entre ellas desde el selector del menú.
        </p>
      </div>

      {!puedeCrear && (
        <div className="mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning-border)", color: "var(--warning-text)" }}>
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Alcanzaste el máximo de empresas que puedes crear. Pídele más a tu administrador o mejora tu plan.
        </div>
      )}

      <DataTableShell
        title="Empresas"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        onAdd={puedeCrear ? () => setDlg({ mode: "crear" }) : undefined}
        addLabel="Nueva empresa"
        searchPlaceholder="Buscar por nombre o NIT..."
      >
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <SortableTh label="Empresa" col="nombre" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>NIT</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Activa</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center"><Loader2 className="mx-auto h-5 w-5 animate-spin" style={{ color: "var(--brand)" }} /></td></tr>
            ) : dt.rows.map((e, idx) => (
              <tr key={e.id} className="tr-row" style={{ borderBottom: idx < dt.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ backgroundColor: "var(--info-bg)", color: "var(--info-text)" }}>
                      <Building2 className="h-3.5 w-3.5" />
                    </div>
                    <span className="font-medium" style={{ color: "var(--text-primary)" }}>{e.nombre}</span>
                    {e.id === empresaId && <Badge variant="info"><Check className="mr-0.5 inline h-2.5 w-2.5" /> Activa</Badge>}
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{e.nit || "—"}</td>
                <td className="px-4 py-3"><Badge variant={e.activa ? "success" : "default"}>{e.activa ? "Sí" : "No"}</Badge></td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => setDlg({ mode: "editar", e })} className="gap-1">
                      <Pencil className="h-3.5 w-3.5" /> Editar
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setEliminar(e)} className="gap-1"
                      style={{ color: "var(--error)", borderColor: "var(--error-border)" }}>
                      <Trash2 className="h-3.5 w-3.5" /> Eliminar
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
            {!isLoading && dt.rows.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Aún no has creado empresas.</td></tr>
            )}
          </tbody>
        </table>
      </DataTableShell>

      {dlg && (
        <EmpresaDialog mode={dlg.mode} empresa={dlg.mode === "editar" ? dlg.e : undefined} onClose={() => setDlg(null)} onSaved={onSaved} />
      )}

      {eliminar && (
        <Dialog open onOpenChange={(o) => { if (!o) setEliminar(null); }}>
          <DialogContent className="max-w-sm">
            <DialogHeader>
              <DialogTitle>Eliminar empresa</DialogTitle>
              <DialogDescription>
                ¿Seguro que quieres eliminar <strong>{eliminar.nombre}</strong>? Dejará de aparecer en tu lista y
                se liberará un cupo. El histórico de causaciones de esta empresa se conserva.
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setEliminar(null)} disabled={delMut.isPending}>Cancelar</Button>
              <Button onClick={() => delMut.mutate(eliminar.id)} disabled={delMut.isPending} className="gap-1.5"
                style={{ backgroundColor: "var(--error)", color: "#fff" }}>
                {delMut.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <Trash2 className="h-3.5 w-3.5" /> Eliminar
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function EmpresaDialog({
  mode, empresa, onClose, onSaved,
}: {
  mode: "crear" | "editar";
  empresa?: AdminEmpresa;
  onClose: () => void;
  onSaved: () => void;
}) {
  const editar = mode === "editar";
  const [nombre, setNombre] = useState(empresa?.nombre ?? "");
  const [nit, setNit] = useState(empresa?.nit ?? "");
  const [err, setErr] = useState("");

  const mut = useMutation({
    mutationFn: () => editar && empresa
      ? api.editarEmpresaPropia(empresa.id, { nombre: nombre.trim(), nit: nit.trim() })
      : api.crearEmpresaPropia({ nombre: nombre.trim(), nit: nit.trim() }),
    onSuccess: onSaved,
    onError: (e) => setErr(errDetalle(e)),
  });

  const submit = () => {
    setErr("");
    if (nombre.trim().length < 1) return setErr("Escribe el nombre de la empresa.");
    if (nit.trim().length < 1) return setErr("El NIT es obligatorio.");
    mut.mutate();
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{editar ? "Editar empresa" : "Nueva empresa"}</DialogTitle>
          <DialogDescription>{editar ? "Actualiza el nombre y el NIT." : "Crea una empresa para trabajar con ella."}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 pt-1">
          <div className="space-y-1"><Label>Nombre</Label><Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Razón social" /></div>
          <div className="space-y-1"><Label>NIT</Label><Input value={nit} onChange={(e) => setNit(e.target.value)} placeholder="900123456" /></div>
          {err && (
            <div className="flex items-start gap-1.5 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error-text)" }}>
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {err}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} disabled={mut.isPending}>Cancelar</Button>
            <Button onClick={submit} disabled={mut.isPending} className="gap-1.5">
              {mut.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {editar ? "Guardar" : "Crear empresa"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
