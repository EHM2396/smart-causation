"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api.login(email, password);
      login(data);
      router.replace("/causacion");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al iniciar sesión");
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
        {/* Logo/brand */}
        <div className="mb-8 text-center">
          <div
            className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl"
            style={{ background: "linear-gradient(135deg, #059669 0%, #0891b2 100%)" }}
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-white" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Smart Causación
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
            Inicia sesión para continuar
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="mb-1.5 block text-sm font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@empresa.com"
              className="w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors"
              style={{
                backgroundColor: "var(--bg-elevated)",
                borderColor: "var(--border-soft)",
                color: "var(--text-primary)",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1.5 block text-sm font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors"
              style={{
                backgroundColor: "var(--bg-elevated)",
                borderColor: "var(--border-soft)",
                color: "var(--text-primary)",
              }}
            />
          </div>

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
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
            style={{ background: "linear-gradient(135deg, #059669 0%, #0891b2 100%)" }}
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Ingresando..." : "Ingresar"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)" }}>
          ¿No tienes cuenta?{" "}
          <Link
            href="/registro"
            className="font-medium"
            style={{ color: "var(--brand)" }}
          >
            Regístrate
          </Link>
        </p>
      </div>
    </div>
  );
}
