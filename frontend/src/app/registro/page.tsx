"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, MailCheck } from "lucide-react";
import { LogoCiolix } from "@/components/logo-ciolix";
import { api } from "@/lib/api";
import { VERSION_LEGAL } from "@/lib/legal";
import { useAuthStore } from "@/stores/auth";

export default function RegistroPage() {
  const [form, setForm] = useState({
    nombre: "",
    email: "",
    password: "",
    nombre_empresa: "",
    nit_empresa: "",
  });
  const [aceptaLegal, setAceptaLegal] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [registradoEmail, setRegistradoEmail] = useState("");
  const login = useAuthStore((s) => s.login);
  const router = useRouter();

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!aceptaLegal) {
      setError("Debes aceptar los Términos y Condiciones y la Política de Privacidad");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api.registro({
        email: form.email,
        password: form.password,
        nombre: form.nombre,
        nombre_empresa: form.nombre_empresa,
        nit_empresa: form.nit_empresa || undefined,
        acepta_legal: true,
        version_legal: VERSION_LEGAL,
      });
      login(data);
      if (!data.email_verificado) {
        setRegistradoEmail(form.email);
      } else {
        router.replace("/causacion");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al registrarse");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center p-4"
      style={{ backgroundColor: "var(--bg-app)" }}
    >
      <div
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{
          backgroundColor: "var(--bg-surface)",
          borderColor: "var(--border-soft)",
          boxShadow: "var(--shadow-md)",
        }}
      >
        {registradoEmail ? (
          <div className="space-y-5 text-center">
            <MailCheck className="mx-auto h-14 w-14" style={{ color: "#059669" }} />
            <div>
              <p className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                ¡Cuenta creada!
              </p>
              <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                Te enviamos un correo de verificación a{" "}
                <strong>{registradoEmail}</strong>.
                <br />
                Revisa tu bandeja y haz clic en el enlace para activar tu cuenta.
              </p>
            </div>
            <Link
              href="/login"
              className="block w-full rounded-lg px-4 py-2.5 text-sm font-semibold text-white text-center"
              style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
            >
              Ir al login
            </Link>
          </div>
        ) : (
          <>
            <div className="mb-8 text-center">
              <div className="mx-auto mb-4 flex items-center justify-center">
                <LogoCiolix variante="login" priority />
              </div>
              <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                Crear cuenta
              </h1>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                  Nombre completo
                </label>
                <input
                  name="nombre"
                  type="text"
                  required
                  value={form.nombre}
                  onChange={handleChange}
                  placeholder="Juan Pérez"
                  className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                  style={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                  Email
                </label>
                <input
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={form.email}
                  onChange={handleChange}
                  placeholder="tu@empresa.com"
                  className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                  style={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                  Contraseña
                </label>
                <input
                  name="password"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="••••••••"
                  className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                  style={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
                />
              </div>

              <div
                className="rounded-lg border p-3"
                style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
              >
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  Datos de la empresa
                </p>
                <div className="space-y-3">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                      Nombre de la empresa
                    </label>
                    <input
                      name="nombre_empresa"
                      type="text"
                      required
                      value={form.nombre_empresa}
                      onChange={handleChange}
                      placeholder="Mi Empresa S.A.S"
                      className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                      style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                      NIT <span style={{ color: "var(--text-muted)" }}>(opcional)</span>
                    </label>
                    <input
                      name="nit_empresa"
                      type="text"
                      value={form.nit_empresa}
                      onChange={handleChange}
                      placeholder="900123456-1"
                      className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                      style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
                    />
                  </div>
                </div>
              </div>

              {/*
                Casilla de aceptación. Nunca debe venir premarcada: la Ley 1581
                de 2012 exige consentimiento expreso e inequívoco, y una casilla
                marcada por defecto no lo acredita.
              */}
              <label className="flex cursor-pointer items-start gap-2.5">
                <input
                  type="checkbox"
                  name="acepta_legal"
                  checked={aceptaLegal}
                  onChange={(e) => setAceptaLegal(e.target.checked)}
                  className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded"
                  style={{ accentColor: "var(--brand-btn)" }}
                />
                <span className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  He leído y acepto los{" "}
                  <Link
                    href="/legal/terminos"
                    target="_blank"
                    className="font-medium underline"
                    style={{ color: "var(--brand)" }}
                  >
                    Términos y Condiciones
                  </Link>{" "}
                  y autorizo el tratamiento de mis datos personales conforme a la{" "}
                  <Link
                    href="/legal/privacidad"
                    target="_blank"
                    className="font-medium underline"
                    style={{ color: "var(--brand)" }}
                  >
                    Política de Privacidad
                  </Link>
                  , incluida la transmisión a proveedores en el exterior descrita en ella.
                </span>
              </label>

              {error && (
                <p
                  className="rounded-lg px-3 py-2 text-sm"
                  style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#ef4444" }}
                >
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || !aceptaLegal}
                className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
                style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                {loading ? "Creando cuenta..." : "Crear cuenta"}
              </button>
            </form>

            <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)" }}>
              ¿Ya tienes cuenta?{" "}
              <Link href="/login" className="font-medium" style={{ color: "var(--brand)" }}>
                Inicia sesión
              </Link>
            </p>

            <p
              className="mt-4 border-t pt-4 text-center text-xs"
              style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}
            >
              <Link href="/legal/terminos">Términos y Condiciones</Link>
              {" · "}
              <Link href="/legal/privacidad">Política de Privacidad</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
