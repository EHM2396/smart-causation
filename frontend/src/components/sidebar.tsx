"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { FileSpreadsheet, FileMinus2, BookOpen, History, UserCircle, Users } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavNode {
  href: string;
  icon: LucideIcon;
  label: string;
  desc: string;
  children?: NavNode[];
}

// "Causación Compras" es un módulo con submódulos (por ahora NC; más adelante
// notas débito). A futuro habrá también "Causación Ventas" con sus submódulos.
const NAV: NavNode[] = [
  {
    href: "/causacion", icon: FileSpreadsheet, label: "Causación Compras", desc: "Facturas de compra DIAN",
    children: [
      { href: "/causacion-nc", icon: FileMinus2, label: "NC Compras", desc: "Notas crédito de compra" },
    ],
  },
  { href: "/historial", icon: History, label: "Historial", desc: "Facturas causadas" },
  { href: "/terceros", icon: Users, label: "Terceros", desc: "Proveedores y vendedores" },
  { href: "/catalogos", icon: BookOpen, label: "Catálogos", desc: "Impuestos, PUC, comprobantes" },
];

// Activo exacto: evita que "/causacion" quede activo estando en "/causacion-nc".
function esActivo(path: string, href: string): boolean {
  return path === href || path.startsWith(href + "/");
}

const NAV_BOTTOM: NavNode[] = [
  { href: "/perfil", icon: UserCircle, label: "Mi perfil", desc: "Cuenta y contraseña" },
];

interface SidebarProps {
  onNavigate?: () => void;
  className?: string;
}

function NavLink({
  node, active, onNavigate, isChild = false,
}: { node: NavNode; active: boolean; onNavigate?: () => void; isChild?: boolean }) {
  const { href, icon: Icon, label, desc } = node;
  return (
    <Link
      href={href}
      onClick={() => onNavigate?.()}
      className={cn(
        "group relative flex items-center gap-3 rounded-lg transition-all duration-150 no-underline",
        isChild ? "py-2 pl-4 pr-3" : "px-3 py-2.5",
      )}
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
        className={cn(
          "flex shrink-0 items-center justify-center rounded-md transition-colors",
          isChild ? "h-6 w-6" : "h-7 w-7",
        )}
        style={{ backgroundColor: active ? "var(--sidebar-icon-active-bg)" : "var(--sidebar-icon-bg)" }}
      >
        <Icon
          className={cn("transition-colors", isChild ? "h-3.5 w-3.5" : "h-4 w-4")}
          style={{ color: active ? "var(--sidebar-icon-active-color)" : "var(--sidebar-text)" }}
        />
      </div>

      {/* Text */}
      <div className="min-w-0 flex-1">
        <p className={cn("font-semibold leading-none", isChild ? "text-[13px]" : "text-sm")}>{label}</p>
        <p className="mt-0.5 truncate text-xs" style={{ color: "var(--sidebar-label)" }}>{desc}</p>
      </div>
    </Link>
  );
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
          style={{ objectFit: "contain", width: "auto", height: "auto", maxWidth: "120px", maxHeight: "36px" }}
          priority
        />
        <Image
          src="/brand/Logo-blanco.webp"
          alt="Ciolix"
          width={120}
          height={36}
          className="hidden dark:block"
          style={{ objectFit: "contain", width: "auto", height: "auto", maxWidth: "120px", maxHeight: "36px" }}
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

        {NAV.map((node) => (
          <div key={node.href} className="space-y-1">
            <NavLink node={node} active={esActivo(path, node.href)} onNavigate={onNavigate} />
            {node.children && node.children.length > 0 && (
              <div
                className="ml-4 space-y-1 border-l pl-2"
                style={{ borderColor: "var(--sidebar-border)" }}
              >
                {node.children.map((child) => (
                  <NavLink key={child.href} node={child} active={esActivo(path, child.href)} onNavigate={onNavigate} isChild />
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* Nav bottom */}
      <nav className="px-3 pb-2 space-y-1" style={{ borderTop: "1px solid var(--sidebar-border)", paddingTop: "8px" }}>
        {NAV_BOTTOM.map((node) => (
          <NavLink key={node.href} node={node} active={esActivo(path, node.href)} onNavigate={onNavigate} />
        ))}
      </nav>

      {/* Footer */}
      <div
        className="px-5 py-3 flex items-center gap-2"
        style={{ borderTop: "1px solid var(--sidebar-border)" }}
      >
        <div
          className="h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0"
          style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
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

