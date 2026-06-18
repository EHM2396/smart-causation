import type {
  BatchValidacionResponse,
  ConsecutivoOut,
  CuentaOpcion,
  HistorialItem,
  IADecision,
  IARegla,
  ImpuestoOut,
  TipoComprobanteOpcion,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Catálogo ─────────────────────────────────────────────────────────────────

export const api = {
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
    const form = new FormData();
    form.append("archivo", file);
    const res = await fetch(`${BASE}/causacion/parsear`, {
      method: "POST",
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
  batchGenerar: async (
    body: {
      items: { factura: object; mapeos_confirmados: object[] }[];
      tipo_comprobante: string;
      centro_costo: string;
      confirmar: boolean;
    }
  ): Promise<Blob> => {
    const res = await fetch(`${BASE}/causacion/batch/generar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Error generando: ${res.status}`);
    return res.blob();
  },

  // Historial de causaciones
  getHistorial: (params?: { fechaDesde?: string; fechaHasta?: string; buscar?: string }) => {
    const qp = new URLSearchParams();
    if (params?.fechaDesde) qp.set("fecha_desde", params.fechaDesde);
    if (params?.fechaHasta) qp.set("fecha_hasta", params.fechaHasta);
    if (params?.buscar) qp.set("buscar", params.buscar);
    const qs = qp.toString();
    return req<HistorialItem[]>(`/causacion/historial${qs ? `?${qs}` : ""}`);
  },

  regenerarHistorial: async (id: number): Promise<Blob> => {
    const res = await fetch(`${BASE}/causacion/historial/${id}/regenerar`, { method: "POST" });
    if (!res.ok) {
      const msg = await res.text().catch(() => res.statusText);
      throw new Error(`Error regenerando: ${msg}`);
    }
    return res.blob();
  },

  limpiarHistorial: (params?: { fechaDesde?: string; fechaHasta?: string }) => {
    const qp = new URLSearchParams();
    if (params?.fechaDesde) qp.set("fecha_desde", params.fechaDesde);
    if (params?.fechaHasta) qp.set("fecha_hasta", params.fechaHasta);
    const qs = qp.toString();
    return req<{ eliminados: number }>(`/causacion/historial${qs ? `?${qs}` : ""}`, { method: "DELETE" });
  },

  exportarLoteHistorial: async (params?: { fechaDesde?: string; fechaHasta?: string }): Promise<Blob> => {
    const qp = new URLSearchParams();
    if (params?.fechaDesde) qp.set("fecha_desde", params.fechaDesde);
    if (params?.fechaHasta) qp.set("fecha_hasta", params.fechaHasta);
    const qs = qp.toString();
    const res = await fetch(`${BASE}/causacion/historial/exportar-lote${qs ? `?${qs}` : ""}`);
    if (!res.ok) {
      const msg = await res.text().catch(() => res.statusText);
      throw new Error(msg);
    }
    return res.blob();
  },

  // Aprendizaje / IA
  getIAReglas: () => req<IARegla[]>("/aprendizaje/reglas"),
  getIAHistorial: (limit = 100) => req<IADecision[]>(`/aprendizaje/historial?limit=${limit}`),
};
