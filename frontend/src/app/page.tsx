"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  Zap, Brain, FileSpreadsheet, Users, BarChart3, Building2,
  Check, X, Upload, Cpu, Download, ArrowRight, Menu, ChevronDown,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { BRAND } from "@/lib/brand";

// ── Utils ─────────────────────────────────────────────────────────────────────

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Data ──────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: Upload,
    title: "Importación masiva de facturas",
    desc: "Sube PDFs de facturas DIAN en lote. El motor extrae automáticamente NIT, valores, impuestos y datos del proveedor.",
  },
  {
    icon: Brain,
    title: "IA que aprende de tu contabilidad",
    desc: "Cada vez que confirmas una causación, la IA refuerza su aprendizaje. Con el tiempo, las sugerencias son casi perfectas.",
  },
  {
    icon: FileSpreadsheet,
    title: "Exportación directa a Siigo",
    desc: "Genera el Excel en el formato exacto de importación masiva de Siigo Nube SF_CO, listo para cargar con un clic.",
  },
  {
    icon: Users,
    title: "Módulo de terceros",
    desc: "Gestiona proveedores con todos los campos que Siigo necesita: tipo de persona, régimen IVA, responsabilidad fiscal y geo.",
  },
  {
    icon: BarChart3,
    title: "Historial completo",
    desc: "Consulta cada causación, regenera archivos anteriores y lleva el control exacto de lo procesado.",
  },
  {
    icon: Building2,
    title: "Multiempresa",
    desc: "Administra varias empresas desde una sola cuenta. Cada una con sus catálogos, reglas de IA e historial propios.",
  },
];

const STEPS = [
  {
    icon: Upload,
    title: "Sube tus facturas",
    desc: "Arrastra los PDFs de tus facturas electrónicas DIAN. Puedes subir decenas a la vez.",
  },
  {
    icon: Cpu,
    title: "La IA analiza y sugiere",
    desc: "El motor extrae los datos, identifica el proveedor y sugiere cuenta contable, impuestos y comprobante.",
  },
  {
    icon: Download,
    title: "Exporta a Siigo",
    desc: "Confirma, ajusta si necesitas, y descarga el Excel listo para importar en Siigo Nube en segundos.",
  },
];

const PLANES = [
  {
    id: "basico",
    nombre: "Básico",
    desc: "Para contadores independientes que quieren comenzar a automatizar.",
    badge: null,
    items: ["300 causaciones / mes", "1 usuario", "1 empresa", "Soporte por correo"],
    destacado: false,
  },
  {
    id: "profesional",
    nombre: "Profesional",
    desc: "Para firmas contables en crecimiento con varios clientes.",
    badge: "⭐ Más popular",
    items: ["1.000 causaciones / mes", "Hasta 5 usuarios", "Hasta 10 empresas", "Soporte prioritario", "1 sesión de capacitación"],
    destacado: true,
  },
  {
    id: "firma",
    nombre: "Firma",
    desc: "Para firmas establecidas con alto volumen y necesidades avanzadas.",
    badge: null,
    items: ["5.000 causaciones / mes", "Hasta 20 usuarios", "Hasta 50 empresas", "Soporte Prioritario + WhatsApp", "3 sesiones de capacitación", "API opcional", "SLA básico"],
    destacado: false,
  },
  {
    id: "enterprise",
    nombre: "Enterprise",
    desc: "Para grandes organizaciones con requerimientos personalizados.",
    badge: null,
    items: ["Causaciones personalizadas", "Usuarios ilimitados", "Empresas ilimitadas", "Ejecutivo dedicado", "Capacitación personalizada", "API incluida", "SLA empresarial"],
    destacado: false,
  },
];

