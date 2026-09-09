"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { useWizardStore } from "@/stores/wizard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Building2, ChevronDown, Check, Plus, Loader2, AlertTriangle } from "lucide-react";

function errDetalle(e: unknown): string {
  const raw = (e as Error).message ?? "";
  const j = raw.replace(/^API\s+\d+:\s*/, "");
  try { const p = JSON.parse(j); if (typeof p?.detail === "string") return p.detail; } catch {}
  return j || "No se pudo crear la empresa";
}

/** Aplica el cambio de empresa: fija la empresa, limpia el wizard y recarga los datos. */
function useCambiarEmpresa() {
  const qc = useQueryClient();
  const setEmpresa = useAuthStore((s) => s.setEmpresa);
  const empresaId = useAuthStore((s) => s.empresaId);
  const resetWizard = useWizardStore((s) => s.reset);
  return (id: number, nombre: string) => {
    const cambia = id !== empresaId;
    setEmpresa(id, nombre);
    if (cambia) {
      resetWizard();
      qc.invalidateQueries();      // recargar todo para la nueva empresa
    }
  };
}

/** Selector de empresa (solo para causadores). Permite cambiar y crear empresas. */
export function EmpresaSwitcher({ onNavigate }: { onNavigate?: () => void }) {
  const token = useAuthStore((s) => s.token);
  const empresaId = useAuthStore((s) => s.empresaId);
  const empresaNombre = useAuthStore((s) => s.empresaNombre);
  const empresaConfirmada = useAuthStore((s) => s.empresaConfirmada);
  const cambiar = useCambiarEmpresa();
  const [open, setOpen] = useState(false);
  const [crearOpen, setCrearOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data: empresas = [] } = useQuery({ queryKey: ["mis-empresas"], queryFn: api.misEmpresas, enabled: !!token });

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  // Mientras el causador no confirme una empresa, el selector se muestra VACÍO
  // (aunque el login haya traído una empresa por defecto).
  const nombreActual = empresaConfirmada
    ? (empresaNombre ?? empresas.find((e) => e.id === empresaId)?.nombre ?? "Selecciona empresa")
    : "Selecciona empresa";
  const seleccionActiva = empresaConfirmada ? empresaId : null;
  const elegir = (id: number, nombre: string) => { cambiar(id, nombre); setOpen(false); onNavigate?.(); };

  return (
    <>
      <div ref={ref} className="relative mb-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors"
          style={{ borderColor: "var(--sidebar-border)", backgroundColor: "var(--sidebar-hover-bg)" }}
          title={nombreActual}
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md" style={{ backgroundColor: "var(--sidebar-icon-bg)" }}>
            <Building2 className="h-4 w-4" style={{ color: "var(--sidebar-icon-active-color)" }} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--sidebar-label)" }}>Empresa</p>
            <p className="truncate text-sm font-semibold" style={{ color: "var(--sidebar-text-active)" }}>{nombreActual}</p>
          </div>
          <ChevronDown className="h-4 w-4 shrink-0" style={{ color: "var(--sidebar-label)" }} />
        </button>

        {open && (
          <div
            className="absolute left-0 right-0 z-50 mt-1 max-h-72 overflow-y-auto rounded-lg border py-1"
            style={{ borderColor: "var(--sidebar-border)", backgroundColor: "var(--sidebar-bg)", boxShadow: "0 10px 30px rgb(0 0 0 / 0.25)" }}
          >
            {empresas.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => elegir(e.id, e.nombre)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm"
                style={{ color: "var(--sidebar-text)" }}
                onMouseEnter={(ev) => (ev.currentTarget.style.backgroundColor = "var(--sidebar-hover-bg)")}
                onMouseLeave={(ev) => (ev.currentTarget.style.backgroundColor = "transparent")}
              >
                <span className="flex-1 truncate">{e.nombre}</span>
                {e.id === seleccionActiva && <Check className="h-4 w-4 shrink-0" style={{ color: "var(--sidebar-icon-active-color)" }} />}
              </button>
            ))}
            <div className="my-1 border-t" style={{ borderColor: "var(--sidebar-border)" }} />
            <button
              type="button"
              onClick={() => { setOpen(false); setCrearOpen(true); }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium"
              style={{ color: "var(--sidebar-icon-active-color)" }}
              onMouseEnter={(ev) => (ev.currentTarget.style.backgroundColor = "var(--sidebar-hover-bg)")}
              onMouseLeave={(ev) => (ev.currentTarget.style.backgroundColor = "transparent")}
            >
              <Plus className="h-4 w-4 shrink-0" /> Nueva empresa
            </button>
          </div>
        )}
      </div>

      {crearOpen && (
        <NuevaEmpresaDialog
          onClose={() => setCrearOpen(false)}
          onCreada={(id, nombre) => { cambiar(id, nombre); setCrearOpen(false); onNavigate?.(); }}
        />
      )}
    </>
  );
}

