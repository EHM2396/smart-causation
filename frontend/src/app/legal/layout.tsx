import Link from "next/link";
import { LogoCiolix } from "@/components/logo-ciolix";
import { ENTIDAD } from "@/lib/legal";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen" style={{ backgroundColor: "var(--bg-app)" }}>
      {/* Franja de marca, igual que en el resto de la app */}
      <div
        data-print="hide"
        className="h-[3px] w-full"
        style={{
          background:
            "linear-gradient(90deg, var(--brand-btn) 0%, var(--brand-accent) 55%, var(--brand-btn-hover) 100%)",
        }}
      />

      <header
        data-print="hide"
        className="sticky top-0 z-20 border-b backdrop-blur"
        style={{
          backgroundColor: "color-mix(in srgb, var(--bg-surface) 85%, transparent)",
          borderColor: "var(--border-soft)",
        }}
      >
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center" aria-label={ENTIDAD.marca}>
            <LogoCiolix variante="completo" ancho={110} alto={32} priority />
          </Link>

          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/legal/terminos"
              className="font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              Términos
            </Link>
            <Link
              href="/legal/privacidad"
              className="font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              Privacidad
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 pb-24 pt-10 sm:px-6">{children}</main>

      <footer
        data-print="hide"
        className="border-t py-8"
        style={{ borderColor: "var(--border-soft)" }}
      >
        <div
          className="mx-auto max-w-3xl px-4 text-xs sm:px-6"
          style={{ color: "var(--text-muted)" }}
        >
          {ENTIDAD.razonSocial} — NIT {ENTIDAD.nit} — {ENTIDAD.ciudad}, {ENTIDAD.pais}
        </div>
      </footer>
    </div>
  );
}