const TABLE_ROWS: {
  label: string;
  basico: boolean | string;
  pro: boolean | string;
  firma: boolean | string;
  enterprise: boolean | string;
}[] = [
  { label: "Causaciones/mes",        basico: "300",      pro: "1.000",        firma: "5.000",        enterprise: "Personaliz." },
  { label: "Usuarios",               basico: "1",        pro: "Hasta 5",      firma: "Hasta 20",     enterprise: "Ilimitados" },
  { label: "Empresas",               basico: "1",        pro: "Hasta 10",     firma: "Hasta 50",     enterprise: "Ilimitadas" },
  { label: "Motor de IA",            basico: true,       pro: true,           firma: true,           enterprise: true },
  { label: "Aprendizaje automático", basico: true,       pro: true,           firma: true,           enterprise: true },
  { label: "Importación masiva",     basico: true,       pro: true,           firma: true,           enterprise: true },
  { label: "Exportación a Siigo",    basico: true,       pro: true,           firma: true,           enterprise: true },
  { label: "Soporte",                basico: "Correo",   pro: "Prioritario",  firma: "Prior.+WA",    enterprise: "Ejecutivo" },
  { label: "Capacitación",           basico: false,      pro: "1 sesión",     firma: "3 sesiones",   enterprise: "Personal." },
  { label: "API",                    basico: false,      pro: false,          firma: "Opcional",     enterprise: true },
  { label: "Integraciones custom",   basico: false,      pro: false,          firma: "Opcional",     enterprise: true },
  { label: "SLA",                    basico: false,      pro: false,          firma: "Básico",       enterprise: "Empresarial" },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function ProximamenteBtn({
  children,
  className = "",
  style = {},
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative inline-block">
      <button
        type="button"
        className={className}
        style={style}
        onClick={() => {
          setShow(true);
          setTimeout(() => setShow(false), 2200);
        }}
      >
        {children}
      </button>
      {show && (
        <div
          className="absolute left-1/2 -translate-x-1/2 -top-12 z-50 whitespace-nowrap rounded-xl px-4 py-2 text-xs font-bold text-white shadow-xl"
          style={{ backgroundColor: "#4F46E5" }}
        >
          ¡Próximamente! 🚀
          <div
            className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0"
            style={{
              borderLeft: "5px solid transparent",
              borderRight: "5px solid transparent",
              borderTop: "5px solid #4F46E5",
            }}
          />
        </div>
      )}
    </div>
  );
}

function CellVal({ val }: { val: boolean | string }) {
  if (val === true)
    return <Check className="h-4 w-4 mx-auto" style={{ color: "#22c55e" }} />;
  if (val === false)
    return <X className="h-4 w-4 mx-auto" style={{ color: "var(--border-strong)" }} />;
  return (
    <span className="text-xs text-center block" style={{ color: "var(--text-secondary)" }}>
      {val}
    </span>
  );
}

function FeatureTable() {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-10 text-center">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 text-sm font-semibold transition-opacity hover:opacity-70"
        style={{ color: "var(--brand)" }}
      >
        {open ? "Ocultar" : "Ver"} comparativa completa
        <ChevronDown
          className={`h-4 w-4 transition-transform duration-300 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          className="mt-8 overflow-x-auto rounded-2xl border"
          style={{ borderColor: "var(--border-soft)" }}
        >
          <table className="w-full min-w-[600px] text-sm border-collapse">
            <thead>
              <tr style={{ backgroundColor: "var(--bg-elevated)" }}>
                <th
                  className="py-3 px-5 text-left font-semibold"
                  style={{ color: "var(--text-secondary)", width: "210px" }}
                >
                  Característica
                </th>
                {(["Básico", "Profesional", "Firma", "Enterprise"] as const).map((p) => (
                  <th
                    key={p}
                    className="py-3 px-4 text-center font-bold"
                    style={{ color: p === "Profesional" ? "var(--brand)" : "var(--text-primary)" }}
                  >
                    {p}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TABLE_ROWS.map((row, i) => (
                <tr
                  key={row.label}
                  style={{
                    backgroundColor:
                      i % 2 === 0 ? "var(--bg-surface)" : "var(--bg-elevated)",
                  }}
                >
                  <td className="py-3 px-5 font-medium" style={{ color: "var(--text-secondary)" }}>
                    {row.label}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <CellVal val={row.basico} />
                  </td>
                  <td className="py-3 px-4 text-center">
                    <CellVal val={row.pro} />
                  </td>
                  <td className="py-3 px-4 text-center">
                    <CellVal val={row.firma} />
                  </td>
                  <td className="py-3 px-4 text-center">
                    <CellVal val={row.enterprise} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      style={{ backgroundColor: "var(--bg-app)", color: "var(--text-primary)", minHeight: "100vh" }}
    >
      {/* ── Navbar ── */}
      <header
        className="fixed top-0 inset-x-0 z-50 transition-all duration-300"
        style={{
          backgroundColor: scrolled
            ? "color-mix(in srgb, var(--bg-surface) 90%, transparent)"
            : "transparent",
          backdropFilter: scrolled ? "blur(16px)" : "none",
          borderBottom: scrolled
            ? "1px solid var(--border-soft)"
            : "1px solid transparent",
          boxShadow: scrolled ? "var(--shadow-sm)" : "none",
        }}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          {/* Logo */}
          <Link href="/" className="shrink-0">
            <Image
              src="/brand/Logo-Completo.webp"
              alt={BRAND.name}
              width={160}
              height={40}
              className="block dark:hidden"
              style={{ objectFit: "contain", height: "auto", maxHeight: "40px" }}
              priority
            />
            <Image
              src="/brand/Logo-Completo-blanco.webp"
              alt={BRAND.name}
              width={160}
              height={40}
              className="hidden dark:block"
              style={{ objectFit: "contain", height: "auto", maxHeight: "40px" }}
              priority
            />
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-7">
            {(
              [
                ["caracteristicas", "Características"],
                ["como-funciona", "Cómo funciona"],
                ["planes", "Planes"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => scrollTo(id)}
                className="text-sm font-medium transition-opacity hover:opacity-60"
                style={{ color: "var(--text-secondary)", background: "none", border: "none", cursor: "pointer" }}
              >
                {label}
              </button>
            ))}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/login"
              className="hidden md:inline-flex items-center rounded-lg border px-4 py-2 text-sm font-semibold transition-all hover:opacity-80"
              style={{ borderColor: "var(--brand)", color: "var(--brand)" }}
            >
              Iniciar sesión
            </Link>
            <ProximamenteBtn
              className="hidden md:inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-bold text-white transition-all hover:opacity-90"
              style={{ background: "linear-gradient(135deg,#4F46E5,#4338CA)" }}
            >
              Empezar gratis
            </ProximamenteBtn>
            <button
              type="button"
              className="md:hidden rounded-lg p-2 transition-opacity hover:opacity-60"
              style={{ color: "var(--text-secondary)" }}
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div
            className="md:hidden border-t px-6 py-4 space-y-1"
            style={{
              backgroundColor: "var(--bg-surface)",
              borderColor: "var(--border-soft)",
            }}
          >
            {(
              [
                ["caracteristicas", "Características"],
                ["como-funciona", "Cómo funciona"],
                ["planes", "Planes"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className="block w-full text-left py-2 text-sm font-medium"
                style={{ color: "var(--text-secondary)", background: "none", border: "none", cursor: "pointer" }}
                onClick={() => { scrollTo(id); setMobileOpen(false); }}
              >
                {label}
              </button>
            ))}
            <div
              className="pt-3 border-t flex flex-col gap-2"
              style={{ borderColor: "var(--border-soft)" }}
            >
              <Link
                href="/login"
                className="text-sm font-bold py-2"
                style={{ color: "var(--brand)" }}
                onClick={() => setMobileOpen(false)}
              >
                Iniciar sesión
              </Link>
              <ProximamenteBtn
                className="rounded-lg py-2.5 text-sm font-bold text-white"
                style={{ background: "linear-gradient(135deg,#4F46E5,#4338CA)" }}
              >
                Empezar gratis
              </ProximamenteBtn>
            </div>
          </div>
        )}
      </header>

      {/* ── Hero ── */}
      <section className="relative overflow-hidden px-6 pb-28 pt-36">
        {/* Glow */}
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(ellipse 80% 55% at 50% 0%, rgba(79,70,229,0.18) 0%, transparent 70%)",
          }}
        />
        {/* Dot grid */}
        <div
          className="pointer-events-none absolute inset-0 -z-10 opacity-[0.15]"
          style={{
            backgroundImage:
              "radial-gradient(var(--border-strong) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />

        <div className="mx-auto max-w-4xl text-center">
          <div
            className="mb-7 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-bold"
            style={{
              borderColor: "rgba(79,70,229,0.35)",
              color: "var(--brand)",
              backgroundColor: "rgba(79,70,229,0.08)",
            }}
          >
            <Zap className="h-3.5 w-3.5" />
            Causación contable con IA para Colombia
          </div>

          <h1
            className="mb-6 text-5xl font-extrabold leading-[1.1] tracking-tight md:text-6xl lg:text-7xl"
            style={{ color: "var(--text-primary)" }}
          >
            Automatiza tu{" "}
            <span
              style={{
                color: "var(--brand)",
                textDecoration: "underline",
                textDecorationColor: "rgba(79,70,229,0.3)",
                textUnderlineOffset: "6px",
              }}
            >
              causación
            </span>
            <br />
            en segundos
          </h1>

          <p
            className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            Sube facturas DIAN, deja que la IA sugiera cuentas, impuestos y comprobantes, y exporta
            directo a Siigo Nube. Sin digitación manual. Sin errores.
          </p>

          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <ProximamenteBtn
              className="flex items-center gap-2 rounded-xl px-8 py-3.5 text-base font-bold text-white shadow-xl transition-all hover:scale-105 active:scale-100"
              style={{
                background: "linear-gradient(135deg,#4F46E5,#4338CA)",
                boxShadow: "0 8px 32px rgba(79,70,229,0.4)",
              }}
            >
              Empezar gratis <ArrowRight className="h-4 w-4" />
            </ProximamenteBtn>
            <ProximamenteBtn
              className="flex items-center gap-2 rounded-xl border px-8 py-3.5 text-base font-semibold transition-all hover:opacity-80"
              style={{
                borderColor: "var(--border-strong)",
                color: "var(--text-primary)",
                backgroundColor: "var(--bg-surface)",
              }}
            >
              Ver demo
            </ProximamenteBtn>
          </div>

          <p className="mt-7 text-sm" style={{ color: "var(--text-muted)" }}>
            ¿Ya tienes cuenta?{" "}
            <Link
              href="/login"
              className="font-bold underline decoration-dotted"
              style={{ color: "var(--brand)" }}
            >
              Inicia sesión aquí
            </Link>
          </p>
        </div>
      </section>

      {/* ── Stats bar ── */}
      <div
        className="border-y py-8"
        style={{
          backgroundColor: "var(--bg-surface)",
          borderColor: "var(--border-soft)",
        }}
      >
        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 px-6 md:grid-cols-4">
          {(
            [
              ["Facturas", "100%", "automáticas"],
              ["Compatible", "DIAN", "electrónica"],
              ["Exporta a", "Siigo", "Nube SF_CO"],
              ["IA con", "Aprend.", "continuo"],
            ] as const
          ).map(([label, value, sub]) => (
            <div key={label} className="text-center">
              <p className="text-2xl font-extrabold" style={{ color: "var(--brand)" }}>
                {value}
              </p>
              <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                {sub}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                {label}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Features ── */}
      <section id="caracteristicas" className="py-24 px-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <h2
              className="mb-4 text-3xl font-extrabold md:text-4xl"
              style={{ color: "var(--text-primary)" }}
            >
              Todo lo que necesitas para automatizar
              <br className="hidden md:block" /> tu contabilidad
            </h2>
            <p
              className="mx-auto max-w-xl text-base"
              style={{ color: "var(--text-secondary)" }}
            >
              Diseñado específicamente para el flujo contable colombiano con DIAN y Siigo Nube.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group rounded-2xl border p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
                style={{
                  backgroundColor: "var(--bg-surface)",
                  borderColor: "var(--border-soft)",
                  boxShadow: "var(--shadow-xs)",
                }}
              >
                <div
                  className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl transition-all group-hover:scale-110"
                  style={{ background: "rgba(79,70,229,0.1)" }}
                >
                  <f.icon className="h-5 w-5" style={{ color: "var(--brand)" }} />
                </div>
                <h3
                  className="mb-2 text-base font-bold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {f.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section
        id="como-funciona"
        className="py-24 px-6"
        style={{
          backgroundColor: "var(--bg-surface)",
          borderTop: "1px solid var(--border-soft)",
          borderBottom: "1px solid var(--border-soft)",
        }}
      >
        <div className="mx-auto max-w-5xl">
          <div className="mb-16 text-center">
            <h2
              className="mb-4 text-3xl font-extrabold md:text-4xl"
              style={{ color: "var(--text-primary)" }}
            >
              Tan fácil como 1 · 2 · 3
            </h2>
            <p className="mx-auto max-w-xl text-base" style={{ color: "var(--text-secondary)" }}>
              De la factura en PDF al asiento contable en Siigo en menos de un minuto.
            </p>
          </div>

          <div className="grid gap-10 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <div
                key={step.title}
                className="relative flex flex-col items-center text-center"
              >
                {i < STEPS.length - 1 && (
                  <div
                    className="absolute hidden md:block top-8 left-[calc(50%+3rem)] right-[-calc(50%-3rem)] h-px"
                    style={{
                      background:
                        "linear-gradient(to right, var(--border-strong), var(--border-soft))",
                    }}
                  />
                )}
                <div
                  className="relative mb-6 flex h-16 w-16 items-center justify-center rounded-2xl"
                  style={{
                    background: "rgba(79,70,229,0.1)",
                    border: "1.5px solid rgba(79,70,229,0.2)",
                  }}
                >
                  <step.icon className="h-7 w-7" style={{ color: "var(--brand)" }} />
                  <span
                    className="absolute -top-3 -right-3 flex h-7 w-7 items-center justify-center rounded-full text-xs font-extrabold text-white shadow-md"
                    style={{ backgroundColor: "var(--brand)" }}
                  >
                    {i + 1}
                  </span>
                </div>
                <h3
                  className="mb-2 text-base font-bold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {step.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {step.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="planes" className="py-24 px-6">
        <div className="mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <h2
              className="mb-4 text-3xl font-extrabold md:text-4xl"
              style={{ color: "var(--text-primary)" }}
            >
              Planes para cada tipo de firma
            </h2>
            <p className="mx-auto max-w-xl text-base" style={{ color: "var(--text-secondary)" }}>
              Desde el contador independiente hasta la firma más grande.
            </p>
            <div
              className="mt-4 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-bold"
              style={{
                borderColor: "rgba(79,70,229,0.35)",
                color: "var(--brand)",
                backgroundColor: "rgba(79,70,229,0.08)",
              }}
            >
              <Zap className="h-3 w-3" /> Precios disponibles próximamente
            </div>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
            {PLANES.map((plan) => (
              <div
                key={plan.id}
                className="relative flex flex-col rounded-2xl border p-6 transition-all duration-300"
                style={{
                  backgroundColor: "var(--bg-surface)",
                  borderColor: plan.destacado ? "var(--brand)" : "var(--border-soft)",
                  boxShadow: plan.destacado
                    ? "0 0 0 2px var(--brand), var(--shadow-lg)"
                    : "var(--shadow-xs)",
                  transform: plan.destacado ? "scale(1.02)" : "none",
                }}
              >
                {plan.badge && (
                  <div
                    className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full px-4 py-1 text-xs font-extrabold text-white shadow"
                    style={{ background: "linear-gradient(135deg,#4F46E5,#4338CA)" }}
                  >
                    {plan.badge}
                  </div>
                )}

                <div className="mb-5">
                  <h3
                    className="mb-1 text-lg font-extrabold"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {plan.nombre}
                  </h3>
                  <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
                    {plan.desc}
                  </p>
                </div>

                {/* Price placeholder */}
                <div
                  className="mb-6 rounded-xl px-4 py-3 text-center text-xs font-bold"
                  style={{
                    backgroundColor: "rgba(79,70,229,0.08)",
                    color: "var(--brand)",
                    border: "1px dashed rgba(79,70,229,0.3)",
                  }}
                >
                  Precio próximamente
                </div>

                <ul className="mb-8 flex-1 space-y-2.5">
                  {plan.items.map((item) => (
                    <li key={item} className="flex items-start gap-2.5 text-sm">
                      <Check
                        className="mt-0.5 h-4 w-4 shrink-0"
                        style={{ color: "#22c55e" }}
                      />
                      <span style={{ color: "var(--text-secondary)" }}>{item}</span>
                    </li>
                  ))}
                </ul>

                <ProximamenteBtn
                  className="w-full rounded-xl py-2.5 text-sm font-bold transition-all hover:opacity-90 active:scale-95"
                  style={
                    plan.destacado
                      ? {
                          background: "linear-gradient(135deg,#4F46E5,#4338CA)",
                          color: "#fff",
                        }
                      : {
                          backgroundColor: "var(--bg-elevated)",
                          color: "var(--text-primary)",
                          border: "1px solid var(--border-soft)",
                        }
                  }
                >
                  {plan.id === "enterprise" ? "Contactar ventas" : "Contratar plan"}
                </ProximamenteBtn>
              </div>
            ))}
          </div>

          <FeatureTable />
        </div>
      </section>

      {/* ── CTA Final ── */}
      <section
        className="py-24 px-6"
        style={{
          backgroundColor: "var(--bg-surface)",
          borderTop: "1px solid var(--border-soft)",
        }}
      >
        <div
          className="relative mx-auto max-w-3xl overflow-hidden rounded-3xl p-12 text-center"
          style={{ background: "linear-gradient(135deg,#4F46E5 0%,#4338CA 100%)" }}
        >
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle at 20% 50%, rgba(255,255,255,0.07) 0%, transparent 50%)",
            }}
          />
          <h2 className="mb-4 text-3xl font-extrabold text-white md:text-4xl">
            ¿Listo para automatizar
            <br />
            tu contabilidad?
          </h2>
          <p className="mb-8 text-base" style={{ color: "#c7d2fe" }}>
            Únete a los contadores que ya están ahorrando horas cada mes con {BRAND.name}.
          </p>
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <ProximamenteBtn
              className="rounded-xl bg-white px-8 py-3.5 text-sm font-extrabold transition-all hover:scale-105 active:scale-100"
              style={{ color: "#4338CA" }}
            >
              Empezar gratis
            </ProximamenteBtn>
            <Link
              href="/login"
              className="rounded-xl border px-8 py-3.5 text-sm font-semibold text-white transition-all hover:bg-white/10"
              style={{ borderColor: "rgba(255,255,255,0.4)" }}
            >
              Ya tengo cuenta →
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer
        className="border-t py-10 px-6"
        style={{ backgroundColor: "var(--bg-app)", borderColor: "var(--border-soft)" }}
      >
        <div className="mx-auto max-w-6xl flex flex-col items-center gap-6 md:flex-row md:justify-between">
          <Link href="/" className="shrink-0">
            <Image
              src="/brand/Logo-Completo.webp"
              alt={BRAND.name}
              width={130}
              height={32}
              className="block dark:hidden"
              style={{ objectFit: "contain", height: "auto", maxHeight: "32px" }}
            />
            <Image
              src="/brand/Logo-Completo-blanco.webp"
              alt={BRAND.name}
              width={130}
              height={32}
              className="hidden dark:block"
              style={{ objectFit: "contain", height: "auto", maxHeight: "32px" }}
            />
          </Link>

          <div
            className="flex flex-wrap items-center justify-center gap-5 text-sm"
            style={{ color: "var(--text-muted)" }}
          >
            <button type="button" onClick={() => scrollTo("caracteristicas")}
              className="transition-opacity hover:opacity-60"
              style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", font: "inherit" }}
            >
              Características
            </button>
            <button type="button" onClick={() => scrollTo("planes")}
              className="transition-opacity hover:opacity-60"
              style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", font: "inherit" }}
            >
              Planes
            </button>
            <Link href="/legal/terminos" className="transition-opacity hover:opacity-60">
              Términos y Condiciones
            </Link>
            <Link href="/legal/privacidad" className="transition-opacity hover:opacity-60">
              Política de Privacidad
            </Link>
            <Link
              href="/login"
              className="font-semibold transition-opacity hover:opacity-60"
              style={{ color: "var(--brand)" }}
            >
              Iniciar sesión
            </Link>
          </div>

          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            © 2026 {BRAND.name}. Todos los derechos reservados.
          </p>
        </div>
      </footer>
    </div>
  );
}
