"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const router = useRouter();

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Token inválido o ausente.");
      return;
    }
    api.verifyEmail(token)
      .then(() => {
        setStatus("success");
        setTimeout(() => router.replace("/login"), 3000);
      })
      .catch((err) => {
        setStatus("error");
        const raw = err instanceof Error ? err.message : "Error al verificar el correo";
        try { setMessage(JSON.parse(raw)?.detail ?? raw); } catch { setMessage(raw); }
      });
  }, [token, router]);

  if (status === "loading") {
    return (
      <div className="flex flex-col items-center gap-4 py-4">
        <Loader2 className="h-10 w-10 animate-spin" style={{ color: "var(--brand)" }} />
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Verificando tu correo...</p>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="space-y-4 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12" style={{ color: "#059669" }} />
        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          ¡Correo verificado correctamente!
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Serás redirigido al login en unos segundos...
        </p>
        <Link href="/login" className="block text-sm font-medium" style={{ color: "var(--brand)" }}>
          Ir al login ahora
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-center">
      <AlertCircle className="mx-auto h-12 w-12" style={{ color: "#ef4444" }} />
      <p className="text-sm font-medium" style={{ color: "#ef4444" }}>
        {message || "No se pudo verificar el correo."}
      </p>
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        El enlace puede haber expirado o ya fue usado.
      </p>
      <Link href="/login" className="block text-sm font-medium" style={{ color: "var(--brand)" }}>
        Volver al login para reenviar
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
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
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Verificación de correo
          </h1>
        </div>

        <Suspense fallback={
          <div className="flex flex-col items-center gap-4 py-4">
            <Loader2 className="h-10 w-10 animate-spin" style={{ color: "var(--brand)" }} />
          </div>
        }>
          <VerifyEmailContent />
        </Suspense>
      </div>
    </div>
  );
}
