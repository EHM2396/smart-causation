"use client";

import { Check, X } from "lucide-react";

const CRITERIOS = [
  { label: "Mínimo 8 caracteres", test: (p: string) => p.length >= 8 },
  { label: "Al menos una mayúscula", test: (p: string) => /[A-Z]/.test(p) },
  { label: "Al menos un número", test: (p: string) => /\d/.test(p) },
  { label: "Al menos un carácter especial", test: (p: string) => /[!@#$%^&*()\-_=+\[\]{};:'",.<>/?\\|`~]/.test(p) },
];

const NIVELES = [
  { label: "Muy débil", color: "#ef4444" },
  { label: "Débil",     color: "#f97316" },
  { label: "Regular",   color: "#eab308" },
  { label: "Fuerte",    color: "#22c55e" },
];

export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;

  const cumplidos = CRITERIOS.filter((c) => c.test(password)).length;
  const nivel = NIVELES[cumplidos - 1] ?? NIVELES[0];

  return (
    <div className="mt-2 space-y-2">
      {/* Barra de progreso */}
      <div className="flex gap-1">
        {NIVELES.map((_, i) => (
          <div
            key={i}
            className="h-1 flex-1 rounded-full transition-all duration-300"
            style={{
              backgroundColor: i < cumplidos ? nivel.color : "var(--border-strong)",
            }}
          />
        ))}
      </div>
      <p className="text-xs font-medium" style={{ color: nivel.color }}>
        {nivel.label}
      </p>

      {/* Lista de criterios */}
      <ul className="space-y-1">
        {CRITERIOS.map((c) => {
          const ok = c.test(password);
          return (
            <li key={c.label} className="flex items-center gap-1.5 text-xs">
              {ok
                ? <Check className="h-3 w-3 shrink-0" style={{ color: "#22c55e" }} />
                : <X    className="h-3 w-3 shrink-0" style={{ color: "var(--text-muted)" }} />
              }
              <span style={{ color: ok ? "var(--text-secondary)" : "var(--text-muted)" }}>
                {c.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
