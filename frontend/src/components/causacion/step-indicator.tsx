"use client";
import { useWizardStore } from "@/stores/wizard";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const PASOS = [
  { n: 1, label: "Cargar facturas",  short: "Cargar"    },
  { n: 2, label: "Mapear cuentas",   short: "Mapear"    },
  { n: 3, label: "Validar partida",  short: "Validar"   },
  { n: 4, label: "Descargar",        short: "Descargar" },
];

export function StepIndicator() {
  const paso = useWizardStore((s) => s.paso);

  return (
    <div
      className="flex items-center justify-between rounded-xl px-3 py-4 sm:px-6"
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border-soft)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {PASOS.map((p, i) => {
        const done = paso > p.n;
        const active = paso === p.n;

        return (
          <div key={p.n} className="flex flex-1 items-center">
            {/* Step item */}
            <div className="flex flex-col items-center gap-1.5 min-w-0">
              {/* Circle */}
              <div
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold transition-all duration-300",
                  done
                    ? "text-white"
                    : active
                    ? "text-white"
                    : ""
                )}
                style={{
                  backgroundColor: done
                    ? "var(--success)"
                    : active
                    ? "var(--brand)"
                    : "var(--bg-elevated)",
                  color: done || active ? "#fff" : "var(--text-muted)",
                  border: done || active ? "none" : "1.5px solid var(--border-strong)",
                  boxShadow: active ? "0 0 0 4px var(--brand-muted)" : "none",
                }}
              >
                {done ? <Check className="h-4 w-4 stroke-[2.5]" /> : p.n}
              </div>

              {/* Label */}
              <span
                className="text-[10px] font-medium whitespace-nowrap sm:text-xs"
                style={{
                  color: active
                    ? "var(--brand)"
                    : done
                    ? "var(--success)"
                    : "var(--text-muted)",
                }}
              >
                <span className="sm:hidden">{p.short}</span>
                <span className="hidden sm:inline">{p.label}</span>
              </span>
            </div>

            {/* Connector */}
            {i < PASOS.length - 1 && (
              <div
                className="flex-1 mx-3 mb-6 h-0.5 rounded-full transition-all duration-500"
                style={{
                  backgroundColor: done ? "var(--success)" : "var(--border-soft)",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
