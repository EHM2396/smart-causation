"use client";

import { useState, useMemo, useCallback } from "react";
import { Search, ChevronLeft, ChevronRight, Plus, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export const PAGE_SIZES = [5, 10, 20, 50] as const;
export type PageSize = (typeof PAGE_SIZES)[number];
export type SortDir = "asc" | "desc";

interface UseDataTableOptions<T> {
  defaultPageSize?: PageSize;
  sortFns?: Record<string, (a: T, b: T) => number>;
  defaultSort?: { col: string; dir: SortDir };
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useDataTable<T>(
  data: T[],
  searchFn: (item: T, query: string) => boolean,
  options?: UseDataTableOptions<T>
) {
  const { defaultPageSize = 10, sortFns, defaultSort } = options ?? {};

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(defaultPageSize);
  const [sortCol, setSortCol] = useState<string | null>(defaultSort?.col ?? null);
  const [sortDir, setSortDir] = useState<SortDir>(defaultSort?.dir ?? "asc");

  const filtered = useMemo(() => {
    let result = data;
    if (search.trim()) {
      const q = search.toLowerCase().trim();
      result = result.filter((item) => searchFn(item, q));
    }
    if (sortCol && sortFns?.[sortCol]) {
      const fn = sortFns[sortCol];
      result = [...result].sort((a, b) =>
        sortDir === "asc" ? fn(a, b) : fn(b, a)
      );
    }
    return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, search, sortCol, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const rows = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  const handleSearch = useCallback((v: string) => {
    setSearch(v);
    setPage(1);
  }, []);

  const handlePageSize = useCallback((s: PageSize) => {
    setPageSize(s);
    setPage(1);
  }, []);

  const handleSort = useCallback(
    (col: string) => {
      setSortDir((prev) => (sortCol === col ? (prev === "asc" ? "desc" : "asc") : "asc"));
      setSortCol(col);
      setPage(1);
    },
    [sortCol]
  );

  return {
    search,
    onSearch: handleSearch,
    page: safePage,
    onPage: setPage,
    pageSize,
    onPageSize: handlePageSize,
    totalPages,
    rows,
    totalFiltered: filtered.length,
    total: data.length,
    sortCol,
    sortDir,
    onSort: handleSort,
  };
}

// ─── Sortable column header ───────────────────────────────────────────────────

interface SortableThProps {
  label: string;
  col: string;
  sortCol: string | null;
  sortDir: SortDir;
  onSort: (col: string) => void;
}

export function SortableTh({ label, col, sortCol, sortDir, onSort }: SortableThProps) {
  const active = sortCol === col;
  return (
    <th
      onClick={() => onSort(col)}
      className="cursor-pointer select-none px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide group"
      style={{ color: active ? "var(--brand)" : "var(--text-muted)" }}
    >
      <div className="flex items-center gap-1">
        {label}
        <span className="transition-opacity" style={{ opacity: active ? 1 : 0.35 }}>
          {!active ? (
            <ChevronsUpDown className="h-3 w-3" />
          ) : sortDir === "asc" ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
        </span>
      </div>
    </th>
  );
}

// ─── Filter chips ─────────────────────────────────────────────────────────────

interface FilterChipsProps {
  label: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}

export function FilterChips({ label, options, value, onChange }: FilterChipsProps) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
        {label}:
      </span>
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className="rounded-full px-2.5 py-0.5 text-xs font-medium transition-all"
            style={{
              backgroundColor: active
                ? "color-mix(in srgb, var(--brand) 15%, transparent)"
                : "var(--bg-elevated)",
              color: active ? "var(--brand)" : "var(--text-muted)",
              border: `1px solid ${active ? "var(--brand)" : "var(--border-soft)"}`,
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// ─── Shell Component ──────────────────────────────────────────────────────────

interface DataTableShellProps {
  title: string;
  total: number;
  totalFiltered: number;
  search: string;
  onSearch: (v: string) => void;
  page: number;
  pageSize: PageSize;
  totalPages: number;
  onPage: (p: number) => void;
  onPageSize: (s: PageSize) => void;
  onAdd?: () => void;
  addLabel?: string;
  searchPlaceholder?: string;
  filters?: React.ReactNode;
  children: React.ReactNode;
}

export function DataTableShell({
  title,
  total,
  totalFiltered,
  search,
  onSearch,
  page,
  pageSize,
  totalPages,
  onPage,
  onPageSize,
  onAdd,
  addLabel = "Agregar",
  searchPlaceholder = "Buscar...",
  filters,
  children,
}: DataTableShellProps) {
  const showing = totalFiltered < total ? `${totalFiltered} de ${total}` : `${total}`;

  return (
    <div
      className="overflow-hidden rounded-xl border"
      style={{
        borderColor: "var(--border-soft)",
        backgroundColor: "var(--bg-surface)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      {/* Header: title + search + add */}
      <div
        className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
      >
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {title}{" "}
          <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
            ({showing})
          </span>
        </span>

        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
              style={{ color: "var(--text-muted)" }}
            />
            <input
              type="text"
              value={search}
              onChange={(e) => onSearch(e.target.value)}
              placeholder={searchPlaceholder}
              className="h-8 rounded-lg border py-0 pl-8 pr-3 text-xs outline-none transition-colors"
              style={{
                width: "190px",
                borderColor: "var(--border-soft)",
                backgroundColor: "var(--bg-surface)",
                color: "var(--text-primary)",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "var(--brand)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-soft)")}
            />
          </div>

          {/* Add button */}
          {onAdd && (
            <button
              onClick={onAdd}
              className="flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
              style={{
                backgroundColor: "color-mix(in srgb, var(--brand) 12%, transparent)",
                color: "var(--brand)",
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              {addLabel}
            </button>
          )}
        </div>
      </div>

      {/* Filter chips row */}
      {filters && (
        <div
          className="border-b px-4 py-2"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
        >
          {filters}
        </div>
      )}

      {/* Table content */}
      <div className="overflow-x-auto">{children}</div>

      {/* Footer: page size + pagination */}
      <div
        className="flex flex-wrap items-center justify-between gap-2 border-t px-4 py-3"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
      >
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <span>Mostrar</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSize(Number(e.target.value) as PageSize)}
            className="rounded-md border px-2 py-0.5 text-xs outline-none"
            style={{
              borderColor: "var(--border-soft)",
              backgroundColor: "var(--bg-surface)",
              color: "var(--text-primary)",
            }}
          >
            {PAGE_SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span>por página</span>
        </div>

        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <span>
            Pág.{" "}
            <strong style={{ color: "var(--text-primary)" }}>{page}</strong>{" "}
            / {totalPages}
          </span>
          <button
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
            className="flex h-7 w-7 items-center justify-center rounded-md border transition-colors disabled:cursor-not-allowed disabled:opacity-40"
            style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)" }}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            disabled={page >= totalPages}
            onClick={() => onPage(page + 1)}
            className="flex h-7 w-7 items-center justify-center rounded-md border transition-colors disabled:cursor-not-allowed disabled:opacity-40"
            style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)" }}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
