"use client";
import { useWizardStore } from "@/stores/wizard";
import { StepIndicator } from "./step-indicator";
import { Paso1 } from "./paso1";
import { Paso2 } from "./paso2";
import { Paso3 } from "./paso3";
import { Paso4 } from "./paso4";
import { ConfigPanel } from "./config-panel";
import { FileText, Layers, CheckCircle2, Tag } from "lucide-react";

function KpiCard({
  icon: Icon,
  label,
  value,
  accent,
  sublabel,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  accent: string;
  sublabel?: string;
}) {
  return (
    <div
      className="relative overflow-hidden rounded-xl px-4 py-4 transition-shadow hover:shadow-md"
      style={{
        backgroundColor: "var(--bg-surface)",
        border: "1px solid var(--border-soft)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Color accent strip */}
      <div
        className="absolute top-0 left-0 right-0 h-[3px]"
        style={{ backgroundColor: accent }}
      />

      <div className="flex items-start justify-between gap-3 mt-1">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            {label}
          </p>
          <p className="mt-1.5 text-2xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
            {value}
          </p>
          {sublabel && (
            <p className="mt-0.5 text-xs truncate" style={{ color: "var(--text-muted)" }}>{sublabel}</p>
          )}
        </div>
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
          style={{ backgroundColor: accent + "15" }}
        >
          <Icon className="h-5 w-5" style={{ color: accent }} />
        </div>
      </div>
    </div>
  );
}

export function CausacionWizard() {
  const { paso, facturas, tipoComp, mapeos } = useWizardStore();

  const totalItems = facturas.reduce((s, f) => s + f.items.length, 0);
  const mapeados = mapeos.filter((m) => m.cuenta_gasto).length;

  return (
    <div className="flex h-full flex-col lg:flex-row">
      {/* Config panel — top strip on mobile, right sidebar on desktop */}
      <ConfigPanel />

      {/* Main */}
      <div className="flex-1 overflow-y-auto px-4 py-6 lg:px-8 lg:py-8">
        {/* KPI bar */}
        <div className="grid grid-cols-2 gap-3 mb-6 sm:grid-cols-4 lg:mb-8">
          <KpiCard icon={FileText}    label="Facturas"       value={facturas.length} accent="#059669" sublabel={facturas.length ? "archivos cargados" : "Sin cargar aún"} />
          <KpiCard icon={Layers}      label="Ítems"          value={totalItems}      accent="#7c3aed" sublabel={totalItems ? "líneas de factura" : "Carga archivos primero"} />
          <KpiCard icon={CheckCircle2} label="Mapeadas"      value={mapeados}        accent="#0891b2" sublabel={mapeados ? `de ${totalItems} ítems` : "Pendiente mapeo"} />
          <KpiCard icon={Tag}         label="Comprobante"    value={tipoComp || "—"} accent="#d97706" sublabel={tipoComp ? "tipo seleccionado" : "Selecciona en config"} />
        </div>

        {/* Steps */}
        <div className="mb-6 lg:mb-8">
          <StepIndicator />
        </div>

        {/* Step content */}
        <div className="max-w-4xl">
          {paso === 1 && <Paso1 />}
          {paso === 2 && <Paso2 />}
          {paso === 3 && <Paso3 />}
          {paso === 4 && <Paso4 />}
        </div>
      </div>
    </div>
  );
}
