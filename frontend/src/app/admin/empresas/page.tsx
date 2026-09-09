"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminEmpresa } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { DataTableShell, SortableTh, useDataTable } from "@/components/ui/data-table";
import { Building2 } from "lucide-react";

export default function AdminEmpresasPage() {
  const { data: cuenta } = useQuery({ queryKey: ["admin-cuenta"], queryFn: api.adminCuenta });
  const { data: empresas = [] } = useQuery({ queryKey: ["admin-empresas"], queryFn: api.adminEmpresas });

  const dt = useDataTable<AdminEmpresa>(
    empresas,
    (e, q) => e.nombre.toLowerCase().includes(q) || (e.nit ?? "").toLowerCase().includes(q) || (e.creada_por ?? "").toLowerCase().includes(q),
    { sortFns: { nombre: (a, b) => a.nombre.localeCompare(b.nombre), creada_por: (a, b) => (a.creada_por ?? "").localeCompare(b.creada_por ?? "") }, defaultSort: { col: "nombre", dir: "asc" } }
  );

  const lim = cuenta?.limite_empresas;
  const limTxt = lim ? (lim.ilimitado ? `${empresas.length}` : `${lim.actuales ?? 0} / ${lim.max}`) : "—";

  return (
    <div className="px-4 py-6 lg:px-8 lg:py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Empresas</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Empresas que han creado tus usuarios · <span className="font-medium tabular-nums">{limTxt}</span>.
          Cada usuario crea sus propias empresas; aquí solo las consultas.
        </p>
      </div>

      <DataTableShell
        title="Empresas de la cuenta"
        total={dt.total}
        totalFiltered={dt.totalFiltered}
        search={dt.search}
        onSearch={dt.onSearch}
        page={dt.page}
        pageSize={dt.pageSize}
        totalPages={dt.totalPages}
        onPage={dt.onPage}
        onPageSize={dt.onPageSize}
        searchPlaceholder="Buscar por nombre, NIT o usuario..."
      >
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
              <SortableTh label="Empresa" col="nombre" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>NIT</th>
              <SortableTh label="Creada por" col="creada_por" sortCol={dt.sortCol} sortDir={dt.sortDir} onSort={dt.onSort} />
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>Estado</th>
            </tr>
          </thead>
          <tbody>
            {dt.rows.map((e, idx) => (
              <tr key={e.id} className="tr-row" style={{ borderBottom: idx < dt.rows.length - 1 ? "1px solid var(--border-soft)" : "none" }}>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ backgroundColor: "var(--info-bg)", color: "var(--info-text)" }}>
                      <Building2 className="h-3.5 w-3.5" />
                    </div>
                    <span className="font-medium" style={{ color: "var(--text-primary)" }}>{e.nombre}</span>
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{e.nit || "—"}</td>
                <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{e.creada_por || "—"}</td>
                <td className="px-4 py-3"><Badge variant={e.activa ? "success" : "default"}>{e.activa ? "Activa" : "Inactiva"}</Badge></td>
              </tr>
            ))}
            {dt.rows.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Tus usuarios aún no han creado empresas.</td></tr>
            )}
          </tbody>
        </table>
      </DataTableShell>
    </div>
  );
}
