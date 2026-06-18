"use client";
import * as React from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface Option {
  value: string;
  label: string;
}

interface ComboboxProps {
  options: Option[];
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Buscar...",
  disabled,
  className,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const ref = React.useRef<HTMLDivElement>(null);

  const selected = options.find((o) => o.value === value);

  const filtered = query
    ? options.filter(
        (o) =>
          o.label.toLowerCase().includes(query.toLowerCase()) ||
          o.value.toLowerCase().includes(query.toLowerCase())
      )
    : options;

  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        title={selected?.label}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-lg border px-3 text-sm transition-colors",
          "focus:outline-none focus:ring-2",
          "disabled:cursor-not-allowed disabled:opacity-40",
          selected ? "" : ""
        )}
        style={{
          borderColor: "var(--border-soft)",
          backgroundColor: "var(--bg-surface)",
          color: selected ? "var(--text-primary)" : "var(--text-muted)",
          outlineColor: "var(--ring)",
        }}
      >
        <span className="truncate">{selected ? selected.label : placeholder}</span>
        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
      </button>

      {open && (
        <div
          className="absolute z-50 mt-1 w-full rounded-lg border shadow-xl"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
        >
          <div className="flex items-center gap-2 border-b px-3 py-2" style={{ borderColor: "var(--border-soft)" }}>
            <Search className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Escribe para filtrar..."
              className="flex-1 bg-transparent text-sm focus:outline-none"
              style={{ color: "var(--text-primary)" }}
            />
          </div>
          <div className="max-h-60 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="py-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin resultados</p>
            ) : (
              filtered.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  title={opt.label}
                  onClick={() => {
                    onChange(opt.value);
                    setQuery("");
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors",
                    opt.value === value ? "" : ""
                  )}
                  style={{
                    backgroundColor:
                      opt.value === value
                        ? "color-mix(in srgb, var(--brand) 18%, transparent)"
                        : "transparent",
                    color: opt.value === value ? "var(--brand)" : "var(--text-secondary)",
                  }}
                >
                  <Check
                    className={cn("h-4 w-4 shrink-0", opt.value === value ? "opacity-100" : "opacity-0")}
                    style={{ color: "var(--brand)" }}
                  />
                  <span className="truncate">{opt.label}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
