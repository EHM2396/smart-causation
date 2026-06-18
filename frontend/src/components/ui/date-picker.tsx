"use client";
import * as React from "react";
import { ChevronLeft, ChevronRight, Calendar } from "lucide-react";

interface DatePickerProps {
  label: string;
  value: string; // "YYYY-MM-DD"
  onChange: (v: string) => void;
  max?: string;
  min?: string;
}

const DAYS_ES = ["DO", "LU", "MA", "MI", "JU", "VI", "SA"];
const MONTHS_ES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

function formatDisplay(iso: string) {
  if (!iso) return "Seleccionar";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function buildCells(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const prevMonth = month === 0 ? 11 : month - 1;
  const prevYear = month === 0 ? year - 1 : year;
  const daysInPrev = new Date(prevYear, prevMonth + 1, 0).getDate();
  const nextMonth = month === 11 ? 0 : month + 1;
  const nextYear = month === 11 ? year + 1 : year;

  const cells: { day: number; kind: "prev" | "cur" | "next"; iso: string }[] = [];

  for (let i = firstDay - 1; i >= 0; i--) {
    const d = daysInPrev - i;
    cells.push({
      day: d, kind: "prev",
      iso: `${prevYear}-${String(prevMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
    });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({
      day: d, kind: "cur",
      iso: `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
    });
  }
  const remaining = 42 - cells.length;
  for (let d = 1; d <= remaining; d++) {
    cells.push({
      day: d, kind: "next",
      iso: `${nextYear}-${String(nextMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
    });
  }
  return cells;
}

export function DatePicker({ label, value, onChange, max, min }: DatePickerProps) {
  const today = new Date().toISOString().slice(0, 10);
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  const initYear = value ? parseInt(value.slice(0, 4)) : new Date().getFullYear();
  const initMonth = value ? parseInt(value.slice(5, 7)) - 1 : new Date().getMonth();
  const [viewYear, setViewYear] = React.useState(initYear);
  const [viewMonth, setViewMonth] = React.useState(initMonth);

  // Sync view when value changes from outside
  React.useEffect(() => {
    if (value) {
      setViewYear(parseInt(value.slice(0, 4)));
      setViewMonth(parseInt(value.slice(5, 7)) - 1);
    }
  }, [value]);

  // Close on outside click
  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const prevMonth = () => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear((y) => y - 1); }
    else setViewMonth((m) => m - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear((y) => y + 1); }
    else setViewMonth((m) => m + 1);
  };

  const isDisabled = (iso: string) => (max && iso > max) || (min && iso < min) || false;

  const cells = buildCells(viewYear, viewMonth);

  return (
    <div ref={ref} className="relative flex flex-col gap-1">
      <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
        {label}
      </label>

      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 items-center gap-2 rounded-lg border px-2.5 text-xs transition-colors focus:outline-none focus:ring-2"
        style={{
          borderColor: value ? "var(--brand)" : "var(--border-soft)",
          backgroundColor: "var(--bg-surface)",
          color: value ? "var(--text-primary)" : "var(--text-muted)",
          outlineColor: "var(--ring)",
          minWidth: "128px",
        }}
      >
        <Calendar
          className="h-3.5 w-3.5 shrink-0"
          style={{ color: value ? "var(--brand)" : "var(--text-muted)" }}
        />
        {formatDisplay(value)}
      </button>

      {/* Popover */}
      {open && (
        <div
          className="absolute top-full left-0 z-50 mt-1.5 w-[272px] rounded-xl border"
          style={{
            borderColor: "var(--border-soft)",
            backgroundColor: "var(--bg-surface)",
            boxShadow: "var(--shadow-lg)",
          }}
        >
          {/* Month navigation */}
          <div
            className="flex items-center justify-between px-3 py-2.5 border-b"
            style={{ borderColor: "var(--border-soft)" }}
          >
            <button
              type="button"
              onClick={prevMonth}
              className="flex h-6 w-6 items-center justify-center rounded-md transition-opacity hover:opacity-70"
              style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)" }}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span
              className="text-xs font-semibold capitalize"
              style={{ color: "var(--text-primary)" }}
            >
              {MONTHS_ES[viewMonth]} de {viewYear}
            </span>
            <button
              type="button"
              onClick={nextMonth}
              className="flex h-6 w-6 items-center justify-center rounded-md transition-opacity hover:opacity-70"
              style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)" }}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 px-2 pt-2.5 pb-1">
            {DAYS_ES.map((d) => (
              <div key={d} className="flex items-center justify-center">
                <span
                  className="text-[10px] font-semibold uppercase"
                  style={{ color: "var(--text-muted)" }}
                >
                  {d}
                </span>
              </div>
            ))}
          </div>

          {/* Day cells */}
          <div className="grid grid-cols-7 gap-y-0.5 px-2 pb-2">
            {cells.map((cell, i) => {
              const isSelected = cell.iso === value;
              const isToday = cell.iso === today;
              const isCur = cell.kind === "cur";
              const disabled = isDisabled(cell.iso);

              return (
                <button
                  key={i}
                  type="button"
                  disabled={!!disabled}
                  onClick={() => {
                    if (!disabled) { onChange(cell.iso); setOpen(false); }
                  }}
                  className="flex h-7 w-full items-center justify-center rounded-md text-xs transition-colors"
                  style={{
                    backgroundColor: isSelected
                      ? "var(--brand)"
                      : isToday
                      ? "color-mix(in srgb, var(--brand) 14%, transparent)"
                      : "transparent",
                    color: isSelected
                      ? "#fff"
                      : isCur
                      ? isToday
                        ? "var(--brand)"
                        : "var(--text-primary)"
                      : "var(--text-muted)",
                    fontWeight: isSelected || isToday ? "600" : "400",
                    opacity: disabled ? 0.3 : 1,
                    cursor: disabled ? "not-allowed" : "pointer",
                    outline: isToday && !isSelected ? "1.5px solid var(--brand)" : "none",
                    outlineOffset: "-1.5px",
                  }}
                >
                  {cell.day}
                </button>
              );
            })}
          </div>

          {/* Footer */}
          <div
            className="flex items-center justify-between border-t px-3 py-2"
            style={{ borderColor: "var(--border-soft)" }}
          >
            <button
              type="button"
              onClick={() => { onChange(""); setOpen(false); }}
              className="text-xs transition-opacity hover:opacity-70"
              style={{ color: "var(--text-muted)" }}
            >
              Borrar
            </button>
            <button
              type="button"
              onClick={() => {
                if (!isDisabled(today)) { onChange(today); setOpen(false); }
              }}
              className="text-xs font-semibold transition-opacity hover:opacity-80"
              style={{ color: "var(--brand)" }}
            >
              Hoy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
