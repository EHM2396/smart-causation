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

export interface FacturaOmitida {
  filename: string;
  numero: string;
  motivo: "venta" | "ya_causada";
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
  nit_comprador?: string;
  fecha: string;
  total: number;
  tipo_proveedor?: string;
  regimen?: string;
  medio_pago?: string;
  forma_pago?: string;
  items: ItemFactura[];
  advertencias?: string[];
  _archivo?: string;
}

// ─── DIAN (integración por token) ─────────────────────────────────────────────

export interface DianDocumento {
  id: string | null;
  numero: string;
  fecha: string;
  proveedor: string;
  tipo: string;
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
  filas: number;  // nº de movimientos que esta factura aporta al archivo SIIGO
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
  subtotal: number | null;
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

// ─── Terceros ─────────────────────────────────────────────────────────────────

export interface TerceroOut {
  id: number;
  nit: string;
  digito_verificacion: number | null;
  codigo_sucursal: string | null;
  tipo_identificacion: number | null;
  tipo_persona: string | null;
  razon_social: string | null;
  nombres_tercero: string | null;
  apellidos_tercero: string | null;
  nombre_comercial: string | null;
  direccion: string | null;
  ciudad: string | null;
  departamento: string | null;
  codigo_pais: string | null;
  codigo_departamento: string | null;
  codigo_ciudad_siigo: string | null;
  codigo_postal: string | null;
  indicativo_tel: number | null;
  telefono: string | null;
  extension_tel: string | null;
  email: string | null;
  regimen: string | null;
  tipo_regimen_iva: string | null;
  codigo_responsabilidad: string | null;
  cuenta_pagar: string | null;
  nombres_contacto: string | null;
  apellidos_contacto: string | null;
  indicativo_tel_contacto: number | null;
  telefono_contacto: string | null;
  extension_tel_contacto: string | null;
  email_contacto: string | null;
  es_cliente: boolean;
  activo: boolean;
  ia_habilitada: boolean | null;
  fuente: string | null;
  empresa_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface TipoIdentificacionOut {
  codigo: number;
  descripcion: string;
}

export interface DepartamentoOut {
  codigo: string;
  nombre: string;
  pais_codigo: string | null;
}

export interface CiudadOut {
  codigo: string;
  nombre: string;
  departamento_codigo: string | null;
  pais_codigo: string | null;
}

export interface SiigoTipoPersonaOut {
  codigo: string;
  descripcion: string;
  valor_interno: string | null;
}

export interface SiigoRegimenIvaOut {
  codigo: string;
  etiqueta: string;
}

export interface SiigoResponsabilidadFiscalOut {
  codigo: string;
  descripcion: string;
}

export interface TercerosCatalogos {
  tipos_identificacion: TipoIdentificacionOut[];
  paises: { codigo: string; nombre: string }[];
  tipos_persona: SiigoTipoPersonaOut[];
  regimenes_iva: SiigoRegimenIvaOut[];
  responsabilidades_fiscales: SiigoResponsabilidadFiscalOut[];
}

export interface TercerosStats {
  total: number;
  juridicas: number;
  naturales: number;
  completos: number;
  pct_completos: number;
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

// ─── Borrador de causación (guardado temporal) ────────────────────────────────

/** Configuración de paso 2 capturada en el borrador (espejo del estado local
 * de paso2.tsx). Incluye baseOverride, que no está en Paso2Cache. */
export interface Paso2Snapshot {
  facturaCount: number;
  cuentaPago: Record<number, string>;
  tipoProveedor: Record<number, string>;
  nitEdit: Record<number, string>;
  cuentaGastoGlobal: Record<number, string>;
  rfGlobal: Record<number, string>;
  riGlobal: Record<number, string>;
  codImpuestoGlobal: Record<number, string>;
  cuentaIvaGlobal: Record<number, string>;
  cuentaGastoItem: Record<string, string>;
  rfItem: Record<string, string>;
  riItem: Record<string, string>;
  codImpuestoItem: Record<string, string>;
  cuentaIvaItem: Record<string, string>;
  verificadas: Record<number, boolean>;
  baseOverride: Record<string, string>;
}

/** Snapshot completo del wizard que se serializa en el borrador. */
export interface BorradorSnapshot {
  facturas: Factura[];
  tipoComp: string;
  centroCosto: string;
  facturasYaCausadas: FacturaCausadaInfo[];
  facturasOmitidas: FacturaOmitida[];
  suggestions: Record<string, Sugerencia>;
  paso2: Paso2Snapshot;
}

export interface BorradorResumen {
  id: number;
  total_facturas: number;
  total_verificadas: number;
  tipo_comp: string | null;
  actualizado_at: string;
}

export interface BorradorCompleto extends BorradorResumen {
  datos: BorradorSnapshot;
}
