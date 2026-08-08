"use client";

import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TerceroOut, TercerosCatalogos, TercerosStats } from "@/lib/types";
import {
  Users,
  Search,
  Building2,
  User,
  CheckCircle2,
  AlertCircle,
  X,
  ChevronDown,
  Edit3,
  Save,
  RefreshCw,
  Download,
  Trash2,
} from "lucide-react";
import { createPortal } from "react-dom";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function nitConDv(t: TerceroOut) {
  if (t.digito_verificacion !== null && t.digito_verificacion !== undefined) {
    return `${t.nit}-${t.digito_verificacion}`;
  }
  return t.nit;
}

function nombreDisplay(t: TerceroOut) {
  return t.razon_social || `${t.nombres_tercero ?? ""} ${t.apellidos_tercero ?? ""}`.trim() || t.nit;
}

const FUENTE_LABEL: Record<string, string> = {
  xml: "XML",
  pdf: "PDF",
  manual: "Manual",
};

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div
      className="rounded-xl border p-4"
      style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
    >
      <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
        {value}
      </p>
      {sub && (
        <p className="mt-0.5 text-xs" style={{ color: "var(--text-secondary)" }}>
          {sub}
        </p>
      )}
    </div>
  );
}

// ─── Badge tipo persona ───────────────────────────────────────────────────────

function TipoBadge({ tipo }: { tipo: string | null }) {
  const isJuridica = tipo === "juridica";
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
      style={{
        backgroundColor: isJuridica ? "rgba(99,102,241,0.12)" : "rgba(16,185,129,0.12)",
        color: isJuridica ? "rgb(99,102,241)" : "rgb(16,185,129)",
        border: `1px solid ${isJuridica ? "rgba(99,102,241,0.3)" : "rgba(16,185,129,0.3)"}`,
      }}
    >
      {isJuridica ? <Building2 className="h-3 w-3" /> : <User className="h-3 w-3" />}
      {isJuridica ? "Jurídica" : "Natural"}
    </span>
  );
}

// ─── Fila de tabla ────────────────────────────────────────────────────────────

function TerceroRow({
  t,
  tipos,
  checked,
  onCheck,
  onClick,
}: {
  t: TerceroOut;
  tipos: { codigo: number; descripcion: string }[];
  checked: boolean;
  onCheck: (v: boolean) => void;
  onClick: () => void;
}) {
  const tipoDesc = tipos.find((x) => x.codigo === t.tipo_identificacion)?.descripcion ?? "—";
  const completo = t.tipo_identificacion !== null && t.codigo_departamento !== null;

  return (
    <tr
      className="cursor-pointer transition-colors"
      style={{ borderBottom: "1px solid var(--border-soft)" }}
      onClick={onClick}
      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.backgroundColor = "var(--bg-elevated)")}
      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.backgroundColor = "")}
    >
      {/* Checkbox */}
      <td className="px-3 py-3 w-8" onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onCheck(e.target.checked)}
          className="h-4 w-4 cursor-pointer rounded"
          style={{ accentColor: "rgb(99,102,241)" }}
        />
      </td>

      {/* NIT + DV */}
      <td className="px-4 py-3">
        <span className="font-mono text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {nitConDv(t)}
        </span>
      </td>

      {/* Razón social */}
      <td className="px-4 py-3 max-w-[220px]">
        <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          {nombreDisplay(t)}
        </p>
        {t.nombre_comercial && t.nombre_comercial !== t.razon_social && (
          <p className="truncate text-xs" style={{ color: "var(--text-secondary)" }}>
            {t.nombre_comercial}
          </p>
        )}
      </td>

      {/* Tipo identificación */}
      <td className="px-4 py-3 hidden md:table-cell">
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {t.tipo_identificacion ? `${t.tipo_identificacion} – ${tipoDesc.split(" ").slice(0, 3).join(" ")}` : "—"}
        </span>
      </td>

      {/* Tipo persona */}
      <td className="px-4 py-3">
        <TipoBadge tipo={t.tipo_persona} />
      </td>

      {/* Ciudad */}
      <td className="px-4 py-3 hidden lg:table-cell">
        <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {t.ciudad || "—"}
        </span>
      </td>

      {/* Completo */}
      <td className="px-4 py-3 text-center">
        {completo ? (
          <CheckCircle2 className="h-4 w-4 mx-auto" style={{ color: "var(--success)" }} />
        ) : (
          <AlertCircle className="h-4 w-4 mx-auto" style={{ color: "var(--text-muted)" }} />
        )}
      </td>

      {/* Fuente */}
      <td className="px-4 py-3 hidden xl:table-cell">
        <span
          className="inline-flex items-center rounded-full px-2 py-0.5 text-xs"
          style={{
            backgroundColor: "var(--bg-elevated)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-soft)",
          }}
        >
          {FUENTE_LABEL[t.fuente ?? ""] ?? "—"}
        </span>
      </td>
    </tr>
  );
}

