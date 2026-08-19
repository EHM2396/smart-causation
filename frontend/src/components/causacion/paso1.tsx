"use client";
import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useWizardStore } from "@/stores/wizard";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Upload, FileSpreadsheet, X, AlertTriangle, CheckCircle2, Loader2, TrendingDown, Clock, History, Trash2, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmt } from "@/lib/utils";
import type { Factura } from "@/lib/types";

function fechaBorrador(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-CO", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function Paso1() {
  const { setFacturas, setFacturasYaCausadas, setPaso, facturas: stored, setPdfUrls, pdfUrls, setFilesProcesando, setSuggestions, setPaso2Cache, setFacturasOmitidas, hydrateBorrador, tutorialActivo } = useWizardStore();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [ventasDetectadas, setVentasDetectadas] = useState<{ filename: string; numero: string }[]>([]);
  const [omitidas, setOmitidas] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

  // ── Borrador guardado (guardado temporal) ────────────────────────────────────
  const queryClient = useQueryClient();
  const [continuandoBorrador, setContinuandoBorrador] = useState(false);
  const [descartandoBorrador, setDescartandoBorrador] = useState(false);
  const { data: borrador } = useQuery({
    queryKey: ["borrador"],
    queryFn: api.getBorrador,
    enabled: !tutorialActivo,
    staleTime: 0,
  });

  const continuarBorrador = async () => {
    setContinuandoBorrador(true);
    try {
      const completo = await api.getBorradorCompleto();
      if (completo?.datos) {
        hydrateBorrador(completo.datos); // setea facturas + config + paso=2
      }
    } catch {
      setErrors(["No se pudo cargar el borrador guardado. Intenta de nuevo."]);
    } finally {
      setContinuandoBorrador(false);
    }
  };

  const descartarBorrador = async () => {
    setDescartandoBorrador(true);
    try {
      await api.descartarBorrador();
      await queryClient.invalidateQueries({ queryKey: ["borrador"] });
    } catch {
      // silencioso: si falla, la tarjeta sigue visible y puede reintentar
    } finally {
      setDescartandoBorrador(false);
    }
  };

  const handleFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const validos = Array.from(incoming).filter(
      (f) => f.name.endsWith(".xlsx") || f.name.endsWith(".zip") || f.name.endsWith(".pdf") || f.name.endsWith(".xml")
    );
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...validos.filter((f) => !names.has(f.name))];
    });
  };

  const clearMessages = () => { setErrors([]); setOmitidas([]); setVentasDetectadas([]); };

  const removeFile = (name: string) => {
    setFiles((prev) => {
      const next = prev.filter((f) => f.name !== name);
      if (next.length === 0) clearMessages();
      return next;
    });
  };

  const handleParse = async () => {
    if (!files.length) return;
    setLoading(true);
    setErrors([]);
    setVentasDetectadas([]);
    setOmitidas([]);

    // Limpiar estado anterior para que paso2 no vea datos obsoletos de la sesión previa
    setFacturas([]);
    setSuggestions({});
    setPaso2Cache(null);
    // NO avanzar a paso2 todavía — el componente debe permanecer montado para que
    // los setters de estado local (ventasDetectadas, errors, omitidas) sean visibles

    const parsed: Factura[] = [];
    const errs: string[] = [];
    const ventas: { filename: string; numero: string }[] = [];

    const newPdfUrls: Record<string, string> = { ...pdfUrls };
    for (const file of files) {
      if (file.name.endsWith(".pdf") && !newPdfUrls[file.name]) {
        newPdfUrls[file.name] = URL.createObjectURL(file);
      }
      try {
        const result: Factura[] = await api.parsearFacturas(file);
        for (const f of result) {
          parsed.push({ ...f, _archivo: file.name });
          for (const adv of f.advertencias ?? []) errs.push(`${file.name}: ${adv}`);
        }
      } catch (e) {
        const msg = (e as Error).message;
        if (msg.includes("[VENTA]")) {
          const match = msg.match(/\[VENTA\]\s*([^:]+):/);
          ventas.push({ filename: file.name, numero: match?.[1]?.trim() ?? file.name });
        } else {
          errs.push(`${file.name}: ${msg}`);
        }
      }
    }

    setPdfUrls(newPdfUrls);

    if (!parsed.length) {
      // Sin facturas de compra parseadas — mostrar aviso y quedarse en paso1
      setVentasDetectadas(ventas);
      if (!ventas.length) errs.push("No se procesó ninguna factura válida.");
      setErrors(errs);
      setLoading(false);
      return;
    }

    // Verificar cuáles ya fueron causadas para esta empresa
    let causadasInfo: import("@/lib/types").FacturaCausadaInfo[] = [];
    try {
      const numeros = parsed.map((f) => f.numero_dian).filter(Boolean);
      const { ya_causadas } = await api.verificarCausadas(numeros);
      causadasInfo = ya_causadas;
    } catch {
      // Si falla la verificación, continuar sin filtrar
    }

    const causadasNums = new Set(causadasInfo.map((c) => c.numero_dian));
    const nuevas = parsed.filter((f) => !causadasNums.has(f.numero_dian));

    const hayComprasValidas = nuevas.length > 0;

    if (!hayComprasValidas) {
      // Todas las facturas son ventas o ya causadas — quedarse en paso1 con aviso
      // (el componente sigue montado, el estado local es visible)
      setVentasDetectadas(ventas);
      setErrors(errs);
      setOmitidas(causadasInfo.map((c) => c.numero_dian));
      setFacturasYaCausadas(causadasInfo);
      setFacturasOmitidas([]);
      setLoading(false);
      return;
    }

    // Hay compras válidas → construir omisiones y avanzar a paso2
    const omisionesParaPaso2: import("@/lib/types").FacturaOmitida[] = [
      ...ventas.map((v) => ({ filename: v.filename, numero: v.numero, motivo: "venta" as const })),
      ...causadasInfo.map((c) => ({
        filename: parsed.find((f) => f.numero_dian === c.numero_dian)?._archivo ?? "",
        numero: c.numero_dian,
        motivo: "ya_causada" as const,
      })),
    ];

    setFacturasOmitidas(omisionesParaPaso2);
    setVentasDetectadas(ventas);
    setErrors(errs);
    setOmitidas(causadasInfo.map((c) => c.numero_dian));
    setFacturasYaCausadas(causadasInfo);
    setFacturas(nuevas);
    setLoading(false);
    // Avanzar a paso2 — filesProcesando activa el overlay mientras cargan las sugerencias IA
    setFilesProcesando(true);
    setPaso(2);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">Cargar facturas DIAN</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Sube archivos <code className="text-[var(--brand)] font-medium">.xlsx</code> del portal DIAN, archivos <code className="text-[var(--brand)] font-medium">.zip</code>, <code className="text-[var(--brand)] font-medium">.xml</code> o <code className="text-[var(--brand)] font-medium">.pdf</code> de factura electrónica DIAN. Puedes subir varios a la vez.
        </p>
      </div>

      {/* Borrador guardado — ofrecer continuar donde quedó */}
      {borrador && borrador.total_facturas > 0 && files.length === 0 && stored.length === 0 && (
        <div
          className="flex flex-col gap-3 rounded-xl border p-5 sm:flex-row sm:items-center sm:justify-between"
          style={{ borderColor: "var(--brand)", backgroundColor: "var(--brand-muted)" }}
        >
          <div className="flex min-w-0 items-start gap-3">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
              style={{ backgroundColor: "color-mix(in srgb, var(--brand) 15%, transparent)" }}
            >
              <History className="h-5 w-5" style={{ color: "var(--brand)" }} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Tienes un borrador guardado
              </p>
              <p className="mt-0.5 text-xs" style={{ color: "var(--text-secondary)" }}>
                {borrador.total_facturas} factura{borrador.total_facturas !== 1 ? "s" : ""} · {borrador.total_verificadas} verificada{borrador.total_verificadas !== 1 ? "s" : ""}
                {borrador.actualizado_at ? ` · actualizado ${fechaBorrador(borrador.actualizado_at)}` : ""}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={descartarBorrador}
              disabled={descartandoBorrador || continuandoBorrador}
              className="gap-1.5"
            >
              {descartandoBorrador ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              Descartar
            </Button>
            <Button
              size="sm"
              onClick={continuarBorrador}
              disabled={continuandoBorrador || descartandoBorrador}
              className="gap-1.5"
            >
              {continuandoBorrador ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
              Continuar
            </Button>
          </div>
        </div>
      )}

      {/* Drop zone — compacto si ya hay archivos */}
      <label
        data-tutorial="dropzone"
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        className="block cursor-pointer transition-all duration-200"
        style={{
          borderRadius: "var(--radius-lg)",
          border: `2px dashed ${dragging ? "var(--brand)" : "var(--border-strong)"}`,
          backgroundColor: dragging ? "var(--brand-muted)" : "var(--bg-surface)",
          boxShadow: dragging ? "var(--shadow-ring)" : "none",
          padding: files.length > 0 ? "0.75rem 1.25rem" : "3rem 1.5rem",
        }}
      >
        <input type="file" multiple accept=".xlsx,.zip,.pdf,.xml" className="sr-only" onChange={(e) => handleFiles(e.target.files)} />

        {/* Modo compacto: ya hay archivos cargados */}
        {files.length > 0 ? (
          <div className="flex items-center gap-3">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              style={{
                background: dragging ? "linear-gradient(135deg, #2563eb, #1d4ed8)" : "linear-gradient(135deg, #eff6ff, #dbeafe)",
              }}
            >
              <Upload className="h-4 w-4" style={{ color: dragging ? "#ffffff" : "var(--brand)" }} />
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
              {dragging ? "Suelta para agregar más" : "Agregar más archivos"}
            </p>
          </div>
        ) : (
          /* Modo completo: sin archivos */
          <div className="flex flex-col items-center gap-4 text-center">
            <div
              className="flex h-16 w-16 items-center justify-center rounded-2xl"
              style={{
                background: dragging
                  ? "linear-gradient(135deg, #2563eb, #1d4ed8)"
                  : "linear-gradient(135deg, #eff6ff, #dbeafe)",
                boxShadow: dragging ? "0 8px 20px rgb(37 99 235 / 0.3)" : "var(--shadow-sm)",
              }}
            >
              <Upload className="h-7 w-7 transition-colors" style={{ color: dragging ? "#ffffff" : "var(--brand)" }} />
            </div>
            <div>
              <p className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                {dragging ? "Suelta los archivos aquí" : "Arrastra aquí o haz clic para seleccionar"}
              </p>
              <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
                Archivos <span className="font-medium" style={{ color: "var(--brand)" }}>.xlsx</span> del portal DIAN, <span className="font-medium" style={{ color: "var(--brand)" }}>.zip</span>, <span className="font-medium" style={{ color: "var(--brand)" }}>.xml</span> o <span className="font-medium" style={{ color: "var(--brand)" }}>.pdf</span> de factura electrónica · múltiples permitidos
              </p>
            </div>
            {!dragging && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
                style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-muted)", border: "1px solid var(--border-soft)" }}
              >
                <FileSpreadsheet className="h-3.5 w-3.5" />
                Excel (.xlsx) · ZIP DIAN (.zip) · XML DIAN (.xml) · PDF DIAN (.pdf)
              </span>
            )}
          </div>
        )}
      </label>

      {/* Loading overlay */}
      {loading ? (
        <div
          className="flex flex-col items-center gap-4 py-10 rounded-xl border"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}
        >
          <div
            className="flex h-16 w-16 items-center justify-center rounded-2xl"
            style={{ background: "linear-gradient(135deg, #eff6ff, #dbeafe)", boxShadow: "var(--shadow-sm)" }}
          >
            <Loader2 className="h-8 w-8 animate-spin" style={{ color: "var(--brand)" }} />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Analizando {files.length} archivo{files.length > 1 ? "s" : ""}…
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
              Procesando archivos de facturas
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* File list */}
          {files.length > 0 && (
            <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border-soft)" }}>
              {/* Header */}
              <div
                className="flex items-center justify-between px-4 py-2.5"
                style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border-soft)" }}
              >
                <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
                  {files.length} archivo{files.length !== 1 ? "s" : ""} seleccionado{files.length !== 1 ? "s" : ""}
                </span>
                <button
                  type="button"
                  onClick={() => { setFiles([]); clearMessages(); }}
                  className="flex items-center gap-1 text-xs font-medium transition-opacity hover:opacity-70"
                  style={{ color: "var(--error)" }}
                >
                  <X className="h-3 w-3" /> Quitar todos
                </button>
              </div>
              {/* Scrollable rows — max 5 visible */}
              <div className="overflow-y-auto" style={{ maxHeight: "220px" }}>
                {files.map((f) => (
                  <div
                    key={f.name}
                    className="flex items-center gap-3 border-b px-4 py-2.5 last:border-b-0"
                    style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
                  >
                    <FileSpreadsheet className="h-4 w-4 shrink-0" style={{ color: "#34d399" }} />
                    <span className="flex-1 truncate text-sm" style={{ color: "var(--text-secondary)" }}>{f.name}</span>
                    <span className="shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>{(f.size / 1024).toFixed(0)} KB</span>
                    <button
                      type="button"
                      onClick={() => removeFile(f.name)}
                      className="shrink-0 transition-colors"
                      style={{ color: "var(--text-muted)" }}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Facturas de VENTA detectadas — Próximamente */}
          {ventasDetectadas.length > 0 && (
            <div
              className="rounded-xl border p-4 space-y-3"
              style={{ borderColor: "color-mix(in srgb, var(--brand-btn) 40%, transparent)", backgroundColor: "color-mix(in srgb, var(--brand-btn) 7%, transparent)" }}
            >
              <div className="flex items-start gap-3">
                <div
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: "linear-gradient(135deg, var(--brand-btn) 0%, var(--brand-accent) 100%)" }}
                >
                  <TrendingDown className="h-4 w-4 text-white" />
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold" style={{ color: "var(--brand-btn)" }}>
                      {ventasDetectadas.length === 1
                        ? "1 factura de venta excluida"
                        : `${ventasDetectadas.length} facturas de venta excluidas`}
                    </p>
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                      style={{ backgroundColor: "color-mix(in srgb, var(--brand-btn) 15%, transparent)", color: "var(--brand-btn)", border: "1px solid color-mix(in srgb, var(--brand-btn) 35%, transparent)" }}
                    >
                      <Clock className="h-3 w-3" /> Próximamente
                    </span>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    {ventasDetectadas.length === 1
                      ? "Esta factura corresponde a una venta de tu empresa y no puede causarse en este módulo."
                      : "Estas facturas corresponden a ventas de tu empresa y no pueden causarse en este módulo."}
                    {" "}El módulo de causación de ventas estará disponible próximamente.
                  </p>
                </div>
              </div>
              {/* Chips con los números excluidos */}
              <div className="flex flex-wrap gap-1.5 pl-12">
                {ventasDetectadas.map((v, i) => (
                  <span
                    key={i}
                    className="rounded-full px-2.5 py-0.5 font-mono text-xs font-medium"
                    style={{ backgroundColor: "color-mix(in srgb, var(--brand-btn) 12%, transparent)", color: "var(--brand-btn)", border: "1px solid color-mix(in srgb, var(--brand-btn) 25%, transparent)" }}
                    title={v.filename}
                  >
                    {v.numero}
                  </span>
                ))}
              </div>
              {/* Botón continuar si hay facturas de compra válidas */}
              {stored.length > 0 && (
                <div className="pl-12">
                  <Button size="sm" onClick={() => setPaso(2)}>
                    Continuar con {stored.length} factura{stored.length !== 1 ? "s" : ""} de compra →
                  </Button>
                </div>
              )}
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

          {/* Facturas ya causadas — aviso + confirmación */}
          {omitidas.length > 0 && (
            <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: "var(--warning-border)", backgroundColor: "var(--warning-bg)" }}>
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--warning-text)" }} />
                <div className="space-y-1">
                  <p className="text-sm font-semibold" style={{ color: "var(--warning-text)" }}>
                    {omitidas.length} factura{omitidas.length > 1 ? "s" : ""} ya {omitidas.length > 1 ? "fueron causadas" : "fue causada"} anteriormente
                  </p>
                  <p className="text-xs" style={{ color: "var(--warning-text)", opacity: 0.8 }}>
                    Se omitirán automáticamente. Puedes continuar con las restantes.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 pl-8">
                {omitidas.map((n) => (
                  <span
                    key={n}
                    className="rounded-full px-2.5 py-0.5 font-mono text-xs font-medium"
                    style={{ backgroundColor: "var(--warning-border)", color: "var(--warning-text)" }}
                  >
                    {n}
                  </span>
                ))}
              </div>
              {stored.length > 0 && (
                <div className="pl-8">
                  <Button size="sm" onClick={() => setPaso(2)}>
                    Continuar con las {stored.length} facturas restantes →
                  </Button>
                </div>
              )}
            </div>
          )}

          {omitidas.length === 0 && !(ventasDetectadas.length > 0 && stored.length > 0) && (
            <Button data-tutorial="parse-btn" onClick={handleParse} disabled={!files.length} size="lg" className="w-full sm:w-auto">
              {files.length
                ? `Procesar ${files.length} archivo${files.length > 1 ? "s" : ""}`
                : "Procesar archivos"}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
