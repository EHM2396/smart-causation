"use client";
import { useEffect } from "react";
import { useWizardStore } from "@/stores/wizard";
import type { DocTipo } from "@/stores/wizard";
import { StepIndicator } from "./step-indicator";
import { Paso1 } from "./paso1";
import { Paso2 } from "./paso2";
import { Paso3 } from "./paso3";
import { Paso4 } from "./paso4";
import { ConfigPanel } from "./config-panel";
import { FileText, Layers, CheckCircle2, Tag, AlertTriangle, BookOpen, FileMinus2, ArrowRight, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import Link from "next/link";

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

function CatalogGate() {
  const tutorialActivo = useWizardStore((s) => s.tutorialActivo);
  const { data: cuentasGasto = [], isLoading: loadingCG } = useQuery({ queryKey: ["cuentas-gasto"], queryFn: api.getCuentasGasto });
  const { data: impuestos   = [], isLoading: loadingImp } = useQuery({ queryKey: ["impuestos"],     queryFn: api.getImpuestos });
  const { data: tipos       = [], isLoading: loadingTC }  = useQuery({ queryKey: ["tipos-comp"],    queryFn: api.getTiposComprobante });

  if (tutorialActivo) return null;
  if (loadingCG || loadingImp || loadingTC) return null;

  const faltantes: string[] = [];
  if (cuentasGasto.length === 0) faltantes.push("Plan de cuentas (PUC)");
  if (impuestos.length === 0)    faltantes.push("Impuestos y retenciones");
  if (tipos.length === 0)        faltantes.push("Tipos de comprobante");

  if (faltantes.length === 0) return null;

  return (
    <div
      className="mb-6 flex flex-col gap-4 rounded-xl border p-5"
      style={{ borderColor: "var(--warning-border)", backgroundColor: "var(--warning-bg)" }}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--warning-text)" }} />
        <div>
          <p className="text-sm font-semibold" style={{ color: "var(--warning-text)" }}>
            Catálogo incompleto — no es posible causar facturas
          </p>
          <p className="mt-1 text-xs" style={{ color: "var(--warning-text)", opacity: 0.8 }}>
            Debes cargar la siguiente información antes de iniciar la causación:
          </p>
          <ul className="mt-2 space-y-1">
            {faltantes.map((f) => (
              <li key={f} className="flex items-center gap-2 text-xs font-medium" style={{ color: "var(--warning-text)" }}>
                <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: "var(--warning-text)" }} />
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <Link
        href="/catalogos"
        className="inline-flex w-fit items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-opacity hover:opacity-80"
        style={{ backgroundColor: "var(--warning-text)", color: "#fff" }}
      >
        <BookOpen className="h-4 w-4" />
        Ir a Catálogos
      </Link>
    </div>
  );
}

function NcRuteadasAviso() {
  const esNC = useWizardStore((s) => s.docTipo === "nc");
  const ncRuteadas = useWizardStore((s) => s.ncRuteadas);
  const setNcRuteadas = useWizardStore((s) => s.setNcRuteadas);

  // Solo tiene sentido en el módulo de Compras (en NC no se rutea nada).
  if (esNC || ncRuteadas <= 0) return null;

  return (
    <div
      className="mb-6 flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between"
      style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}
    >
      <div className="flex items-start gap-3">
        <FileMinus2 className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--info-text)" }} />
        <div>
          <p className="text-sm font-semibold" style={{ color: "var(--info-text)" }}>
            {ncRuteadas} nota{ncRuteadas !== 1 ? "s" : ""} crédito detectada{ncRuteadas !== 1 ? "s" : ""} en este lote
          </p>
          <p className="mt-0.5 text-xs" style={{ color: "var(--info-text)", opacity: 0.85 }}>
            Se enviaron a <strong>NC Compras</strong> y quedaron <strong>guardadas en borrador</strong> — entra a ese módulo para causarlas. No necesitas volver a cargarlas.
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link
          href="/causacion-nc"
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold no-underline"
          style={{ backgroundColor: "var(--info-text)", color: "#fff" }}
        >
          <ArrowRight className="h-4 w-4" /> Ir a NC Compras
        </Link>
        <button
          type="button"
          onClick={() => setNcRuteadas(0)}
          className="rounded-md p-1.5 transition-opacity hover:opacity-70"
          style={{ color: "var(--info-text)" }}
          aria-label="Cerrar aviso"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export function CausacionWizard({ docTipo = "compras" }: { docTipo?: DocTipo }) {
  const { paso, facturas, tipoComp, mapeos, docTipo: docTipoActual, setDocTipo, reset } = useWizardStore();

  // Al entrar al módulo, si venías del otro (compras <-> nc), fija el modo y
  // limpia el estado para no mezclar facturas de compra con notas crédito.
  useEffect(() => {
    if (docTipoActual !== docTipo) {
      setDocTipo(docTipo);
      reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docTipo]);

  const esNC = docTipo === "nc";
  const totalItems = facturas.reduce((s, f) => s + f.items.length, 0);
  const mapeados = mapeos.filter((m) => m.cuenta_gasto).length;

  return (
    <div className="flex h-full flex-col lg:flex-row">
      {/* Config panel — top strip on mobile, right sidebar on desktop */}
      <ConfigPanel />

      {/* Separator */}
      <div className="hidden lg:block w-px shrink-0" style={{ backgroundColor: "var(--border-soft)" }} />

      {/* Main */}
      <div className="flex-1 overflow-y-auto px-4 py-6 lg:px-8 lg:py-8">
        {/* KPI bar */}
        <div className="grid grid-cols-2 gap-3 mb-6 sm:grid-cols-4 lg:mb-8">
          <KpiCard icon={FileText}    label={esNC ? "Notas crédito" : "Facturas"} value={facturas.length} accent="#4F46E5" sublabel={facturas.length ? (esNC ? "notas cargadas" : "archivos cargados") : "Sin cargar aún"} />
          <KpiCard icon={Layers}      label="Ítems"          value={totalItems}      accent="#7c3aed" sublabel={totalItems ? "líneas de factura" : "Carga archivos primero"} />
          <KpiCard icon={CheckCircle2} label="Mapeadas"      value={mapeados}        accent="#8FB5FF" sublabel={mapeados ? `de ${totalItems} ítems` : "Pendiente mapeo"} />
          <KpiCard icon={Tag}         label="Comprobante"    value={tipoComp || "—"} accent="#d97706" sublabel={tipoComp ? "tipo seleccionado" : "Selecciona en config"} />
        </div>

        {/* Steps */}
        <div className="mb-6 lg:mb-8">
          <StepIndicator />
        </div>

        {/* Catalog preflight check */}
        <CatalogGate />

        {/* Aviso: notas crédito detectadas y enviadas a NC Compras */}
        <NcRuteadasAviso />

        {/* Step content */}
        <div>
          {paso === 1 && <Paso1 />}
          <div style={{ display: paso === 2 ? "block" : "none" }}>
            {(paso === 2 || paso === 3) && <Paso2 />}
          </div>
          {paso === 3 && <Paso3 />}
          {paso === 4 && <Paso4 />}
        </div>
      </div>
    </div>
  );
}
