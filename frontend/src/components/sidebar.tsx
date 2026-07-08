"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { FileSpreadsheet, BookOpen, History, UserCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/causacion", icon: FileSpreadsheet, label: "Causación", desc: "Procesar facturas DIAN" },
  { href: "/historial", icon: History, label: "Historial", desc: "Facturas causadas" },
  { href: "/catalogos", icon: BookOpen, label: "Catálogos", desc: "Impuestos, PUC, comprobantes" },
];

const NAV_BOTTOM = [
  { href: "/perfil", icon: UserCircle, label: "Mi perfil", desc: "Cuenta y contraseña" },
];

interface SidebarProps {
  onNavigate?: () => void;
  className?: string;
}

export function Sidebar({ onNavigate, className }: SidebarProps) {
  const path = usePathname();

  return (
    <aside
      className={cn("flex h-screen w-64 flex-col", className)}
      style={{
        backgroundColor: "var(--sidebar-bg)",
        borderRight: "1px solid var(--sidebar-border)",
      }}
    >
      {/* Brand */}
      <div
        className="flex items-center px-5 py-4"
        style={{ borderBottom: "1px solid var(--sidebar-border)" }}
      >
        <Image
          src="/brand/Logo-completo-negro.webp"
          alt="Ciolix"
          width={120}
          height={36}
          className="block dark:hidden"
          style={{ objectFit: "contain" }}
          priority
        />
        <Image
          src="/brand/Logo-blanco.webp"
          alt="Ciolix"
          width={120}
          height={36}
          className="hidden dark:block"
          style={{ objectFit: "contain" }}
          priority
        />
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <p
          className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-widest"
          style={{ color: "var(--sidebar-label)" }}
        >
          Principal
        </p>

        {NAV.map(({ href, icon: Icon, label, desc }) => {
          const active = path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={() => onNavigate?.()}
              className={cn("group relative flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all duration-150 no-underline")}
              style={{
                backgroundColor: active ? "var(--sidebar-active-bg)" : "transparent",
                color: active ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
                textDecoration: "none",
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLElement).style.backgroundColor = "var(--sidebar-hover-bg)";
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
              }}
            >
              {/* Active left indicator bar */}
              {active && (
                <span
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full"
                  style={{ backgroundColor: "var(--sidebar-icon-active-color)" }}
                />
              )}

              {/* Icon */}
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors"
                style={{
                  backgroundColor: active
                    ? "var(--sidebar-icon-active-bg)"
                    : "var(--sidebar-icon-bg)",
                }}
              >
                <Icon
                  className="h-4 w-4 transition-colors"
                  style={{ color: active ? "var(--sidebar-icon-active-color)" : "var(--sidebar-text)" }}
                />
              </div>

              {/* Text */}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold leading-none">{label}</p>
                <p className="mt-0.5 truncate text-xs" style={{ color: "var(--sidebar-label)" }}>
                  {desc}
                </p>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Nav bottom */}
      <nav className="px-3 pb-2 space-y-1" style={{ borderTop: "1px solid var(--sidebar-border)", paddingTop: "8px" }}>
        {NAV_BOTTOM.map(({ href, icon: Icon, label, desc }) => {
          const active = path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={() => onNavigate?.()}
              className={cn("group relative flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all duration-150 no-underline")}
              style={{
                backgroundColor: active ? "var(--sidebar-active-bg)" : "transparent",
                color: active ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
                textDecoration: "none",
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLElement).style.backgroundColor = "var(--sidebar-hover-bg)";
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
              }}
            >
              {active && (
                <span
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full"
                  style={{ backgroundColor: "var(--sidebar-icon-active-color)" }}
                />
              )}
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors"
                style={{ backgroundColor: active ? "var(--sidebar-icon-active-bg)" : "var(--sidebar-icon-bg)" }}
              >
                <Icon className="h-4 w-4 transition-colors"
                  style={{ color: active ? "var(--sidebar-icon-active-color)" : "var(--sidebar-text)" }} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold leading-none">{label}</p>
                <p className="mt-0.5 truncate text-xs" style={{ color: "var(--sidebar-label)" }}>{desc}</p>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        className="px-5 py-3 flex items-center gap-2"
        style={{ borderTop: "1px solid var(--sidebar-border)" }}
      >
        <div
          className="h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0"
          style={{ background: "linear-gradient(135deg, #059669 0%, #0891b2 100%)" }}
        >
          C
        </div>
        <p className="text-xs font-medium" style={{ color: "var(--sidebar-label)" }}>
          v1.0 · desarrollo
        </p>
      </div>
    </aside>
  );
}

