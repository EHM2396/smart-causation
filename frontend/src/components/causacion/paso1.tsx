"use client";
import { useState, useCallback } from "react";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Upload, FileSpreadsheet, X, AlertTriangle, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmt } from "@/lib/utils";
import type { Factura } from "@/lib/types";

export function Paso1() {
  const { setFacturas, setPaso, facturas: stored } = useWizardStore();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const xlsx = Array.from(incoming).filter((f) => f.name.endsWith(".xlsx"));
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...xlsx.filter((f) => !names.has(f.name))];
    });
  };

  const removeFile = (name: string) => setFiles((prev) => prev.filter((f) => f.name !== name));

  const handleParse = async () => {
    if (!files.length) return;
    setLoading(true);
    setErrors([]);
    const ok: Factura[] = [];
    const errs: string[] = [];

    for (const file of files) {
      try {
        const result: Factura[] = await api.parsearFacturas(file);
        for (const f of result) {
          ok.push({ ...f, _archivo: file.name });
          for (const adv of f.advertencias ?? []) errs.push(`${file.name}: ${adv}`);
        }
      } catch (e) {
        errs.push(`${file.name}: ${(e as Error).message}`);
      }
    }

    setErrors(errs);
    if (ok.length) {
      setFacturas(ok);
      setPaso(2);
    } else {
      setErrors((prev) => [...prev, "No se procesó ninguna factura válida."]);
    }
    setLoading(false);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">Cargar facturas DIAN</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Sube los archivos <code className="text-[var(--brand)] font-medium">.xlsx</code> exportados del portal DIAN. Puedes subir varios a la vez.
        </p>
      </div>

      {/* Drop zone */}
      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        className="block cursor-pointer transition-all duration-200"
        style={{
          borderRadius: "var(--radius-lg)",
          border: `2px dashed ${dragging ? "var(--brand)" : "var(--border-strong)"}`,
          backgroundColor: dragging ? "var(--brand-muted)" : "var(--bg-surface)",
          boxShadow: dragging ? "var(--shadow-ring)" : "none",
          padding: "3rem 1.5rem",
        }}
      >
        <input type="file" multiple accept=".xlsx" className="sr-only" onChange={(e) => handleFiles(e.target.files)} />
        <div className="flex flex-col items-center gap-4 text-center">
          {/* Icon with gradient background */}
          <div
            className="flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{
              background: dragging
                ? "linear-gradient(135deg, #2563eb, #1d4ed8)"
                : "linear-gradient(135deg, #eff6ff, #dbeafe)",
              boxShadow: dragging ? "0 8px 20px rgb(37 99 235 / 0.3)" : "var(--shadow-sm)",
            }}
          >
            <Upload
              className="h-7 w-7 transition-colors"
              style={{ color: dragging ? "#ffffff" : "var(--brand)" }}
            />
          </div>

          {/* Text */}
          <div>
            <p className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              {dragging ? "Suelta los archivos aquí" : "Arrastra aquí o haz clic para seleccionar"}
            </p>
            <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
              Archivos <span className="font-medium" style={{ color: "var(--brand)" }}>.xlsx</span> exportados del portal DIAN · múltiples permitidos
            </p>
          </div>

          {/* Pill badge */}
          {!dragging && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
              style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border-soft)" }}
            >
              <FileSpreadsheet className="h-3.5 w-3.5" />
              Solo archivos Excel (.xlsx)
            </span>
          )}
        </div>
      </label>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f) => (
            <div key={f.name} className="flex items-center gap-3 rounded-lg border border-[var(--border-soft)] bg-[var(--bg-surface)] px-4 py-3">
              <FileSpreadsheet className="h-5 w-5 shrink-0 text-emerald-400" />
              <span className="flex-1 truncate text-sm text-[var(--text-secondary)]">{f.name}</span>
              <span className="text-xs text-[var(--text-muted)]">{(f.size / 1024).toFixed(0)} KB</span>
              <button onClick={() => removeFile(f.name)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Errors */}
      {errors.length > 0 && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 space-y-1">
          {errors.map((e, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-amber-400">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              {e}
            </div>
          ))}
        </div>
      )}

      <Button onClick={handleParse} disabled={!files.length || loading} size="lg" className="w-full sm:w-auto">
        {loading ? "Procesando..." : `Parsear ${files.length ? `${files.length} archivo${files.length > 1 ? "s" : ""}` : "facturas"}`}
      </Button>
    </div>
  );
}
