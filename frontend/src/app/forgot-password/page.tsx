"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, CheckCircle2, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    await api.forgotPassword(email);
    setSent(true);
    setLoading(false);
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: "var(--bg-app)" }}>
      <div
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)", boxShadow: "var(--shadow-md)" }}
      >
        <div className="mb-8 text-center">
          <div
            className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl"
            style={{ background: "linear-gradient(135deg, #4F46E5 0%, #8FB5FF 100%)" }}
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-white" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Recuperar contraseña
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
            Te enviaremos un enlace para restablecerla
          </p>
        </div>

        {sent ? (
          <div className="space-y-4 text-center">
            <div className="flex justify-center">
              <CheckCircle2 className="h-12 w-12" style={{ color: "#059669" }} />
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Si el correo está registrado, recibirás el enlace en breve.
            </p>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Revisa tu bandeja de entrada y la carpeta de spam.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
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
                style={{ backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-soft)", color: "var(--text-primary)" }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
              style={{ background: "linear-gradient(135deg, #4F46E5 0%, #8FB5FF 100%)" }}
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Enviando..." : "Enviar enlace"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm">
          <Link href="/login" className="flex items-center justify-center gap-1.5 font-medium" style={{ color: "var(--brand)" }}>
            <ArrowLeft className="h-3.5 w-3.5" /> Volver al login
          </Link>
        </p>
      </div>
    </div>
  );
}
