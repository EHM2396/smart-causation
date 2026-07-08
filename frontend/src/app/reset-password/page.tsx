"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Loader2, CheckCircle2, AlertCircle, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const router = useRouter();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) { setError("La contraseña debe tener al menos 8 caracteres."); return; }
    if (password !== confirm) { setError("Las contraseñas no coinciden."); return; }
    if (!token) { setError("Token inválido o ausente."); return; }

    setLoading(true);
    setError("");
    try {
      await api.resetPassword(token, password);
      setSuccess(true);
      setTimeout(() => router.replace("/login"), 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al restablecer la contraseña";
      try { setError(JSON.parse(msg)?.detail ?? msg); } catch { setError(msg); }
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="text-center space-y-3">
        <AlertCircle className="mx-auto h-12 w-12" style={{ color: "#ef4444" }} />
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Enlace inválido o expirado.</p>
        <Link href="/forgot-password" className="text-sm font-medium" style={{ color: "var(--brand)" }}>
          Solicitar un nuevo enlace
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="text-center space-y-3">
        <CheckCircle2 className="mx-auto h-12 w-12" style={{ color: "#059669" }} />
        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          ¡Contraseña actualizada!
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Serás redirigido al login en unos segundos...
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Nueva contraseña
        </label>
        <input
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mínimo 8 caracteres"
          className="w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors"
          style={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
        />
      </div>
      <div>
        <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          Confirmar contraseña
        </label>
        <input
          type="password"
          required
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Repite la contraseña"
          className="w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors"
          style={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
        style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {loading ? "Guardando..." : "Guardar nueva contraseña"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: "var(--bg-app)" }}>
      <div
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)", boxShadow: "var(--shadow-md)" }}
      >
        <div className="mb-8 text-center">
          <div
            className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl"
            style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-white" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Nueva contraseña</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>Elige una contraseña segura</p>
        </div>

        <Suspense fallback={<div className="text-center text-sm" style={{ color: "var(--text-muted)" }}>Cargando...</div>}>
          <ResetPasswordForm />
        </Suspense>

        <p className="mt-6 text-center text-sm">
          <Link href="/login" className="flex items-center justify-center gap-1.5 font-medium" style={{ color: "var(--brand)" }}>
            <ArrowLeft className="h-3.5 w-3.5" /> Volver al login
          </Link>
        </p>
      </div>
    </div>
  );
}
