"use client";
import Link from "next/link";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import {
  Building2, DownloadCloud, FileSpreadsheet, ReceiptText, FileCheck2,
  History, Users, BookOpen, ArrowRight,
} from "lucide-react";

// Accesos rápidos a los módulos de trabajo. Es la misma navegación del sidebar,
// pero en grande: desde acá el contador entra a trabajar tras elegir la empresa.
const ACCESOS = [
  { href: "/importar", icon: DownloadCloud, label: "Importar DIAN", desc: "Traer todo con un token", color: "#4F46E5" },
  { href: "/causacion", icon: FileSpreadsheet, label: "Causación Compras", desc: "Facturas de compra DIAN", color: "#4F46E5" },
  { href: "/causacion-ventas", icon: ReceiptText, label: "Causación Ventas", desc: "Facturas de venta DIAN", color: "#0ea5a4" },
  { href: "/causacion-soporte", icon: FileCheck2, label: "Documento Soporte", desc: "Compras a no obligados", color: "#0284c7" },
  { href: "/historial", icon: History, label: "Historial", desc: "Facturas causadas", color: "#7c3aed" },
  { href: "/terceros", icon: Users, label: "Terceros", desc: "Proveedores y vendedores", color: "#d97706" },
  { href: "/catalogos", icon: BookOpen, label: "Catálogos", desc: "Impuestos, PUC, comprobantes", color: "#0f766e" },
];

/**
 * Pantalla de inicio tras elegir (o cambiar de) empresa.
 *
 * Existe para que el cambio de empresa sea EVIDENTE: antes, al cambiar, el usuario
 * se quedaba dentro del mismo módulo y la única señal era el nombre en el selector
 * del sidebar, lo que se presta a trabajar sobre la empresa equivocada.
 */
export default function InicioPage() {
  const empresaId = useAuthStore((s) => s.empresaId);
  const empresaNombre = useAuthStore((s) => s.empresaNombre);
  const token = useAuthStore((s) => s.token);

  const { data: empresas = [] } = useQuery({
    queryKey: ["mis-empresas"],
    queryFn: api.misEmpresas,
    enabled: !!token,
  });

  const empresa = empresas.find((e) => e.id === empresaId);
  const nombre = empresaNombre ?? empresa?.nombre ?? "—";
  const nit = empresa?.nit;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      {/* Identidad de la empresa activa */}
      <div
        className="rounded-2xl border p-8 text-center"
        style={{
          borderColor: "var(--border-soft)",
          backgroundColor: "var(--bg-surface)",
          boxShadow: "var(--shadow-card)",
        }}
      >
        <Image
          src="/brand/Logo-completo-negro.webp"
          alt="Ciolix"
          width={132}
          height={40}
          className="mx-auto block dark:hidden"
          style={{ objectFit: "contain", width: "auto", height: "auto", maxWidth: "132px", maxHeight: "40px" }}
          priority
        />
        <Image
          src="/brand/Logo-blanco.webp"
          alt="Ciolix"
          width={132}
          height={40}
          className="mx-auto hidden dark:block"
          style={{ objectFit: "contain", width: "auto", height: "auto", maxWidth: "132px", maxHeight: "40px" }}
          priority
        />

        <p
          className="mt-8 flex items-center justify-center gap-1.5 text-xs font-semibold uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}
        >
          <Building2 className="h-3.5 w-3.5" /> Estás trabajando en
        </p>

        <h1
          className="mt-2 text-3xl font-bold leading-tight sm:text-4xl"
          style={{ color: "var(--text-primary)" }}
        >
          {nombre}
        </h1>

        {nit && (
          <p className="mt-2 font-mono text-sm" style={{ color: "var(--text-muted)" }}>
            NIT {nit}
          </p>
        )}

        <p className="mx-auto mt-5 max-w-lg text-sm" style={{ color: "var(--text-secondary)" }}>
          Todo lo que causes a partir de ahora queda registrado en esta empresa.
          Si no es la correcta, cámbiala en el selector de la barra lateral.
        </p>
      </div>

      {/* Accesos a los módulos */}
      <p
        className="mb-3 mt-10 px-1 text-[11px] font-semibold uppercase tracking-widest"
        style={{ color: "var(--text-muted)" }}
      >
        Empezar a trabajar
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {ACCESOS.map(({ href, icon: Icon, label, desc, color }) => (
          <Link
            key={href}
            href={href}
            className="group flex items-center gap-3 rounded-xl border p-4 no-underline transition-opacity hover:opacity-80"
            style={{
              borderColor: "var(--border-soft)",
              backgroundColor: "var(--bg-surface)",
              textDecoration: "none",
            }}
          >
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
              style={{ backgroundColor: `${color}1A` }}
            >
              <Icon className="h-5 w-5" style={{ color }} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{label}</p>
              <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>{desc}</p>
            </div>
            <ArrowRight className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
          </Link>
        ))}
      </div>
    </div>
  );
}
