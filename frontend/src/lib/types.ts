// ─── Catálogo ────────────────────────────────────────────────────────────────

export interface CuentaOpcion {
  codigo: string;
  nombre: string;
  label: string;
  tag?: string;
}

export interface ImpuestoOut {
  id: number;
  codigo: string;
  nombre: string | null;
  tipo_impuesto: string | null;
  tarifa: number | null;
  cta_ventas: string | null;
  cta_compras: string | null;
  cta_dev_ventas: string | null;
  cta_dev_compras: string | null;
  activo: boolean;
  created_at: string;
}

export interface TipoComprobanteOut {
  id: number;
  codigo: string;
  titulo: string;
  activo: boolean;
  created_at: string;
}

export interface TipoComprobanteOpcion {
  codigo: string;
  titulo: string;
  label: string;
}

export interface ConsecutivoOut {
  tipo_comp: string;
  ultimo: number;
  proximo: number;
}

// ─── Factura ya causada (historial) ──────────────────────────────────────────

export interface FacturaCausadaInfo {
  numero_dian: string;
  nit_proveedor: string | null;
  razon_social: string | null;
  fecha_factura: string | null;
  total: number | null;
  consecutivo: string | null;
  tipo_comprobante: string | null;
  fecha_causacion: string | null;
  datos_json: string | null;
}

// ─── Facturas / Parseo ────────────────────────────────────────────────────────

export interface ItemFactura {
  descripcion: string;
  base: number;
  valor_impuesto: number;
  cod_impuesto?: string;
  porcentaje?: number;
}

export interface Factura {
  numero_dian: string;
  razon_social: string;
  nit: string;
  fecha: string;
  total: number;
  tipo_proveedor?: string;
  regimen?: string;
  items: ItemFactura[];
  advertencias?: string[];
  _archivo?: string;
}

// ─── Sugerencia IA ────────────────────────────────────────────────────────────

export interface Sugerencia {
  cuenta: string | null;
  origen: string | null;
  explicacion_ia: string | null;
  confianza_ia: number | null;
  cuenta_pago_sugerida: string | null;
  cuenta_pago_origen: string | null;
}

// ─── Mapeo ────────────────────────────────────────────────────────────────────

export type FuenteMapeo = "aprendido" | "regla" | "sugerido" | "ia_alta" | "manual";

export interface MapeoItem {
  idx_factura: number;
  descripcion: string;
  base: number;
  cod_impuesto: string;
  porcentaje: number;
  valor_impuesto: number;
  cuenta_gasto: string;
  cuenta_sugerida?: string | null;
  fuente: FuenteMapeo;
  ia_confianza?: number | null;
  ia_explicacion?: string | null;
  ia_modelo?: string | null;
  cuenta_impuesto_deb: string;
  cuenta_impuesto_cre: string;
  es_retencion: boolean;
  cuenta_pago: string;
  cuenta_pago_nombre: string;
}

// ─── Validación ───────────────────────────────────────────────────────────────

export interface ValidacionComprobante {
  consecutivo: number;
  numero_dian: string;
  total_debito: number;
  total_credito: number;
  diferencia: number;
  cuadra: boolean;
}

export interface BatchValidacionResponse {
  comprobantes: ValidacionComprobante[];
  global_cuadra: boolean;
  gran_total_debitos: number;
  gran_total_creditos: number;
}

// ─── Historial ────────────────────────────────────────────────────────────────

export interface HistorialItem {
  id: number;
  consecutivo: string | null;
  numero_dian: string;
  nit_proveedor: string | null;
  razon_social: string | null;
  fecha_factura: string | null;
  fecha_causacion: string | null;
  total: number;
  tipo_comprobante: string | null;
  archivo_origen: string | null;
  tiene_datos: boolean;
}

export interface IARegla {
  id: number;
  patron: string;
  cuenta_puc: string;
  tipo: "keyword" | "regex";
  prioridad: number;
  version: number;
  activa: boolean;
  created_at: string;
}

export interface IADecision {
  id: number;
  numero_dian: string | null;
  nit_proveedor: string | null;
  descripcion_item: string | null;
  cuenta_sugerida: string | null;
  cuenta_aplicada: string | null;
  cod_impuesto: string | null;
  fue_corregida: boolean;
  origen: string | null;
  created_at: string;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  token_type: string;
  usuario_id: number;
  nombre: string;
  email: string;
  rol: string;
  empresa_id: number;
  empresa_nombre: string;
  email_verificado: boolean;
  tutorial_pendiente: boolean;
}

// ─── Wizard state ─────────────────────────────────────────────────────────────

export type PasoWizard = 1 | 2 | 3 | 4;
