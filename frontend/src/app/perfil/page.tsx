"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, CheckCircle2, AlertCircle, User, Building2, Lock, Eye, EyeOff, BookOpen, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

// ── Validación de contraseña ──────────────────────────────────────────────────

function checkPassword(pw: string) {
  return {
    length: pw.length >= 8,
    uppercase: /[A-Z]/.test(pw),
    number: /\d/.test(pw),
    special: /[!@#$%^&*()\-_=+[\]{};:'",.<>/?\\|`~]/.test(pw),
  };
}

const REQS = [
  { key: "length" as const,    label: "Mínimo 8 caracteres" },
  { key: "uppercase" as const, label: "Al menos una mayúscula" },
  { key: "number" as const,    label: "Al menos un número" },
  { key: "special" as const,   label: "Al menos un carácter especial (!@#$...)" },
];

const STRENGTH_LABELS = ["", "Muy débil", "Débil", "Aceptable", "Segura"];
const STRENGTH_COLORS = ["", "#ef4444", "#f97316", "#eab308", "#22c55e"];

function PasswordStrengthBar({ password }: { password: string }) {
  const checks = checkPassword(password);
  const score = Object.values(checks).filter(Boolean).length;
  if (!password) return null;

  return (
    <div className="mt-2 space-y-2">
      {/* Barra */}
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-1.5 flex-1 rounded-full transition-all duration-300"
            style={{ backgroundColor: i <= score ? STRENGTH_COLORS[score] : "var(--border-soft)" }}
          />
        ))}
      </div>
      <p className="text-xs font-medium" style={{ color: STRENGTH_COLORS[score] }}>
        {STRENGTH_LABELS[score]}
      </p>
      {/* Requisitos */}
      <div className="space-y-1">
        {REQS.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-1.5">
            <div
              className="h-3.5 w-3.5 rounded-full flex items-center justify-center shrink-0 transition-colors"
              style={{ backgroundColor: checks[key] ? "#22c55e" : "var(--border-soft)" }}
            >
              {checks[key] && (
                <svg viewBox="0 0 12 12" className="h-2 w-2 text-white" fill="none" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l3 3 5-5" />
                </svg>
              )}
            </div>
            <span className="text-xs" style={{ color: checks[key] ? "#22c55e" : "var(--text-muted)" }}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

type Feedback = { type: "success" | "error"; message: string };

function FeedbackMsg({ fb }: { fb: Feedback }) {
  return (
    <div
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
      style={{
        backgroundColor: fb.type === "success" ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
        color: fb.type === "success" ? "#22c55e" : "#ef4444",
      }}
    >
      {fb.type === "success"
        ? <CheckCircle2 className="h-4 w-4 shrink-0" />
        : <AlertCircle className="h-4 w-4 shrink-0" />}
      {fb.message}
    </div>
  );
}

export default function PerfilPage() {
  const router = useRouter();
  const { usuario, setTutorialPendiente } = useAuthStore();

  // ── Info personal + empresa ───────────────────────────────────────────────
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [nombreEmpresa, setNombreEmpresa] = useState("");
  const [nit, setNit] = useState("");
  const [loadingPerfil, setLoadingPerfil] = useState(false);
  const [fbPerfil, setFbPerfil] = useState<Feedback | null>(null);

  // ── Contraseña ────────────────────────────────────────────────────────────
  const [pwActual, setPwActual] = useState("");
  const [pwNueva, setPwNueva] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [showActual, setShowActual] = useState(false);
  const [showNueva, setShowNueva] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loadingPw, setLoadingPw] = useState(false);
  const [fbPw, setFbPw] = useState<Feedback | null>(null);

  const checks = checkPassword(pwNueva);
  const pwValida = Object.values(checks).every(Boolean);
  const pwCoincide = pwNueva === pwConfirm && pwConfirm.length > 0;

  useEffect(() => {
    api.me().then((data) => {
      setNombre(data.nombre ?? "");
      setEmail(data.email ?? "");
      setNombreEmpresa(data.empresa_nombre ?? "");
      setNit(data.empresa_nit ?? "");
    });
  }, []);

  async function handleGuardarPerfil(e: React.FormEvent) {
    e.preventDefault();
    setLoadingPerfil(true);
    setFbPerfil(null);
    try {
      const res = await api.actualizarPerfil({
        nombre,
        nombre_empresa: nombreEmpresa,
        nit_empresa: nit || undefined,
      });
      setFbPerfil({ type: "success", message: res.message });
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Error al guardar";
      try { setFbPerfil({ type: "error", message: JSON.parse(raw)?.detail ?? raw }); }
      catch { setFbPerfil({ type: "error", message: raw }); }
    } finally {
      setLoadingPerfil(false);
    }
  }

  async function handleCambiarPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!pwValida) { setFbPw({ type: "error", message: "La contraseña no cumple los requisitos" }); return; }
    if (!pwCoincide) { setFbPw({ type: "error", message: "Las contraseñas no coinciden" }); return; }
    setLoadingPw(true);
    setFbPw(null);
    try {
      const res = await api.cambiarPassword({ password_actual: pwActual, nueva_password: pwNueva });
      setFbPw({ type: "success", message: res.message });
      setPwActual(""); setPwNueva(""); setPwConfirm("");
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Error al cambiar contraseña";
      try { setFbPw({ type: "error", message: JSON.parse(raw)?.detail ?? raw }); }
      catch { setFbPw({ type: "error", message: raw }); }
    } finally {
      setLoadingPw(false);
    }
  }

  const inputCls = "w-full rounded-lg border px-3 py-2 text-sm outline-none transition-colors";
  const inputStyle = { backgroundColor: "var(--bg-elevated)", borderColor: "var(--border-soft)", color: "var(--text-primary)" };
  const labelCls = "mb-1.5 block text-sm font-medium";
  const labelStyle = { color: "var(--text-secondary)" };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4 lg:p-8">
      <div>
        <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Mi perfil</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          Administra tu información personal y de empresa
        </p>
      </div>

      {/* ── Información ────────────────────────────────────────────────────── */}
      <form
        onSubmit={handleGuardarPerfil}
        className="rounded-2xl border p-6 space-y-5"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)" }}
      >
        <div className="flex items-center gap-2 pb-1" style={{ borderBottom: "1px solid var(--border-soft)" }}>
          <User className="h-4 w-4" style={{ color: "var(--brand)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Información personal
          </h2>
        </div>

        <div>
          <label className={labelCls} style={labelStyle}>Nombre completo</label>
          <input
            type="text"
            required
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            className={inputCls}
            style={inputStyle}
          />
        </div>

        <div>
          <label className={labelCls} style={labelStyle}>Correo electrónico</label>
          <div className="relative">
            <input
              type="email"
              value={email}
              disabled
              className={`${inputCls} pr-10 cursor-not-allowed opacity-60`}
              style={inputStyle}
            />
            <Lock className="absolute right-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5" style={{ color: "var(--text-muted)" }} />
          </div>
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            El correo no puede modificarse
          </p>
        </div>

        <div className="pt-1" style={{ borderTop: "1px solid var(--border-soft)" }}>
          <div className="flex items-center gap-2 pb-4 pt-3">
            <Building2 className="h-4 w-4" style={{ color: "var(--brand)" }} />
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Empresa</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className={labelCls} style={labelStyle}>Nombre de la empresa</label>
              <input
                type="text"
                required
                value={nombreEmpresa}
                onChange={(e) => setNombreEmpresa(e.target.value)}
                className={inputCls}
                style={inputStyle}
              />
            </div>
            <div>
              <label className={labelCls} style={labelStyle}>
                NIT <span style={{ color: "var(--text-muted)" }}>(opcional)</span>
              </label>
              <input
                type="text"
                value={nit}
                onChange={(e) => setNit(e.target.value)}
                placeholder="900123456-1"
                className={inputCls}
                style={inputStyle}
              />
            </div>
          </div>
        </div>

        {fbPerfil && <FeedbackMsg fb={fbPerfil} />}

        <button
          type="submit"
          disabled={loadingPerfil}
          className="flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
          style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
        >
          {loadingPerfil && <Loader2 className="h-4 w-4 animate-spin" />}
          {loadingPerfil ? "Guardando..." : "Guardar cambios"}
        </button>
      </form>

      {/* ── Contraseña ──────────────────────────────────────────────────────── */}
      <form
        onSubmit={handleCambiarPassword}
        className="rounded-2xl border p-6 space-y-5"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)" }}
      >
        <div className="flex items-center gap-2 pb-1" style={{ borderBottom: "1px solid var(--border-soft)" }}>
          <Lock className="h-4 w-4" style={{ color: "var(--brand)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Cambiar contraseña
          </h2>
        </div>

        {/* Contraseña actual */}
        <div>
          <label className={labelCls} style={labelStyle}>Contraseña actual</label>
          <div className="relative">
            <input
              type={showActual ? "text" : "password"}
              required
              value={pwActual}
              onChange={(e) => setPwActual(e.target.value)}
              placeholder="••••••••"
              className={`${inputCls} pr-10`}
              style={inputStyle}
            />
            <button type="button" onClick={() => setShowActual((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }}>
              {showActual ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Nueva contraseña */}
        <div>
          <label className={labelCls} style={labelStyle}>Nueva contraseña</label>
          <div className="relative">
            <input
              type={showNueva ? "text" : "password"}
              required
              value={pwNueva}
              onChange={(e) => setPwNueva(e.target.value)}
              placeholder="••••••••"
              className={`${inputCls} pr-10`}
              style={inputStyle}
            />
            <button type="button" onClick={() => setShowNueva((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }}>
              {showNueva ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <PasswordStrengthBar password={pwNueva} />
        </div>

        {/* Confirmar */}
        <div>
          <label className={labelCls} style={labelStyle}>Confirmar nueva contraseña</label>
          <div className="relative">
            <input
              type={showConfirm ? "text" : "password"}
              required
              value={pwConfirm}
              onChange={(e) => setPwConfirm(e.target.value)}
              placeholder="••••••••"
              className={`${inputCls} pr-10`}
              style={inputStyle}
            />
            <button type="button" onClick={() => setShowConfirm((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }}>
              {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {pwConfirm.length > 0 && (
            <p className="mt-1 text-xs" style={{ color: pwCoincide ? "#22c55e" : "#ef4444" }}>
              {pwCoincide ? "✓ Las contraseñas coinciden" : "Las contraseñas no coinciden"}
            </p>
          )}
        </div>

        {fbPw && <FeedbackMsg fb={fbPw} />}

        <button
          type="submit"
          disabled={loadingPw || !pwActual || !pwNueva || !pwConfirm}
          className="flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white transition-opacity disabled:opacity-60"
          style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
        >
          {loadingPw && <Loader2 className="h-4 w-4 animate-spin" />}
          {loadingPw ? "Actualizando..." : "Cambiar contraseña"}
        </button>
      </form>

      {/* ── Tutorial ────────────────────────────────────────────────────────── */}
      <div
        className="rounded-2xl border p-6 space-y-4"
        style={{ backgroundColor: "var(--bg-surface)", borderColor: "var(--border-soft)" }}
      >
        <div className="flex items-center gap-2 pb-1" style={{ borderBottom: "1px solid var(--border-soft)" }}>
          <BookOpen className="h-4 w-4" style={{ color: "var(--brand)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Tutorial</h2>
        </div>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Reinicia el tutorial paso a paso para volver a ver cómo funciona la plataforma desde el principio.
        </p>
        <button
          type="button"
          onClick={async () => {
            await api.actualizarTutorial(true).catch(() => {});
            setTutorialPendiente(true);
            router.push("/causacion");
          }}
          className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-opacity hover:opacity-80"
          style={{ backgroundColor: "var(--brand)", color: "#fff", border: "none", cursor: "pointer" }}
        >
          <RotateCcw className="h-4 w-4" />
          Reiniciar tutorial
        </button>
      </div>
    </div>
  );
}
