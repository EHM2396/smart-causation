"use client";

import { Menu, X, Search } from "lucide-react";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { ThemeToggle } from "@/components/theme-toggle";

const PAGE_META: Record<string, { title: string; description: string }> = {
  "/causacion": {
    title: "Causación",
    description: "Procesá facturas DIAN y generá archivos SIIGO",
  },
  "/catalogos": {
    title: "Catálogos",
    description: "Administrá impuestos, cuentas PUC y tipos de comprobante",
  },
  "/historial": {
    title: "Historial",
    description: "Registro de facturas causadas y regeneración de archivos SIIGO",
  },
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  const match = Object.entries(PAGE_META).find(([key]) => pathname.startsWith(key));
  const pageMeta = match ? match[1] : { title: "Smart Causación", description: "" };

  return (
    <div
      className="flex h-screen flex-col overflow-hidden"
      style={{ backgroundColor: "var(--bg-app)", color: "var(--text-primary)" }}
    >
      {/* Brand accent stripe — top of every page */}
      <div
        className="h-[3px] w-full shrink-0"
        style={{ background: "linear-gradient(90deg, #059669 0%, #0891b2 55%, #047857 100%)" }}
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Desktop sidebar */}
        <div className="hidden flex-shrink-0 lg:block">
          <Sidebar />
        </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="Cerrar menú"
          style={{ backgroundColor: "rgba(0,0,0,0.55)" }}
        />
      )}

      {/* Mobile sidebar slide-in */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out lg:hidden ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar onNavigate={() => setSidebarOpen(false)} className="h-full" />
      </div>

      {/* Right side: topbar + content */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Mobile header */}
        <header
          className="flex h-14 flex-shrink-0 items-center justify-between border-b px-4 lg:hidden"
          style={{
            backgroundColor: "var(--bg-surface)",
            borderColor: "var(--border-soft)",
            boxShadow: "var(--shadow-xs)",
          }}
        >
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSidebarOpen((v) => !v)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border"
              style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)" }}
              aria-label={sidebarOpen ? "Cerrar menú" : "Abrir menú"}
            >
              {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
            <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Smart Causación
            </span>
          </div>
          <ThemeToggle />
        </header>

        {/* Desktop topbar */}
        <header
          className="hidden h-14 flex-shrink-0 items-center justify-between border-b px-6 lg:flex"
          style={{
            backgroundColor: "var(--bg-surface)",
            borderColor: "var(--border-soft)",
            boxShadow: "var(--shadow-xs)",
          }}
        >
          <div className="flex items-center gap-3">
            {/* Page breadcrumb pill */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Smart Causación</span>
              <span style={{ color: "var(--border-strong)" }}>/</span>
              <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{pageMeta.title}</span>
            </div>
            {pageMeta.description && (
              <span
                className="hidden xl:inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border-soft)" }}
              >
                {pageMeta.description}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm"
              style={{
                borderColor: "var(--border-soft)",
                color: "var(--text-muted)",
                backgroundColor: "var(--bg-elevated)",
              }}
              aria-label="Buscar"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Buscar...</span>
              <kbd
                className="ml-1 hidden rounded px-1.5 py-0.5 text-[10px] font-mono sm:inline"
                style={{ backgroundColor: "var(--border-soft)", color: "var(--text-muted)" }}
              >
                ⌘K
              </kbd>
            </button>
            <ThemeToggle />
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
      </div>
    </div>
  );
}

