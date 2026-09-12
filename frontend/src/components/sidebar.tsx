"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import type { LucideIcon } from "lucide-react";
import { FileSpreadsheet, FileMinus2, BookOpen, History, UserCircle, Users, ReceiptText, DownloadCloud, Save, Loader2, FileCheck2, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useWizardStore } from "@/stores/wizard";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// Rutas que tienen un wizard de causación con borrador en curso.
const RUTAS_WIZARD = ["/causacion", "/causacion-nc", "/causacion-ventas", "/causacion-nc-ventas", "/causacion-soporte", "/causacion-nc-soporte"];

interface NavNode {
  href: string;
  icon: LucideIcon;
  label: string;
  desc: string;
  children?: NavNode[];
}

// "Causación Compras" y "Causación Ventas" son módulos con submódulos (por ahora
// NC; más adelante notas débito).
const NAV: NavNode[] = [
  { href: "/importar", icon: DownloadCloud, label: "Importar DIAN", desc: "Traer todo con un token" },
  {
    href: "/causacion", icon: FileSpreadsheet, label: "Causación Compras", desc: "Facturas de compra DIAN",
    children: [
      { href: "/causacion-nc", icon: FileMinus2, label: "NC Compras", desc: "Notas crédito de compra" },
    ],
  },
  {
    href: "/causacion-ventas", icon: ReceiptText, label: "Causación Ventas", desc: "Facturas de venta DIAN",
    children: [
      { href: "/causacion-nc-ventas", icon: FileMinus2, label: "NC Ventas", desc: "Devoluciones en ventas" },
    ],
  },
  {
    href: "/causacion-soporte", icon: FileCheck2, label: "Documento Soporte", desc: "Compras a no obligados (tipo 05)",
    children: [
      { href: "/causacion-nc-soporte", icon: FileMinus2, label: "Ajuste Soporte", desc: "Notas de ajuste al DS" },
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
  node, active, onNavigate, isChild = false, onIntercept, hasChildren = false, expanded = false,
}: { node: NavNode; active: boolean; onNavigate?: () => void; isChild?: boolean; onIntercept?: (href: string) => boolean; hasChildren?: boolean; expanded?: boolean }) {
  const { href, icon: Icon, label, desc } = node;
  return (
    <Link
      href={href}
      onClick={(e) => {
        // Si hay un borrador en curso y se cambia de módulo, se intercepta para
        // avisar y guardar antes de salir.
        if (onIntercept?.(href)) { e.preventDefault(); return; }
        onNavigate?.();
      }}
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

      {/* Chevron para módulos con submódulos: gira cuando está desplegado */}
      {hasChildren && (
        <ChevronDown
          className="h-4 w-4 shrink-0 transition-transform duration-200"
          style={{ color: "var(--sidebar-label)", transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}
        />
      )}
    </Link>
  );
}

// Grupo de navegación: un módulo y (si tiene) sus submódulos, que se muestran solo
// cuando la sección está ACTIVA (estás dentro) o al pasar el mouse por encima.
function NavGroup({
  node, path, onNavigate, onIntercept,
}: { node: NavNode; path: string; onNavigate?: () => void; onIntercept?: (href: string) => boolean }) {
  const [hover, setHover] = useState(false);
  const tieneHijos = !!node.children?.length;
  const seccionActiva = esActivo(path, node.href) || (node.children?.some((c) => esActivo(path, c.href)) ?? false);
  const abierto = tieneHijos && (seccionActiva || hover);

  return (
    <div
      className="space-y-1"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <NavLink
        node={node}
        active={esActivo(path, node.href)}
        onNavigate={onNavigate}
        onIntercept={onIntercept}
        hasChildren={tieneHijos}
        expanded={abierto}
      />
      {tieneHijos && abierto && (
        <div className="ml-4 space-y-1 border-l pl-2" style={{ borderColor: "var(--sidebar-border)" }}>
          {node.children!.map((child) => (
            <NavLink
              key={child.href}
              node={child}
              active={esActivo(path, child.href)}
              onNavigate={onNavigate}
              onIntercept={onIntercept}
              isChild
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function Sidebar({ onNavigate, className }: SidebarProps) {
  const path = usePathname();
  const router = useRouter();
  const guardarBorradorFn = useWizardStore((s) => s.guardarBorradorFn);
  const [navPendiente, setNavPendiente] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  // ¿Hay que avisar antes de salir? Solo si estamos en un módulo de causación con
  // un borrador en curso y se navega a OTRA ruta distinta.
  const interceptar = (href: string): boolean => {
    const hayTrabajo = RUTAS_WIZARD.includes(path) && !!guardarBorradorFn;
    if (hayTrabajo && href !== path) { setNavPendiente(href); return true; }
    return false;
  };

  const guardarYSalir = async () => {
    if (!navPendiente) return;
    setGuardando(true);
    try {
      const fn = useWizardStore.getState().guardarBorradorFn;
      if (fn) await fn();
    } catch { /* el guardado maneja su propio estado; igual dejamos salir */ }
    setGuardando(false);
    const dest = navPendiente;
    setNavPendiente(null);
    onNavigate?.();
    router.push(dest);
  };

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
          <NavGroup key={node.href} node={node} path={path} onNavigate={onNavigate} onIntercept={interceptar} />
        ))}
      </nav>

      {/* Nav bottom */}
      <nav className="px-3 pb-2 space-y-1" style={{ borderTop: "1px solid var(--sidebar-border)", paddingTop: "8px" }}>
        {NAV_BOTTOM.map((node) => (
          <NavLink key={node.href} node={node} active={esActivo(path, node.href)} onNavigate={onNavigate} onIntercept={interceptar} />
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

      {/* Aviso: guardar el borrador antes de cambiar de módulo */}
      <Dialog open={navPendiente !== null} onOpenChange={(o) => { if (!o && !guardando) setNavPendiente(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Save className="h-5 w-5" style={{ color: "var(--brand)" }} />
              Guardar antes de cambiar
            </DialogTitle>
            <DialogDescription>
              Tienes un borrador en curso en este módulo. Se guardará antes de cambiar
              para no perder tu configuración.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setNavPendiente(null)} disabled={guardando}>
              Cancelar
            </Button>
            <Button onClick={() => { void guardarYSalir(); }} disabled={guardando} className="gap-1.5">
              {guardando ? <><Loader2 className="h-4 w-4 animate-spin" /> Guardando…</> : <><Save className="h-4 w-4" /> Guardar y cambiar</>}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </aside>
  );
}

