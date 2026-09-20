"use client";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminEmpresa, AdminUsuario } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { DataTableShell, useDataTable } from "@/components/ui/data-table";
import {
  Building2, ChevronDown, ChevronsDownUp, ChevronsUpDown, Landmark, Users2,
} from "lucide-react";

// ─── KPI ──────────────────────────────────────────────────────────────────────

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

// ─── Un causador + sus empresas ──────────────────────────────────────────────

interface GrupoUsuario {
  key: string;
  nombre: string;
  email: string | null;
  empresas: AdminEmpresa[];
}

function iniciales(nombre: string): string {
  const partes = nombre.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  return (partes[0][0] + (partes[1]?.[0] ?? "")).toUpperCase();
}

function GrupoRow({ grupo, expandido, onToggle }: { grupo: GrupoUsuario; expandido: boolean; onToggle: () => void }) {
  const activas = grupo.empresas.filter((e) => e.activa).length;
  const sinEmpresas = grupo.empresas.length === 0;

  return (
    <div style={{ borderBottom: "1px solid var(--border-soft)" }}>
      <button
        type="button"
        onClick={onToggle}
        disabled={sinEmpresas}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors"
        style={{ cursor: sinEmpresas ? "default" : "pointer" }}
        onMouseEnter={(e) => { if (!sinEmpresas) (e.currentTarget as HTMLElement).style.backgroundColor = "var(--bg-elevated)"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
          style={{ backgroundColor: "var(--brand-muted)", color: "var(--brand)" }}
        >
          {iniciales(grupo.nombre)}
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>{grupo.nombre}</p>
          {grupo.email && (
            <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>{grupo.email}</p>
          )}
        </div>

        {sinEmpresas ? (
          <span className="shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>Sin empresas creadas</span>
        ) : (
          <>
            <Badge variant={activas === grupo.empresas.length ? "success" : "warning"}>
              {grupo.empresas.length} empresa{grupo.empresas.length === 1 ? "" : "s"}
              {activas < grupo.empresas.length && ` · ${activas} activa${activas === 1 ? "" : "s"}`}
            </Badge>
            <ChevronDown
              className="h-4 w-4 shrink-0 transition-transform duration-200"
              style={{ color: "var(--text-muted)", transform: expandido ? "rotate(180deg)" : "rotate(0deg)" }}
            />
          </>
        )}
      </button>

      {!sinEmpresas && expandido && (
        <div className="pb-3 pl-[52px] pr-4">
          <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border-soft)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border-soft)" }}>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Empresa</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>NIT</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {grupo.empresas.map((e, idx) => (
                  <tr key={e.id} style={{ borderBottom: idx < grupo.empresas.length - 1 ? "1px solid var(--border-soft)" : "none" }}>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} />
                        <span style={{ color: "var(--text-primary)" }}>{e.nombre}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{e.nit || "—"}</td>
                    <td className="px-3 py-2"><Badge variant={e.activa ? "success" : "default"}>{e.activa ? "Activa" : "Inactiva"}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Página ───────────────────────────────────────────────────────────────────

export default function AdminEmpresasPage() {
  const { data: cuenta } = useQuery({ queryKey: ["admin-cuenta"], queryFn: api.adminCuenta });
  const { data: usuarios = [] } = useQuery({ queryKey: ["admin-usuarios"], queryFn: api.adminUsuarios });
  const { data: empresas = [] } = useQuery({ queryKey: ["admin-empresas"], queryFn: api.adminEmpresas });

  const [expandidos, setExpandidos] = useState<Set<string>>(new Set());

  // Un grupo por causador (aunque no haya creado ninguna empresa todavía, para
  // que el admin vea de un vistazo quién le falta empezar) + un grupo aparte
  // para empresas huérfanas (de antes de que owner_id fuera obligatorio).
  const grupos = useMemo<GrupoUsuario[]>(() => {
    const porUsuario = new Map<number, GrupoUsuario>();
    for (const u of usuarios as AdminUsuario[]) {
      porUsuario.set(u.id, { key: `u-${u.id}`, nombre: u.nombre, email: u.email, empresas: [] });
    }
    const huerfanas: AdminEmpresa[] = [];
    for (const e of empresas as AdminEmpresa[]) {
      const g = e.owner_id != null ? porUsuario.get(e.owner_id) : undefined;
      if (g) g.empresas.push(e);
      else huerfanas.push(e);
    }
    const lista = Array.from(porUsuario.values());
    if (huerfanas.length > 0) {
      lista.push({ key: "sin-usuario", nombre: "Sin usuario asociado", email: null, empresas: huerfanas });
    }
    // Primero quienes tienen empresas (más primero), después los que no.
    return lista.sort((a, b) => b.empresas.length - a.empresas.length || a.nombre.localeCompare(b.nombre));
  }, [usuarios, empresas]);

  const dt = useDataTable<GrupoUsuario>(
    grupos,
    (g, q) =>
      g.nombre.toLowerCase().includes(q) ||
      (g.email ?? "").toLowerCase().includes(q) ||
      g.empresas.some((e) => e.nombre.toLowerCase().includes(q) || (e.nit ?? "").toLowerCase().includes(q)),
    { defaultPageSize: 20 }
  );

  const conEmpresas = grupos.filter((g) => g.empresas.length > 0);
  const totalActivas = empresas.filter((e) => e.activa).length;
  const lim = cuenta?.limite_empresas;
  const limTxt = lim ? (lim.ilimitado ? `${empresas.length}` : `${lim.actuales ?? 0} / ${lim.max}`) : `${empresas.length}`;

  // Si hay búsqueda, se expande todo lo que coincidió (para que el resultado se
  // vea sin un clic más); si no hay búsqueda, manda lo que el usuario tocó.
  const buscando = dt.search.trim().length > 0;
  const estaExpandido = (key: string) => buscando || expandidos.has(key);
  const toggle = (key: string) =>
    setExpandidos((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  const expandirTodo = () => setExpandidos(new Set(conEmpresas.map((g) => g.key)));
  const colapsarTodo = () => setExpandidos(new Set());

  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Empresas</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Agrupadas por el usuario que las creó. Cada causador crea sus propias empresas;
          aquí solo las consultas.
        </p>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={Users2} label="Usuarios con empresas" value={`${conEmpresas.length} / ${usuarios.length}`} accent="#7c3aed" />
        <Kpi icon={Building2} label="Total empresas" value={limTxt} accent="#4F46E5" />
        <Kpi icon={Landmark} label="Activas" value={String(totalActivas)} accent="#059669" />
        <Kpi icon={Landmark} label="Inactivas" value={String(empresas.length - totalActivas)} accent="#dc2626" />
      </div>

      <DataTableShell
        title="Por usuario"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        searchPlaceholder="Buscar por usuario, empresa o NIT..."
        filters={
          <button
            type="button"
            onClick={expandidos.size > 0 ? colapsarTodo : expandirTodo}
            className="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
            style={{ backgroundColor: "color-mix(in srgb, var(--text-muted) 12%, transparent)", color: "var(--text-secondary)" }}
          >
            {expandidos.size > 0 ? <ChevronsDownUp className="h-3.5 w-3.5" /> : <ChevronsUpDown className="h-3.5 w-3.5" />}
            {expandidos.size > 0 ? "Colapsar todo" : "Expandir todo"}
          </button>
        }
      >
        <div>
          {dt.rows.map((g) => (
            <GrupoRow key={g.key} grupo={g} expandido={estaExpandido(g.key)} onToggle={() => toggle(g.key)} />
          ))}
          {dt.rows.length === 0 && (
            <p className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin resultados.</p>
          )}
        </div>
      </DataTableShell>
    </div>
  );
}