function NuevaEmpresaDialog({ onClose, onCreada }: { onClose: () => void; onCreada: (id: number, nombre: string) => void }) {
  const qc = useQueryClient();
  const [nombre, setNombre] = useState("");
  const [nit, setNit] = useState("");
  const [err, setErr] = useState("");

  const mut = useMutation({
    mutationFn: () => api.crearEmpresaPropia({ nombre: nombre.trim(), nit: nit.trim() }),
    onSuccess: (emp) => {
      qc.invalidateQueries({ queryKey: ["mis-empresas"] });
      onCreada(emp.id, emp.nombre);
    },
    onError: (e) => setErr(errDetalle(e)),
  });

  const submit = () => {
    setErr("");
    if (nombre.trim().length < 1) return setErr("Escribe el nombre de la empresa.");
    if (nit.trim().length < 1) return setErr("El NIT es obligatorio.");
    mut.mutate();
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Nueva empresa</DialogTitle>
          <DialogDescription>Crea una empresa para trabajar con ella. Luego podrás configurar sus catálogos.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 pt-1">
          <div className="space-y-1"><Label>Nombre</Label><Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Razón social" /></div>
          <div className="space-y-1"><Label>NIT</Label><Input value={nit} onChange={(e) => setNit(e.target.value)} placeholder="900123456" /></div>
          {err && (
            <div className="flex items-start gap-1.5 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error-text)" }}>
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {err}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} disabled={mut.isPending}>Cancelar</Button>
            <Button onClick={submit} disabled={mut.isPending} className="gap-1.5">
              {mut.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Crear empresa
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Pantalla que obliga a elegir empresa (causadores con más de una) antes de trabajar. */
export function EmpresaGate() {
  const token = useAuthStore((s) => s.token);
  const cambiar = useCambiarEmpresa();
  const { data: empresas = [] } = useQuery({ queryKey: ["mis-empresas"], queryFn: api.misEmpresas, enabled: !!token });

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border p-6 text-center" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", boxShadow: "var(--shadow-sm)" }}>
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl" style={{ background: "linear-gradient(135deg, var(--brand-btn), var(--brand-accent))" }}>
          <Building2 className="h-7 w-7 text-white" />
        </div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Elige la empresa</h2>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Selecciona la empresa con la que vas a trabajar. Podrás cambiarla cuando quieras desde el menú.
        </p>
        <div className="mt-5 space-y-2">
          {empresas.map((e) => (
            <button
              key={e.id}
              type="button"
              onClick={() => cambiar(e.id, e.nombre)}
              className="flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-colors hover:opacity-90"
              style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: "var(--info-bg)", color: "var(--info-text)" }}>
                <Building2 className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{e.nombre}</p>
                {e.nit && <p className="truncate font-mono text-xs" style={{ color: "var(--text-muted)" }}>{e.nit}</p>}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
