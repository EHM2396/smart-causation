import type {
  BatchValidacionResponse,
  ConsecutivoOut,
  CuentaOpcion,
  HistorialItem,
  IADecision,
  IARegla,
  ImpuestoOut,
  LoginResponse,
  TipoComprobanteOpcion,
} from "./types";
import { useAuthStore } from "@/stores/auth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const { token, empresaId } = useAuthStore.getState();
  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders["Authorization"] = `Bearer ${token}`;
  }
  if (empresaId != null) {
    authHeaders["X-Empresa-Id"] = String(empresaId);
  }
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeaders, ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

async function reqBlob(path: string, init?: RequestInit): Promise<Blob> {
  const { token, empresaId } = useAuthStore.getState();
  const authHeaders: Record<string, string> = {};
  if (token) {
    authHeaders["Authorization"] = `Bearer ${token}`;
  }
  if (empresaId != null) {
    authHeaders["X-Empresa-Id"] = String(empresaId);
  }
  const res = await fetch(`${BASE}${path}`, {
    headers: { ...authHeaders, ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg);
  }
  return res.blob();
}

// ─── Helpers internos ────────────────────────────────────────────────────────

async function _uploadExcel(path: string, file: File): Promise<{ insertados: number; actualizados: number; omitidos_codigo?: number; omitidos_nivel?: number; omitidos?: number; formato?: string; errores: { fila: number; error: string }[] }> {
  const { token, empresaId } = useAuthStore.getState();
  const form = new FormData();
  form.append("archivo", file);
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (empresaId != null) headers["X-Empresa-Id"] = String(empresaId);
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers, body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ─── Catálogo ─────────────────────────────────────────────────────────────────

export const api = {
  // Auth
  login: (email: string, password: string) =>
    req<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  registro: (body: {
    email: string;
    password: string;
    nombre: string;
    nombre_empresa: string;
    nit_empresa?: string;
  }) => req<LoginResponse>("/auth/registro", { method: "POST", body: JSON.stringify(body) }),
  me: () => req<{ id: number; email: string; nombre: string; rol: string; email_verificado: boolean; empresa_id: number | null; empresa_nombre: string | null; empresa_nit: string | null }>("/auth/me"),

  actualizarPerfil: (body: { nombre: string; nombre_empresa: string; nit_empresa?: string }) =>
    req<{ message: string }>("/auth/perfil", { method: "PUT", body: JSON.stringify(body) }),

  cambiarPassword: (body: { password_actual: string; nueva_password: string }) =>
    req<{ message: string }>("/auth/cambiar-password", { method: "PUT", body: JSON.stringify(body) }),

  // Email flows (no requieren auth)
  forgotPassword: (email: string) =>
    fetch(`${BASE}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).then((r) => r.json() as Promise<{ message: string }>),

  resetPassword: (token: string, nueva_password: string) =>
    fetch(`${BASE}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, nueva_password }),
    }).then(async (r) => {
      if (!r.ok) { const t = await r.text(); throw new Error(t); }
      return r.json() as Promise<{ message: string }>;
    }),

  verifyEmail: (token: string) =>
    fetch(`${BASE}/auth/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    }).then(async (r) => {
      if (!r.ok) { const t = await r.text(); throw new Error(t); }
      return r.json() as Promise<{ message: string }>;
    }),

  resendVerification: (email: string) =>
    fetch(`${BASE}/auth/resend-verification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).then((r) => r.json() as Promise<{ message: string }>),

  // Cuentas
  getCuentasGasto: () => req<CuentaOpcion[]>("/cuentas/gasto"),
  getCuentasPago: () => req<CuentaOpcion[]>("/cuentas/pago"),
  crearCuenta: (body: { codigo: string; nombre: string; fiscal?: boolean }) =>
    req<{ id: number; codigo: string; nombre: string }>("/cuentas/", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Impuestos
  getImpuestos: () => req<ImpuestoOut[]>("/impuestos"),
  crearImpuesto: (body: {
    codigo: string;
    nombre?: string;
    tipo_impuesto?: string;
    tarifa?: number;
    cta_compras?: string;
  }) => req<ImpuestoOut>("/impuestos", { method: "POST", body: JSON.stringify(body) }),

  // Tipos comprobante
  getTiposComprobante: () => req<TipoComprobanteOpcion[]>("/tipos-comprobante/opciones"),
  crearTipoComprobante: (body: { codigo: string; titulo: string }) =>
    req("/tipos-comprobante", { method: "POST", body: JSON.stringify(body) }),

  // Consecutivos
  getConsecutivo: (tipoComp: string) =>
    req<ConsecutivoOut>(`/consecutivos/${tipoComp}`),
  setConsecutivo: (tipoComp: string, nuevoValor: number) =>
    req<ConsecutivoOut>(`/consecutivos/${tipoComp}`, {
      method: "PUT",
      body: JSON.stringify({ nuevo_valor: nuevoValor }),
    }),

  // Parseo de facturas
  parsearFacturas: async (file: File) => {
    const { token, empresaId } = useAuthStore.getState();
    const form = new FormData();
    form.append("archivo", file);
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (empresaId != null) headers["X-Empresa-Id"] = String(empresaId);
    const res = await fetch(`${BASE}/causacion/parsear`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!res.ok) throw new Error(`Parseo fallido ${res.status}`);
    return res.json();
  },

  // Sugerencia de cuenta
  sugerirCuenta: (nit: string | null, descripcion: string) =>
    req<{ cuenta_sugerida: string | null; origen: string | null }>(
      "/causacion/sugerir-cuenta",
      { method: "POST", body: JSON.stringify({ nit, descripcion }) }
    ),

  // Validación batch
  batchValidar: (body: {
    items: { factura: object; mapeos_confirmados: object[] }[];
    tipo_comprobante: string;
    centro_costo: string;
  }) =>
    req<BatchValidacionResponse>("/causacion/batch/validar", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Generar batch (descarga)
  batchGenerar: (body: {
    items: { factura: object; mapeos_confirmados: object[] }[];
    tipo_comprobante: string;
    centro_costo: string;
    confirmar: boolean;
  }): Promise<Blob> =>
    reqBlob("/causacion/batch/generar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // Historial de causaciones
  getHistorial: (params?: { fechaDesde?: string; fechaHasta?: string; buscar?: string }) => {
    const qp = new URLSearchParams();
    if (params?.fechaDesde) qp.set("fecha_desde", params.fechaDesde);
    if (params?.fechaHasta) qp.set("fecha_hasta", params.fechaHasta);
    if (params?.buscar) qp.set("buscar", params.buscar);
    const qs = qp.toString();
    return req<HistorialItem[]>(`/causacion/historial${qs ? `?${qs}` : ""}`);
  },

  regenerarHistorial: (id: number): Promise<Blob> =>
    reqBlob(`/causacion/historial/${id}/regenerar`, { method: "POST" }),

  limpiarHistorial: (params?: { fechaDesde?: string; fechaHasta?: string }) => {
    const qp = new URLSearchParams();
    if (params?.fechaDesde) qp.set("fecha_desde", params.fechaDesde);
    if (params?.fechaHasta) qp.set("fecha_hasta", params.fechaHasta);
    const qs = qp.toString();
    return req<{ eliminados: number }>(`/causacion/historial${qs ? `?${qs}` : ""}`, { method: "DELETE" });
  },

  exportarLoteHistorial: (params?: { fechaDesde?: string; fechaHasta?: string }): Promise<Blob> => {
    const qp = new URLSearchParams();
    if (params?.fechaDesde) qp.set("fecha_desde", params.fechaDesde);
    if (params?.fechaHasta) qp.set("fecha_hasta", params.fechaHasta);
    const qs = qp.toString();
    return reqBlob(`/causacion/historial/exportar-lote${qs ? `?${qs}` : ""}`);
  },

  // Aprendizaje / IA
  getIAReglas: () => req<IARegla[]>("/aprendizaje/reglas"),
  getIAHistorial: (limit = 100) => req<IADecision[]>(`/aprendizaje/historial?limit=${limit}`),

  // Carga masiva catálogos
  cargarExcelImpuestos: (file: File) => _uploadExcel("/impuestos/cargar-excel", file),
  cargarExcelCuentas: (file: File) => _uploadExcel("/cuentas/cargar-excel", file),
  cargarExcelTipos: (file: File) => _uploadExcel("/tipos-comprobante/cargar-excel", file),

  // Plantillas Excel
  descargarPlantillaImpuestos: () => reqBlob("/impuestos/plantilla"),
  descargarPlantillaCuentas: () => reqBlob("/cuentas/plantilla"),
  descargarPlantillaTipos: () => reqBlob("/tipos-comprobante/plantilla"),

  // Limpieza de catálogos (soft-delete)
  limpiarImpuestos: () => req<{ desactivados: number }>("/impuestos/limpiar", { method: "POST" }),
  limpiarCuentas: () => req<{ desactivados: number }>("/cuentas/limpiar", { method: "POST" }),
  limpiarTipos: () => req<{ desactivados: number }>("/tipos-comprobante/limpiar", { method: "POST" }),

  // Eliminación individual (soft-delete)
  eliminarImpuesto: (codigo: string) => req<{ ok: boolean }>(`/impuestos/${codigo}`, { method: "DELETE" }),
  eliminarCuenta: (codigo: string) => req<{ ok: boolean }>(`/cuentas/${codigo}`, { method: "DELETE" }),
  eliminarTipo: (codigo: string) => req<{ ok: boolean }>(`/tipos-comprobante/${codigo}`, { method: "DELETE" }),
};
