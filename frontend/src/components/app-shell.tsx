"use client";

import { Menu, X, LogOut, UserCircle } from "lucide-react";
import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { Sidebar } from "@/components/sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuthStore } from "@/stores/auth";
import { useWizardStore } from "@/stores/wizard";
import { Tutorial } from "@/components/tutorial/tutorial";

// Rutas que se renderizan sin el shell y sin exigir sesión.
// /legal debe ser accesible para cualquiera: los documentos legales tienen que
// poder consultarse ANTES de registrarse, no solo desde una cuenta activa.
const AUTH_PATHS = ["/login", "/registro", "/legal", "/forgot-password", "/reset-password", "/verify-email"];

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
  "/perfil": {
    title: "Mi perfil",
    description: "Información personal, empresa y contraseña",
  },
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, usuario, logout, _hydrated } = useAuthStore();
  const resetWizard = useWizardStore((s) => s.reset);

  const isAuthPage = AUTH_PATHS.some((p) => pathname.startsWith(p));

  // Redirect only after hydration is complete to avoid F5 false-logout
  useEffect(() => {
    if (_hydrated && !isAuthPage && !token) {
      router.replace("/login");
    }
  }, [_hydrated, isAuthPage, token, router]);

  // Auto-logout after 10 minutes of inactivity
  useEffect(() => {
    if (isAuthPage || !token) return;

    const TIMEOUT = 10 * 60 * 1000;
    let timer: ReturnType<typeof setTimeout>;

    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        queryClient.clear();
        logout();
        router.replace("/login");
      }, TIMEOUT);
    };

    const events = ["mousemove", "mousedown", "keydown", "touchstart", "scroll", "click"] as const;
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();

    return () => {
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [isAuthPage, token, logout, queryClient, router]);

  // Render auth pages without the shell
  if (isAuthPage) {
    return <>{children}</>;
  }

  // Wait for hydration before deciding to redirect
  if (!_hydrated) {
    return null;
  }

  if (!token) {
    return null;
  }

  const match = Object.entries(PAGE_META).find(([key]) => pathname.startsWith(key));
  const pageMeta = match ? match[1] : { title: "Ciolix", description: "" };

  return (
    <div
      className="flex h-screen flex-col overflow-hidden"
      style={{ backgroundColor: "var(--bg-app)", color: "var(--text-primary)" }}
    >
      {/* Brand accent stripe — top of every page */}
      <div
        className="h-[3px] w-full shrink-0"
        style={{ background: "linear-gradient(90deg, var(--brand-btn) 0%, var(--brand-accent) 55%, var(--brand-btn-hover) 100%)" }}
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
              Ciolix
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <button
              type="button"
              onClick={() => { resetWizard(); queryClient.clear(); logout(); router.replace("/login"); }}
              className="flex h-9 w-9 items-center justify-center rounded-lg border"
              style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}
              title="Cerrar sesión"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
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
              <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Ciolix</span>
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
            <ThemeToggle />
            {usuario && (
              <div className="flex items-center gap-2 border-l pl-2" style={{ borderColor: "var(--border-soft)" }}>
                <Link
                  href="/perfil"
                  className="hidden items-center gap-1.5 rounded-lg px-2 py-1 text-xs transition-colors lg:flex"
                  style={{ color: "var(--text-muted)" }}
                  title="Mi perfil"
                >
                  <UserCircle className="h-3.5 w-3.5" />
                  {usuario.nombre}
                </Link>
                <button
                  type="button"
                  onClick={() => { resetWizard(); queryClient.clear(); logout(); router.replace("/login"); }}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border"
                  style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}
                  title="Cerrar sesión"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
      </div>
      <Tutorial />
    </div>
  );
}

