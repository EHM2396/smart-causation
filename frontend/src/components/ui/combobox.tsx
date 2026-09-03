"use client";
import * as React from "react";
import { createPortal } from "react-dom";
import { Check, ChevronsUpDown, Search, X } from "lucide-react";
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
  clearable?: boolean;
  /**
   * Cómo se renderiza el dropdown:
   *  - true  (por defecto): se porta a document.body con position:fixed. Necesario
   *    cuando el Combobox vive dentro de contenedores con overflow oculto (p.ej. el
   *    sidebar de configuración) para que el menú no quede recortado.
   *  - false: se renderiza en línea (position:absolute) dentro del propio wrapper.
   *    OBLIGATORIO cuando el Combobox está dentro de un diálogo modal de Radix: un
   *    dropdown portado al body queda FUERA del contenido del diálogo, y Radix
   *    (focus-trap + pointer-events:none en el resto del documento) impide escribir
   *    en el buscador y hacer clic en las opciones.
   */
  portal?: boolean;
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Buscar...",
  disabled,
  className,
  clearable,
  portal = true,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [coords, setCoords] = React.useState({ top: 0, left: 0, width: 0 });
  const [mounted, setMounted] = React.useState(false);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => { setMounted(true); }, []);

  const selected = options.find((o) => o.value === value);

  const filtered = query
    ? options.filter(
        (o) =>
          o.label.toLowerCase().includes(query.toLowerCase()) ||
          o.value.toLowerCase().includes(query.toLowerCase())
      )
    : options;

  const updateCoords = React.useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setCoords({
        top: rect.bottom + 4,
        left: rect.left,
        width: Math.max(rect.width, 280),
      });
    }
  }, []);

  React.useEffect(() => {
    if (open && portal) updateCoords();
  }, [open, portal, updateCoords]);

  // Cerrar al hacer click fuera
  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!triggerRef.current?.contains(target) && !dropdownRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const dropdownInner = (
    <>
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
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:opacity-80"
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
    </>
  );

  // Dropdown portado al body (por defecto): position:fixed calculado sobre el trigger.
  const portalDropdown = open ? (
    <div
      ref={dropdownRef}
      style={{
        position: "fixed",
        top: coords.top,
        left: coords.left,
        width: coords.width,
        zIndex: 9999,
        pointerEvents: "auto",
        borderColor: "var(--border-soft)",
        backgroundColor: "var(--bg-surface)",
      }}
      className="rounded-lg border shadow-xl"
    >
      {dropdownInner}
    </div>
  ) : null;

  // Dropdown en línea: vive dentro del wrapper (y por tanto dentro del diálogo Radix).
  const inlineDropdown = open ? (
    <div
      ref={dropdownRef}
      style={{
        position: "absolute",
        top: "calc(100% + 4px)",
        left: 0,
        width: "100%",
        minWidth: 240,
        zIndex: 9999,
        borderColor: "var(--border-soft)",
        backgroundColor: "var(--bg-surface)",
      }}
      className="rounded-lg border shadow-xl"
    >
      {dropdownInner}
    </div>
  ) : null;

  return (
    <div className={cn("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        title={selected?.label}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-lg border px-3 text-sm transition-colors",
          "focus:outline-none focus:ring-2",
          "disabled:cursor-not-allowed disabled:opacity-40"
        )}
        style={{
          borderColor: "var(--border-soft)",
          backgroundColor: "var(--bg-surface)",
          color: selected ? "var(--text-primary)" : "var(--text-muted)",
          outlineColor: "var(--ring)",
        }}
      >
        <span className="truncate">{selected ? selected.label : placeholder}</span>
        <div className="ml-2 flex shrink-0 items-center gap-0.5">
          {clearable && selected && !disabled && (
            <span
              role="button"
              aria-label="Limpiar selección"
              onClick={(e) => { e.stopPropagation(); onChange(""); }}
              className="flex h-4 w-4 items-center justify-center rounded-full transition-opacity hover:opacity-70"
              style={{ color: "var(--text-muted)" }}
            >
              <X className="h-3 w-3" />
            </span>
          )}
          <ChevronsUpDown className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
        </div>
      </button>

      {portal
        ? (mounted && portalDropdown ? createPortal(portalDropdown, document.body) : null)
        : inlineDropdown}
    </div>
  );
}