// ─── Modal de detalle / edición ───────────────────────────────────────────────

function TerceroModal({
  tercero,
  catalogos,
  onClose,
  onSaved,
  onExport,
  onDeleted,
}: {
  tercero: TerceroOut;
  catalogos: TercerosCatalogos | undefined;
  onClose: () => void;
  onSaved: (t: TerceroOut) => void;
  onExport: (id: number) => void;
  onDeleted: (id: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [form, setForm] = useState<Partial<TerceroOut>>({});

  const merged = { ...tercero, ...form };

  function field(key: keyof TerceroOut) {
    return {
      value: (form[key] ?? tercero[key] ?? "") as string,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
        setForm((prev) => ({ ...prev, [key]: e.target.value || null })),
    };
  }

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await api.actualizarTercero(tercero.id, form);
      onSaved(updated);
      setEditing(false);
      setForm({});
    } catch (err) {
      alert(String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.eliminarTercero(tercero.id);
      onDeleted(tercero.id);
      onClose();
    } catch (err) {
      alert(String(err));
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  const tipos = catalogos?.tipos_identificacion ?? [];
  const regimenesIva = catalogos?.regimenes_iva ?? [];
  const responsabilidades = catalogos?.responsabilidades_fiscales ?? [];

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="relative flex w-full max-w-3xl flex-col rounded-2xl border shadow-2xl"
        style={{ maxHeight: "90vh", borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-6 py-4 shrink-0"
          style={{ borderColor: "var(--border-soft)" }}
        >
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              {nombreDisplay(tercero)}
            </h2>
            <p className="mt-0.5 text-xs font-mono" style={{ color: "var(--text-secondary)" }}>
              NIT {nitConDv(tercero)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {editing ? (
              <>
                <button
                  onClick={() => { setEditing(false); setForm({}); }}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium transition-opacity hover:opacity-70"
                  style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-opacity hover:opacity-80 disabled:opacity-50"
                  style={{ backgroundColor: "rgb(99,102,241)", color: "white" }}
                >
                  <Save className="h-3.5 w-3.5" />
                  {saving ? "Guardando…" : "Guardar"}
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => onExport(tercero.id)}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-opacity hover:opacity-70"
                  style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
                >
                  <Download className="h-3.5 w-3.5" />
                  Exportar
                </button>
                <button
                  onClick={() => setEditing(true)}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-opacity hover:opacity-70"
                  style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
                >
                  <Edit3 className="h-3.5 w-3.5" />
                  Editar
                </button>
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-opacity hover:opacity-70"
                  style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "rgb(239,68,68)" }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Eliminar
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-lg transition-opacity hover:opacity-70"
              style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-6">
          {/* Sección: Identificación */}
          <Section title="Identificación">
            <Row label="NIT" value={nitConDv(tercero)} />
            <EditRow
              label="Tipo de identificación"
              editing={editing}
              display={tipos.find((t) => t.codigo === merged.tipo_identificacion)?.descripcion ?? "—"}
            >
              <select
                className="w-full rounded-lg border px-3 py-1.5 text-sm"
                style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)" }}
                value={String(form.tipo_identificacion ?? tercero.tipo_identificacion ?? "")}
                onChange={(e) => setForm((p) => ({ ...p, tipo_identificacion: e.target.value ? Number(e.target.value) : null }))}
              >
                <option value="">— Selecciona —</option>
                {tipos.map((t) => (
                  <option key={t.codigo} value={t.codigo}>
                    {t.codigo} – {t.descripcion}
                  </option>
                ))}
              </select>
            </EditRow>
            <Row label="Tipo persona" value={<TipoBadge tipo={merged.tipo_persona} />} />
            <EditRow label="Razón social" editing={editing} display={merged.razon_social ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("razon_social")} />
            </EditRow>
            <EditRow label="Nombres (natural)" editing={editing} display={merged.nombres_tercero ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("nombres_tercero")} />
            </EditRow>
            <EditRow label="Apellidos (natural)" editing={editing} display={merged.apellidos_tercero ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("apellidos_tercero")} />
            </EditRow>
            <EditRow label="Nombre comercial" editing={editing} display={merged.nombre_comercial ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("nombre_comercial")} />
            </EditRow>
          </Section>

          {/* Sección: Ubicación */}
          <Section title="Ubicación (Siigo)">
            <EditRow label="Dirección" editing={editing} display={merged.direccion ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("direccion")} />
            </EditRow>
            <Row label="Ciudad" value={merged.ciudad ?? "—"} />
            <Row label="Departamento" value={merged.departamento ?? "—"} />
            <EditRow label="Código país (Siigo)" editing={editing} display={merged.codigo_pais ?? "Col"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("codigo_pais")} placeholder="Col" />
            </EditRow>
            <EditRow label="Cód. departamento (Siigo)" editing={editing} display={merged.codigo_departamento ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("codigo_departamento")} />
            </EditRow>
            <EditRow label="Cód. ciudad (Siigo)" editing={editing} display={merged.codigo_ciudad_siigo ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("codigo_ciudad_siigo")} />
            </EditRow>
            <EditRow label="Código postal" editing={editing} display={merged.codigo_postal ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("codigo_postal")} />
            </EditRow>
          </Section>

          {/* Sección: Contacto */}
          <Section title="Contacto">
            <EditRow label="Teléfono" editing={editing} display={merged.telefono ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("telefono")} />
            </EditRow>
            <EditRow label="Correo electrónico" editing={editing} display={merged.email ?? "—"}>
              <input type="email" className={INPUT_CLS} style={INPUT_STYLE} {...field("email")} />
            </EditRow>
          </Section>

          {/* Sección: Fiscal */}
          <Section title="Información fiscal (Siigo)">
            <EditRow
              label="Tipo régimen IVA"
              editing={editing}
              display={
                regimenesIva.find((r) => r.codigo === merged.tipo_regimen_iva)?.etiqueta ??
                merged.tipo_regimen_iva ??
                "—"
              }
            >
              <select
                className={INPUT_CLS}
                style={INPUT_STYLE}
                value={form.tipo_regimen_iva ?? tercero.tipo_regimen_iva ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, tipo_regimen_iva: e.target.value || null }))}
              >
                <option value="">— Selecciona —</option>
                {regimenesIva.map((r) => (
                  <option key={r.codigo} value={r.codigo}>
                    {r.etiqueta}
                  </option>
                ))}
              </select>
            </EditRow>
            <EditRow
              label="Cód. responsabilidad fiscal"
              editing={editing}
              display={
                responsabilidades.find((r) => r.codigo === merged.codigo_responsabilidad)?.codigo ??
                merged.codigo_responsabilidad ??
                "—"
              }
            >
              <select
                className={INPUT_CLS}
                style={INPUT_STYLE}
                value={form.codigo_responsabilidad ?? tercero.codigo_responsabilidad ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, codigo_responsabilidad: e.target.value || null }))}
              >
                <option value="">— Selecciona —</option>
                {responsabilidades.map((r) => (
                  <option key={r.codigo} value={r.codigo}>
                    {r.codigo} – {r.descripcion}
                  </option>
                ))}
              </select>
            </EditRow>
            <EditRow label="Cuenta por pagar (PUC)" editing={editing} display={merged.cuenta_pagar ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("cuenta_pagar")} />
            </EditRow>
          </Section>

          {/* Sección: Contacto principal Siigo */}
          <Section title="Contacto principal (Siigo)">
            <EditRow label="Nombres contacto" editing={editing} display={merged.nombres_contacto ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("nombres_contacto")} />
            </EditRow>
            <EditRow label="Apellidos contacto" editing={editing} display={merged.apellidos_contacto ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("apellidos_contacto")} />
            </EditRow>
            <EditRow label="Teléfono contacto" editing={editing} display={merged.telefono_contacto ?? "—"}>
              <input type="text" className={INPUT_CLS} style={INPUT_STYLE} {...field("telefono_contacto")} />
            </EditRow>
            <EditRow label="Email contacto" editing={editing} display={merged.email_contacto ?? "—"}>
              <input type="email" className={INPUT_CLS} style={INPUT_STYLE} {...field("email_contacto")} />
            </EditRow>
          </Section>

          {/* Meta */}
          <Section title="Información del registro">
            <Row label="Fuente" value={FUENTE_LABEL[tercero.fuente ?? ""] ?? "—"} />
            <Row label="Creado" value={new Date(tercero.created_at).toLocaleString("es-CO")} />
            <Row label="Actualizado" value={new Date(tercero.updated_at).toLocaleString("es-CO")} />
          </Section>
        </div>
      </div>

      {/* Modal de confirmación de eliminación */}
      {confirmDelete && (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl"
          style={{ backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
        >
          <div
            className="mx-4 w-full max-w-sm rounded-2xl border p-6 shadow-2xl"
            style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full" style={{ backgroundColor: "rgba(239,68,68,0.12)" }}>
              <Trash2 className="h-6 w-6" style={{ color: "rgb(239,68,68)" }} />
            </div>
            <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              ¿Eliminar este tercero?
            </h3>
            <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              <span className="font-medium" style={{ color: "var(--text-primary)" }}>{nombreDisplay(tercero)}</span> será removido del módulo. Esta acción no se puede deshacer desde la plataforma.
            </p>
            <div className="mt-5 flex gap-3">
              <button
                onClick={() => setConfirmDelete(false)}
                className="flex-1 rounded-xl border py-2 text-sm font-medium transition-opacity hover:opacity-70"
                style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)" }}
              >
                Cancelar
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 rounded-xl py-2 text-sm font-semibold transition-opacity hover:opacity-80 disabled:opacity-50"
                style={{ backgroundColor: "rgb(239,68,68)", color: "white" }}
              >
                {deleting ? "Eliminando…" : "Sí, eliminar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return createPortal(modal, document.body);
}

// ─── Helpers de layout del modal ─────────────────────────────────────────────

const INPUT_CLS = "w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none";
const INPUT_STYLE = {
  borderColor: "var(--border-soft)",
  backgroundColor: "var(--bg-surface)",
  color: "var(--text-primary)",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p
        className="mb-3 text-xs font-semibold uppercase tracking-widest"
        style={{ color: "var(--text-muted)" }}
      >
        {title}
      </p>
      <div
        className="rounded-xl border divide-y"
        style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
      >
        {children}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5">
      <span className="text-xs shrink-0 w-44" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>
      <span className="text-sm text-right" style={{ color: "var(--text-primary)" }}>
        {value}
      </span>
    </div>
  );
}

function EditRow({
  label,
  editing,
  display,
  children,
}: {
  label: string;
  editing: boolean;
  display: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-4 px-4 py-2.5">
      <span className="text-xs shrink-0 w-44" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>
      {editing ? (
        <div className="flex-1">{children}</div>
      ) : (
        <span className="text-sm flex-1 text-right" style={{ color: "var(--text-primary)" }}>
          {display}
        </span>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function TercerosPage() {
  const [search, setSearch] = useState("");
  const [filterTipo, setFilterTipo] = useState<"" | "juridica" | "natural">("");
  const [selected, setSelected] = useState<TerceroOut | null>(null);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const queryClient = useQueryClient();

  const { data: terceros = [], isLoading, refetch } = useQuery({
    queryKey: ["terceros", filterTipo],
    queryFn: () => api.getTerceros({ tipo_persona: filterTipo || undefined }),
    staleTime: 30_000,
  });

  const { data: catalogos } = useQuery({
    queryKey: ["terceros-catalogos"],
    queryFn: () => api.getTercerosCatalogos(),
    staleTime: 60_000 * 5,
  });

  const { data: stats } = useQuery({
    queryKey: ["terceros-stats"],
    queryFn: () => api.getTercerosStats(),
    staleTime: 30_000,
  });

  const filtered = useMemo(() => {
    if (!search) return terceros;
    const q = search.toLowerCase();
    return terceros.filter(
      (t) =>
        t.nit.includes(q) ||
        (t.razon_social ?? "").toLowerCase().includes(q) ||
        (t.nombre_comercial ?? "").toLowerCase().includes(q)
    );
  }, [terceros, search]);

  const allFilteredChecked = filtered.length > 0 && filtered.every((t) => checkedIds.has(t.id));

  function toggleAll() {
    if (allFilteredChecked) {
      setCheckedIds(new Set());
    } else {
      setCheckedIds(new Set(filtered.map((t) => t.id)));
    }
  }

  function toggleOne(id: number, checked: boolean) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id); else next.delete(id);
      return next;
    });
  }

  async function handleExport(ids?: number[]) {
    setExporting(true);
    try {
      const blob = await api.exportarTerceros(ids);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "terceros_siigo.xlsx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(String(err));
    } finally {
      setExporting(false);
    }
  }

  function handleSaved(updated: TerceroOut) {
    queryClient.setQueryData<TerceroOut[]>(["terceros", filterTipo], (old) =>
      old ? old.map((t) => (t.id === updated.id ? updated : t)) : old
    );
    setSelected(updated);
  }

  function handleDeleted(id: number) {
    queryClient.setQueryData<TerceroOut[]>(["terceros", filterTipo], (old) =>
      old ? old.filter((t) => t.id !== id) : old
    );
    queryClient.invalidateQueries({ queryKey: ["terceros-stats"] });
    setCheckedIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
  }

  async function handleBulkDelete() {
    setBulkDeleting(true);
    try {
      await Promise.all([...checkedIds].map((id) => api.eliminarTercero(id)));
      const deleted = new Set(checkedIds);
      queryClient.setQueryData<TerceroOut[]>(["terceros", filterTipo], (old) =>
        old ? old.filter((t) => !deleted.has(t.id)) : old
      );
      queryClient.invalidateQueries({ queryKey: ["terceros-stats"] });
      setCheckedIds(new Set());
      setConfirmBulkDelete(false);
    } catch (err) {
      alert(String(err));
    } finally {
      setBulkDeleting(false);
    }
  }

  return (
    <div className="flex flex-col h-full" style={{ color: "var(--text-primary)" }}>
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-6 py-4 shrink-0"
        style={{ borderColor: "var(--border-soft)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl"
            style={{ backgroundColor: "rgba(99,102,241,0.12)", color: "rgb(99,102,241)" }}
          >
            <Users className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
              Terceros
            </h1>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Proveedores registrados a partir de facturas causadas
            </p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="flex h-8 w-8 items-center justify-center rounded-lg transition-opacity hover:opacity-70"
          style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text-secondary)" }}
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Total" value={stats.total} />
            <StatCard label="Jurídicas" value={stats.juridicas} />
            <StatCard label="Naturales" value={stats.naturales} />
            <StatCard
              label="Completos"
              value={`${stats.pct_completos}%`}
              sub={`${stats.completos} de ${stats.total}`}
            />
          </div>
        )}

        {/* Filtros + exportar */}
        <div className="flex flex-wrap gap-3 items-center">
          {/* Buscador */}
          <div
            className="flex flex-1 min-w-[200px] items-center gap-2 rounded-xl border px-3 py-2"
            style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
          >
            <Search className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
            <input
              type="text"
              placeholder="Buscar por NIT o razón social…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 bg-transparent text-sm focus:outline-none"
              style={{ color: "var(--text-primary)" }}
            />
            {search && (
              <button onClick={() => setSearch("")}>
                <X className="h-3.5 w-3.5" style={{ color: "var(--text-muted)" }} />
              </button>
            )}
          </div>

          {/* Filtro tipo */}
          <div className="relative">
            <select
              value={filterTipo}
              onChange={(e) => setFilterTipo(e.target.value as "" | "juridica" | "natural")}
              className="appearance-none rounded-xl border pl-3 pr-8 py-2 text-sm focus:outline-none"
              style={{
                borderColor: "var(--border-soft)",
                backgroundColor: "var(--bg-surface)",
                color: "var(--text-primary)",
              }}
            >
              <option value="">Todos los tipos</option>
              <option value="juridica">Jurídica</option>
              <option value="natural">Natural</option>
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4"
              style={{ color: "var(--text-muted)" }}
            />
          </div>

          {/* Acciones sobre seleccionados */}
          {checkedIds.size > 0 && (
            <>
              <button
                onClick={() => handleExport([...checkedIds])}
                disabled={exporting}
                className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-opacity hover:opacity-80 disabled:opacity-50"
                style={{ backgroundColor: "rgb(99,102,241)", color: "white" }}
              >
                <Download className="h-4 w-4" />
                Exportar {checkedIds.size} seleccionado{checkedIds.size !== 1 ? "s" : ""}
              </button>
              <button
                onClick={() => setConfirmBulkDelete(true)}
                className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-opacity hover:opacity-80"
                style={{ backgroundColor: "rgba(239,68,68,0.12)", color: "rgb(239,68,68)" }}
              >
                <Trash2 className="h-4 w-4" />
                Eliminar {checkedIds.size} seleccionado{checkedIds.size !== 1 ? "s" : ""}
              </button>
            </>
          )}

          {/* Exportar todo */}
          <button
            onClick={() => handleExport()}
            disabled={exporting || terceros.length === 0}
            className="flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-opacity hover:opacity-70 disabled:opacity-40"
            style={{
              borderColor: "var(--border-soft)",
              backgroundColor: "var(--bg-surface)",
              color: "var(--text-secondary)",
            }}
          >
            <Download className="h-4 w-4" />
            {exporting ? "Exportando…" : "Exportar todo"}
          </button>
        </div>

        {/* Tabla */}
        <div
          className="overflow-hidden rounded-xl border"
          style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid var(--border-soft)",
                    backgroundColor: "var(--bg-elevated)",
                  }}
                >
                  {/* Checkbox select all */}
                  <th className="px-3 py-3 w-8">
                    <input
                      type="checkbox"
                      checked={allFilteredChecked}
                      onChange={toggleAll}
                      disabled={filtered.length === 0}
                      className="h-4 w-4 cursor-pointer rounded"
                      style={{ accentColor: "rgb(99,102,241)" }}
                    />
                  </th>
                  {[
                    "NIT – DV",
                    "Razón social",
                    "Tipo ID",
                    "Tipo",
                    "Ciudad",
                    "Completo",
                    "Fuente",
                  ].map((h, i) => (
                    <th
                      key={h}
                      className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide${
                        i === 2 ? " hidden md:table-cell" : i === 4 ? " hidden lg:table-cell" : i === 6 ? " hidden xl:table-cell" : ""
                      }`}
                      style={{ color: "var(--text-muted)" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
                      Cargando…
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center" style={{ color: "var(--text-muted)" }}>
                      <Users className="h-8 w-8 mx-auto mb-2 opacity-40" />
                      <p className="text-sm">
                        {search || filterTipo
                          ? "Sin resultados para los filtros aplicados"
                          : "Aún no hay terceros registrados. Se crean automáticamente al guardar aprendizaje en Causación."}
                      </p>
                    </td>
                  </tr>
                ) : (
                  filtered.map((t) => (
                    <TerceroRow
                      key={t.id}
                      t={t}
                      tipos={catalogos?.tipos_identificacion ?? []}
                      checked={checkedIds.has(t.id)}
                      onCheck={(v) => toggleOne(t.id, v)}
                      onClick={() => setSelected(t)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {filtered.length > 0 && (
          <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
            {filtered.length} tercero{filtered.length !== 1 ? "s" : ""}
            {search || filterTipo ? " (filtrados)" : ""}
            {checkedIds.size > 0 && ` · ${checkedIds.size} seleccionado${checkedIds.size !== 1 ? "s" : ""}`}
          </p>
        )}
      </div>

      {/* Modal confirmación eliminación masiva */}
      {confirmBulkDelete && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
        >
          <div
            className="w-full max-w-sm rounded-2xl border p-6 shadow-2xl"
            style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full" style={{ backgroundColor: "rgba(239,68,68,0.12)" }}>
              <Trash2 className="h-6 w-6" style={{ color: "rgb(239,68,68)" }} />
            </div>
            <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              ¿Eliminar {checkedIds.size} tercero{checkedIds.size !== 1 ? "s" : ""}?
            </h3>
            <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              Los {checkedIds.size} terceros seleccionados serán removidos del módulo. Esta acción no se puede deshacer desde la plataforma.
            </p>
            <div className="mt-5 flex gap-3">
              <button
                onClick={() => setConfirmBulkDelete(false)}
                disabled={bulkDeleting}
                className="flex-1 rounded-xl border py-2 text-sm font-medium transition-opacity hover:opacity-70 disabled:opacity-40"
                style={{ borderColor: "var(--border-soft)", color: "var(--text-secondary)" }}
              >
                Cancelar
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={bulkDeleting}
                className="flex-1 rounded-xl py-2 text-sm font-semibold transition-opacity hover:opacity-80 disabled:opacity-50"
                style={{ backgroundColor: "rgb(239,68,68)", color: "white" }}
              >
                {bulkDeleting ? "Eliminando…" : `Sí, eliminar ${checkedIds.size}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal detalle */}
      {selected && (
        <TerceroModal
          tercero={selected}
          catalogos={catalogos}
          onClose={() => setSelected(null)}
          onSaved={handleSaved}
          onExport={(id) => handleExport([id])}
          onDeleted={handleDeleted}
        />
      )}
    </div>
  );
}
