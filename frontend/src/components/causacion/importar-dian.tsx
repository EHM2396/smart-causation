"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import {
  AlertTriangle, Search, Download, Loader2, ShieldCheck, KeyRound, CalendarDays, X,
  ShoppingCart, TrendingUp, FileMinus2, ArrowRight, CheckCircle2, FileCheck2, Check, ListChecks, Info,
} from "lucide-react";
import type { DocTipo } from "@/stores/wizard";
import type { DianDocumento, Factura } from "@/lib/types";
import { ordenarPorFechaEmision, periodosIVA, MAX_MESES_CONSULTA, limiteHasta, AVISO_TOPE_CALENDARIO } from "@/lib/utils";

// YYYY-MM-DD (input date) → DD/MM/YYYY (formato que espera el portal DIAN)
function isoToDian(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  const [, y, mo, d] = m;
  return `${d}/${mo}/${y}`;
}
function hoyISO(offsetDias = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDias);
  return d.toISOString().slice(0, 10);
}
function limpiarError(raw: string): string {
  const jsonPart = raw.replace(/^API\s+\d+:\s*/, "");
  try {
    const parsed = JSON.parse(jsonPart);
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch { /* no era JSON */ }
  return jsonPart || raw;
}

type Bucket = "compras" | "nc" | "ventas" | "nc_ventas" | "soporte" | "nc_soporte";

// Fuente = de dónde se CONSULTA cada documento en el portal de la DIAN. Ojo: en
// una misma fuente viajan juntas las facturas y sus notas crédito (la DIAN no las
// separa en el listado; se separan al parsear el XML). Por eso "Facturas de
// compra" y "NC de compra" comparten la fuente ``compras``.
type Fuente = "compras" | "ventas" | "soporte" | "soporte_ajuste";
type ItemKey =
  | "facturas_compra" | "nc_compra"
  | "facturas_venta" | "nc_venta"
  | "documento_soporte" | "nc_soporte";

interface ItemSeleccion { key: ItemKey; label: string; bucket: Bucket; fuente: Fuente; grupo: string }

// Los 6 tipos que el usuario puede elegir extraer, agrupados por MÓDULO. Solo se
// puede traer UN módulo a la vez (compras, ventas o soporte): elegir uno deselecciona
// los otros. Es a propósito — mezclar módulos recarga la consulta y era lo que
// hacía que se perdieran documentos. Dentro de un módulo, factura y su nota
// crédito viajan juntas en el listado de la DIAN (se separan al parsear el XML).
const GRUPOS_SELECCION: { id: string; titulo: string; icon: typeof ShoppingCart; color: string; items: ItemSeleccion[] }[] = [
  { id: "compras", titulo: "Compras (recibidos)", icon: ShoppingCart, color: "#4F46E5", items: [
    { key: "facturas_compra", label: "Facturas de compra",       bucket: "compras", fuente: "compras", grupo: "compras" },
    { key: "nc_compra",       label: "Notas crédito de compra",   bucket: "nc",      fuente: "compras", grupo: "compras" },
  ]},
  { id: "ventas", titulo: "Ventas (emitidos)", icon: TrendingUp, color: "#0ea5a4", items: [
    { key: "facturas_venta",  label: "Facturas de venta",         bucket: "ventas",    fuente: "ventas", grupo: "ventas" },
    { key: "nc_venta",        label: "Notas crédito de venta",     bucket: "nc_ventas", fuente: "ventas", grupo: "ventas" },
  ]},
  { id: "soporte", titulo: "Documentos soporte", icon: FileCheck2, color: "#0284c7", items: [
    { key: "documento_soporte", label: "Documento soporte",           bucket: "soporte",    fuente: "soporte",         grupo: "soporte" },
    { key: "nc_soporte",        label: "Nota de ajuste al soporte",    bucket: "nc_soporte", fuente: "soporte_ajuste",  grupo: "soporte" },
  ]},
];
const ITEMS_SELECCION: ItemSeleccion[] = GRUPOS_SELECCION.flatMap((g) => g.items);
const _grupoDe = (k: ItemKey): string => ITEMS_SELECCION.find((i) => i.key === k)!.grupo;

const DESTINOS: { tipo: Bucket; ruta: string; label: string; icon: typeof ShoppingCart; color: string }[] = [
  { tipo: "compras",    ruta: "/causacion",           label: "Causación Compras", icon: ShoppingCart, color: "#4F46E5" },
  { tipo: "nc",         ruta: "/causacion-nc",         label: "NC Compras",        icon: FileMinus2,   color: "#7c3aed" },
  { tipo: "ventas",     ruta: "/causacion-ventas",     label: "Causación Ventas",  icon: TrendingUp,   color: "#0ea5a4" },
  { tipo: "nc_ventas",  ruta: "/causacion-nc-ventas",  label: "NC Ventas",         icon: FileMinus2,   color: "#d97706" },
  { tipo: "soporte",    ruta: "/causacion-soporte",    label: "Documento Soporte", icon: FileCheck2,   color: "#0284c7" },
  { tipo: "nc_soporte", ruta: "/causacion-nc-soporte", label: "Ajuste Soporte",    icon: FileMinus2,   color: "#9333ea" },
];

// Separa facturas / NC / ND usando la clase que deduce el backend del listado DIAN.
// Solo se descargan los tipos elegidos. Las ND no se traen (no hay módulo que las
// cause) y lo "desconocido" se baja igual para que el XML decida y nada se oculte.
function separarListado(docs: DianDocumento[], quiereFacturas: boolean, quiereNc: boolean) {
  const conteo = { facturas: 0, nc: 0, nd: 0, desconocidos: 0 };
  const ids: string[] = [];
  for (const d of docs) {
    if (!d.id) continue;
    const clase = d.clase ?? "desconocido";
    if (clase === "factura") {
      conteo.facturas += 1;
      if (quiereFacturas) ids.push(d.id);
    } else if (clase === "nota_credito") {
      conteo.nc += 1;
      if (quiereNc) ids.push(d.id);
    } else if (clase === "nota_debito") {
      conteo.nd += 1;
    } else {
      conteo.desconocidos += 1;
      if (quiereFacturas || quiereNc) ids.push(d.id);
    }
  }
  return { conteo, ids };
}

function DescartadasInfo({ entries }: { entries: [string, number][] }) {
  if (!entries.length) return null;
  return (
    <div className="rounded-lg border p-3 space-y-1"
      style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-elevated)" }}>
      <p className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
        Documentos que no quedaron en tu módulo:
      </p>
      {entries.map(([tipo, n]) => {
        const d = DESTINOS.find((x) => x.tipo === tipo);
        if (!d) return null;
        const Icon = d.icon;
        return (
          <div key={tipo} className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
            <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: d.color }} />
            <span>
              <strong>{n}</strong> {d.label} — al leer el archivo de la DIAN resultaron ser de un tipo que no elegiste.
              Para causarlas, vuelve a consultar con ese tipo activo.
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function ImportarDian() {
  const qc = useQueryClient();
  const presets = useMemo(periodosIVA, []);
  const [authUrl, setAuthUrl] = useState("");
  const [desde, setDesde] = useState(() => presets[0].desde);
  const [hasta, setHasta] = useState(() => presets[0].hasta);
  const presetActivo = presets.find((p) => p.desde === desde && p.hasta === hasta)?.id ?? "personalizado";
  const hoy = hoyISO(0);
  const maxHasta = limiteHasta(desde) < hoy ? limiteHasta(desde) : hoy;
  // Al mover "desde", si "hasta" queda a más de 4 meses se recorta al tope.
  const cambiarDesde = (v: string) => {
    setDesde(v);
    const lim = limiteHasta(v) < hoy ? limiteHasta(v) : hoy;
    if (hasta > lim) setHasta(lim);
  };
  const rangoExcedido = hasta > limiteHasta(desde);

  // Selección de qué extraer. Solo UN módulo a la vez (compras, ventas o soporte);
  // por defecto, el primero con sus dos tipos activos. Elegir un tipo de otro
  // módulo cambia de módulo y deselecciona el anterior — nunca se mezclan, para
  // no recargar la consulta ni volver a perder documentos.
  const [seleccion, setSeleccion] = useState<Record<ItemKey, boolean>>(
    () => Object.fromEntries(
      ITEMS_SELECCION.map((i) => [i.key, i.grupo === GRUPOS_SELECCION[0].id]),
    ) as Record<ItemKey, boolean>,
  );
  // Módulo actualmente elegido (el de cualquier tipo activo; el invariante
  // garantiza que todos los activos son del mismo módulo).
  const grupoActivo = ITEMS_SELECCION.find((i) => seleccion[i.key])?.grupo ?? null;
  const toggleItem = (k: ItemKey) => {
    // Cambiar de módulo invalida la consulta hecha (era de otra bandeja de la DIAN).
    if (grupoActivo !== null && grupoActivo !== _grupoDe(k)) { setResultado(null); setResumen(null); }
    cambiarSeleccion(k);
  };
  const cambiarSeleccion = (k: ItemKey) => setSeleccion((prev) => {
    const activo = ITEMS_SELECCION.find((i) => prev[i.key])?.grupo ?? null;
    if (activo === null || activo === _grupoDe(k)) {
      // Mismo módulo (o ninguno aún): alternar este tipo normalmente.
      return { ...prev, [k]: !prev[k] };
    }
    // Otro módulo: cambiar de módulo → dejar activo SOLO este tipo.
    const limpio = Object.fromEntries(ITEMS_SELECCION.map((i) => [i.key, false])) as Record<ItemKey, boolean>;
    return { ...limpio, [k]: true };
  });
  const algunoSeleccionado = ITEMS_SELECCION.some((i) => seleccion[i.key]);
  // Fuentes a consultar: una fuente se pide si al menos uno de sus tipos está activo.
  const fuentesSeleccionadas = (): Fuente[] => {
    const s = new Set<Fuente>();
    for (const it of ITEMS_SELECCION) if (seleccion[it.key]) s.add(it.fuente);
    return [...s];
  };
  // Módulos a los que SÍ se distribuye (los tipos activos). Un módulo no elegido
  // no se escribe aunque su documento haya venido en la misma fuente que otro sí.
  const bucketsPermitidos = (): Set<Bucket> =>
    new Set(ITEMS_SELECCION.filter((i) => seleccion[i.key]).map((i) => i.bucket));

  const [consultando, setConsultando] = useState(false);
  const [importando, setImportando] = useState(false);
  const [prog, setProg] = useState({ done: 0, total: 0 });
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<{ grupo: string | null; docsCompras: DianDocumento[]; docsVentas: DianDocumento[]; idsSoporte: string[]; idsSoporteAjuste: string[]; advertenciasIncompleto: string[] } | null>(null);
  const [resumen, setResumen] = useState<{ encontradas: Record<Bucket, number>; agregadas: Record<Bucket, number>; mostrados: Bucket[]; descartadas: Partial<Record<Bucket, number>> } | null>(null);
  const [erroresImport, setErroresImport] = useState(0);
  // Se cortó la conexión A MITAD del lote (no un documento puntual): lo ya
  // traído hasta ese momento igual se guardó — solo falta reintentar el resto.
  const [conexionCortada, setConexionCortada] = useState(false);

  const consultar = async () => {
    if (!authUrl.trim()) { setError("Pega la URL de AuthToken de la DIAN."); return; }
    if (!algunoSeleccionado) { setError("Elige al menos un tipo de documento para extraer."); return; }
    if (rangoExcedido) { setError(`El periodo no puede ser mayor a ${MAX_MESES_CONSULTA} meses. Acorta las fechas o consulta por partes.`); return; }
    setConsultando(true); setError(""); setResultado(null); setResumen(null);
    try {
      const res = await api.dianConsultarTodo({
        auth_url: authUrl.trim(), fecha_desde: isoToDian(desde), fecha_hasta: isoToDian(hasta),
        fuentes: fuentesSeleccionadas(),
      });
      const idsSoporte = res.soporte.documents.map((d) => d.id).filter((x): x is string => !!x);
      const idsSoporteAjuste = res.soporte_ajuste.documents.map((d) => d.id).filter((x): x is string => !!x);
      const emitidoAparte = new Set([...idsSoporte, ...idsSoporteAjuste]);
      // Los DS y sus ajustes se consultan aparte (tipo 05/95): se quitan de ventas
      // por si aparecieran también en la bandeja de emitidos, para no duplicar.
      const docsVentas = res.ventas.documents.filter((d) => !!d.id && !emitidoAparte.has(d.id));
      const advertenciasIncompleto = [
        res.compras.advertencia,
        res.ventas.advertencia,
        res.soporte.advertencia,
        res.soporte_ajuste.advertencia,
      ].filter((a): a is string => !!a);
      setResultado({
        grupo: grupoActivo,
        docsCompras: res.compras.documents, docsVentas,
        idsSoporte, idsSoporteAjuste,
        advertenciasIncompleto,
      });
    } catch (e) {
      setError(limpiarError((e as Error).message));
    } finally {
      setConsultando(false);
    }
  };

  const distribuir = async (buckets: Record<Bucket, Factura[]>, permitidos: Set<Bucket>) => {
    // encontradas: documentos que trajo ESTE lote de la DIAN, antes de descartar
    // duplicados. agregadas: las que realmente terminaron NUEVAS en el borrador
    // (la DIAN a veces lista el mismo documento más de una vez — reenvíos,
    // eventos de validación — y ya estar en el borrador tampoco cuenta). Se
    // muestran ambas para que un número "agregadas" menor que "encontradas" no
    // se lea como pérdida de datos: es el sistema evitando duplicar la misma
    // factura.
    // descartadas: tipos que LLEGARON en la descarga (la DIAN los incluye en la
    // misma bandeja) pero el usuario NO los eligió, por lo que se saltan. Se
    // muestran en el resumen para que el usuario entienda la diferencia entre
    // el total del "Consultar" y el total que quedó en su módulo.
    const encontradas: Record<Bucket, number> = { compras: 0, nc: 0, ventas: 0, nc_ventas: 0, soporte: 0, nc_soporte: 0 };
    const agregadas: Record<Bucket, number> = { compras: 0, nc: 0, ventas: 0, nc_ventas: 0, soporte: 0, nc_soporte: 0 };
    const descartadas: Partial<Record<Bucket, number>> = {};
    for (const { tipo } of DESTINOS) {
      // Un módulo que el usuario NO eligió no se toca, aunque su documento haya
      // venido en la misma fuente que otro sí elegido (p. ej. traer solo facturas
      // de compra: las NC llegan en la misma bandeja pero no se distribuyen).
      // Se registran en `descartadas` para mostrárselas al usuario y que entienda
      // por qué el número final difiere del conteo de la consulta.
      if (!permitidos.has(tipo)) {
        const n = buckets[tipo]?.length ?? 0;
        if (n > 0) descartadas[tipo] = n;
        continue;
      }
      const nuevasSinOrdenar = buckets[tipo] ?? [];
      encontradas[tipo] = nuevasSinOrdenar.length;
      if (!nuevasSinOrdenar.length) continue;
      // La DIAN devuelve los documentos más recientes primero; se ordenan de más
      // antigua a más reciente ANTES de fusionar (así SIIGO asigna los
      // consecutivos en orden cronológico, no al revés).
      const nuevas = ordenarPorFechaEmision(nuevasSinOrdenar);
      // Fusionar con lo que ya haya en ese borrador (sin duplicar por numero_dian,
      // ni contra lo existente NI dentro del propio lote nuevo — la DIAN puede
      // listar el mismo documento más de una vez). Solo se ordena el lote NUEVO:
      // lo existente no se reordena, porque su posición puede estar ligada a
      // configuración ya guardada (cuenta, verificada…) por índice.
      const completo = await api.getBorradorCompleto(tipo as DocTipo);
      const prev = (completo?.datos ?? {}) as Record<string, unknown>;
      const existentes = (prev.facturas as Factura[]) ?? [];
      const nums = new Set(existentes.map((f) => f.numero_dian));
      const nuevasUnicas: Factura[] = [];
      for (const f of nuevas) {
        if (nums.has(f.numero_dian)) continue;
        nums.add(f.numero_dian);
        nuevasUnicas.push(f);
      }
      agregadas[tipo] = nuevasUnicas.length;
      const merged = [...existentes, ...nuevasUnicas];
      const snapshot = {
        facturas: merged,
        tipoComp: (prev.tipoComp as string) ?? "",
        centroCosto: (prev.centroCosto as string) ?? "",
        facturasYaCausadas: prev.facturasYaCausadas ?? [],
        facturasOmitidas: prev.facturasOmitidas ?? [],
        suggestions: prev.suggestions ?? {},
        paso2: prev.paso2 ?? null,
      };
      await api.guardarBorrador({
        datos: snapshot as unknown as Record<string, unknown>,
        total_facturas: merged.length,
        total_verificadas: 0,
        tipo_comp: snapshot.tipoComp || null,
      }, tipo as DocTipo);
      qc.invalidateQueries({ queryKey: ["borrador", tipo] });
    }
    return { encontradas, agregadas, descartadas };
  };

  // Lo que se va a traer se deriva de la consulta + la selección actual: si el
  // usuario activa o quita las NC después de consultar, los números se ajustan solos.
  const sepCompras = separarListado(resultado?.docsCompras ?? [], seleccion.facturas_compra, seleccion.nc_compra);
  const sepVentas = separarListado(resultado?.docsVentas ?? [], seleccion.facturas_venta, seleccion.nc_venta);
  const idsSoporteATraer = seleccion.documento_soporte ? (resultado?.idsSoporte ?? []) : [];
  const idsAjusteATraer = seleccion.nc_soporte ? (resultado?.idsSoporteAjuste ?? []) : [];
  const totalATraer = sepCompras.ids.length + sepVentas.ids.length + idsSoporteATraer.length + idsAjusteATraer.length;
  const notasDebito = sepCompras.conteo.nd + sepVentas.conteo.nd;
  const sinTipoClaro = sepCompras.conteo.desconocidos + sepVentas.conteo.desconocidos;
  const consultaVacia = !!resultado && resultado.docsCompras.length + resultado.docsVentas.length
    + resultado.idsSoporte.length + resultado.idsSoporteAjuste.length === 0;
  const tarjetasConsulta: { key: ItemKey; label: string; n: number; color: string; icon: typeof ShoppingCart }[] =
    resultado?.grupo === "compras" ? [
      { key: "facturas_compra", label: "Facturas de compra", n: sepCompras.conteo.facturas, color: "#4F46E5", icon: ShoppingCart },
      { key: "nc_compra", label: "Notas crédito de compra", n: sepCompras.conteo.nc, color: "#7c3aed", icon: FileMinus2 },
    ] : resultado?.grupo === "ventas" ? [
      { key: "facturas_venta", label: "Facturas de venta", n: sepVentas.conteo.facturas, color: "#0ea5a4", icon: TrendingUp },
      { key: "nc_venta", label: "Notas crédito de venta", n: sepVentas.conteo.nc, color: "#d97706", icon: FileMinus2 },
    ] : resultado?.grupo === "soporte" ? [
      { key: "documento_soporte", label: "Documento soporte", n: resultado.idsSoporte.length, color: "#0284c7", icon: FileCheck2 },
      { key: "nc_soporte", label: "Nota de ajuste al soporte", n: resultado.idsSoporteAjuste.length, color: "#9333ea", icon: FileMinus2 },
    ] : [];

  const importar = async () => {
    if (!resultado) return;
    const totalDocs = totalATraer;
    if (!totalDocs) { setError("No hay documentos para traer en este rango."); return; }
    setImportando(true); setError(""); setResumen(null); setErroresImport(0); setConexionCortada(false);
    setProg({ done: 0, total: totalDocs });
    try {
      const { buckets, errores, conexionError } = await api.dianImportarTodoStream(
        { auth_url: authUrl.trim(), ids_compras: sepCompras.ids, ids_ventas: sepVentas.ids, ids_soporte: idsSoporteATraer, ids_soporte_ajuste: idsAjusteATraer },
        (done, total) => setProg({ done, total }),
      );
      // SIEMPRE se distribuye lo que se alcanzó a traer, aunque la conexión se
      // haya cortado a mitad de camino — así nunca se pierde el progreso ni hay
      // que volver a empezar desde cero.
      const permitidos = bucketsPermitidos();
      const conteo = await distribuir(buckets, permitidos);
      setResumen({ ...conteo, mostrados: [...permitidos], descartadas: conteo.descartadas });
      setErroresImport(errores);
      setConexionCortada(!!conexionError);
    } catch (e) {
      setError(limpiarError((e as Error).message));
    } finally {
      setImportando(false);
      setProg({ done: 0, total: 0 });
    }
  };

  const pct = prog.total > 0 ? Math.round((prog.done / prog.total) * 100) : 0;
  // Pre-computado aquí (fuera del JSX) para evitar pasar tipos genéricos
  // complejos como props de JSX, que confunden al parser de Turbopack/SWC.
  const descartadasEntries: [string, number][] = resumen
    ? Object.entries(resumen.descartadas).filter(([, n]) => !!n)
    : [];

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 lg:py-10 space-y-5">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Importar de la DIAN</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Pega el token, elige el rango y <strong>un módulo a la vez</strong> (Compras, Ventas o Documentos soporte).
          El sistema trae ese módulo completo —parte el rango por fechas si hace falta, para que no se pierda ninguno—
          y separa la factura de su nota crédito en el módulo que corresponde. Con el mismo token puedes repetir para otro módulo.
        </p>
      </div>

      {/* Aviso de seguridad */}
      <div className="flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}>
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--info-text)" }} />
        <div className="text-xs leading-relaxed" style={{ color: "var(--info-text)" }}>
          Inicia sesión en el portal de la DIAN, copia la <strong>URL de AuthToken</strong> y pégala aquí.
          Con un solo token se traen recibidas (compras), emitidas (ventas) y documentos soporte. Tu token es temporal y no se guarda.
        </div>
      </div>

      {/* URL AuthToken */}
      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <KeyRound className="h-4 w-4" style={{ color: "var(--brand)" }} /> URL AuthToken de la DIAN
        </label>
        <input
          type="text"
          value={authUrl}
          onChange={(e) => setAuthUrl(e.target.value)}
          placeholder="https://catalogo-vpfe.dian.gov.co/User/AuthToken?pk=...&rk=...&token=..."
          className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--brand)]"
          style={{ borderColor: "var(--border-strong)", backgroundColor: "var(--bg-surface)", color: "var(--text-primary)" }}
        />
      </div>

      {/* Periodo */}
      <div className="space-y-2.5">
        <label className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <CalendarDays className="h-4 w-4" style={{ color: "var(--brand)" }} /> Periodo
        </label>
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => {
            const active = presetActivo === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => { setDesde(p.desde); setHasta(p.hasta); }}
                className="rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors"
                style={{
                  backgroundColor: active ? "var(--brand)" : "var(--bg-elevated)",
                  color: active ? "#fff" : "var(--text-secondary)",
                  border: `1px solid ${active ? "var(--brand)" : "var(--border-soft)"}`,
                }}
              >
                {p.label}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <DatePicker label="Desde" value={desde} onChange={cambiarDesde} max={hasta} />
          <span className="pb-2 text-xs" style={{ color: "var(--text-muted)" }}>hasta</span>
          <DatePicker
            label="Hasta" value={hasta} onChange={setHasta} min={desde} max={maxHasta}
            hint={AVISO_TOPE_CALENDARIO}
          />
        </div>
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2"
          style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}>
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: "var(--info-text)" }} />
          <p className="text-xs leading-relaxed" style={{ color: "var(--info-text)" }}>
            <strong>Máximo {MAX_MESES_CONSULTA} meses por consulta.</strong> Por eso el calendario bloquea los días que se
            pasan de ese límite. Para un periodo más largo, consulta por partes con el mismo token.
          </p>
        </div>
      </div>

      {/* Qué extraer — el usuario elige UN módulo ANTES de consultar. Solo uno a la
          vez (elegir otro deselecciona el anterior): mezclar módulos recarga la
          consulta y era lo que hacía que se perdieran documentos. */}
      <div className="space-y-2.5">
        <label className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <ListChecks className="h-4 w-4" style={{ color: "var(--brand)" }} /> Qué extraer
          <span className="font-normal" style={{ color: "var(--text-muted)" }}>— un módulo a la vez</span>
        </label>
        <div className="grid gap-3 sm:grid-cols-3">
          {GRUPOS_SELECCION.map((g) => {
            const Icon = g.icon;
            const esActivo = grupoActivo === g.id;
            const atenuado = grupoActivo !== null && !esActivo;
            return (
              <div
                key={g.id}
                className="rounded-xl border p-3 space-y-2 transition-opacity"
                style={{
                  borderColor: esActivo ? g.color : "var(--border-soft)",
                  backgroundColor: "var(--bg-surface)",
                  opacity: atenuado ? 0.55 : 1,
                }}
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4" style={{ color: g.color }} />
                  <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{g.titulo}</span>
                </div>
                <div className="space-y-1.5">
                  {g.items.map((it) => {
                    const on = seleccion[it.key];
                    return (
                      <button
                        key={it.key}
                        type="button"
                        onClick={() => toggleItem(it.key)}
                        disabled={consultando || importando}
                        className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition-colors hover:opacity-90 disabled:opacity-60"
                        aria-pressed={on}
                        title={atenuado ? "Cambia a este módulo (deselecciona el otro)" : undefined}
                        style={{ backgroundColor: on ? "var(--bg-elevated)" : "transparent" }}
                      >
                        <span
                          className="flex h-4 w-4 shrink-0 items-center justify-center rounded"
                          style={{
                            backgroundColor: on ? "var(--brand)" : "transparent",
                            border: `1.5px solid ${on ? "var(--brand)" : "var(--border-strong)"}`,
                          }}
                        >
                          {on && <Check className="h-3 w-3" style={{ color: "#fff" }} />}
                        </span>
                        <span style={{ color: on ? "var(--text-primary)" : "var(--text-secondary)" }}>{it.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Solo puedes traer un módulo por consulta. Para otro módulo, termina este y vuelve a consultar con el mismo token.
        </p>
      </div>

      <Button onClick={consultar} disabled={consultando || importando || !algunoSeleccionado} size="lg" className="gap-2">
        {consultando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        {consultando ? "Consultando DIAN…" : "Consultar"}
      </Button>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--error-border)", backgroundColor: "var(--error-bg)" }} role="alert">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--error-text)" }} />
          <div className="flex-1">
            <p className="text-sm font-semibold" style={{ color: "var(--error-text)" }}>No pudimos consultar la DIAN</p>
            <p className="mt-0.5 text-sm" style={{ color: "var(--error-text)", opacity: 0.9 }}>{error}</p>
          </div>
          <button type="button" onClick={() => setError("")} style={{ color: "var(--error-text)" }}><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Resultado de la consulta */}
      {resultado && !resumen && (
        <div className="rounded-xl border p-4 space-y-4" style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Encontrado en el rango
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {tarjetasConsulta.map(({ key, label, n, color, icon: Icon }) => {
              const activo = seleccion[key];
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => cambiarSeleccion(key)}
                  disabled={importando}
                  aria-pressed={activo}
                  title={activo ? "Toca para no traerlas" : "Toca para incluirlas"}
                  className="rounded-lg border p-3 text-left transition-opacity hover:opacity-90 disabled:cursor-not-allowed"
                  style={{
                    borderColor: activo ? color + "66" : "var(--border-soft)",
                    backgroundColor: "var(--bg-elevated)",
                    opacity: activo ? 1 : 0.6,
                  }}
                >
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4" style={{ color }} />
                    <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</span>
                    <span
                      className="ml-auto flex h-4 w-4 shrink-0 items-center justify-center rounded"
                      style={{ backgroundColor: activo ? "var(--brand)" : "transparent", border: `1.5px solid ${activo ? "var(--brand)" : "var(--border-strong)"}` }}
                    >
                      {activo && <Check className="h-3 w-3" style={{ color: "#fff" }} />}
                    </span>
                  </div>
                  <p className="mt-1 text-2xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{n}</p>
                  <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {activo ? "Se traerán" : "No seleccionadas — no se traerán"}
                  </p>
                </button>
              );
            })}
          </div>
          {consultaVacia && (
            <div className="flex items-start gap-2 rounded-lg border p-3"
              style={{ borderColor: "var(--info-border)", backgroundColor: "var(--info-bg)" }}>
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--info-text)" }} />
              <p className="text-xs leading-relaxed" style={{ color: "var(--info-text)" }}>
                La DIAN no devolvió documentos en este rango. Si esperabas encontrar algunos, <strong>genera un enlace
                nuevo</strong> en el portal de la DIAN y vuelve a consultar: el enlace dura una hora y, cuando vence, a
                veces la DIAN responde vacío en lugar de avisar.
              </p>
            </div>
          )}
          {(notasDebito > 0 || sinTipoClaro > 0) && (
            <div className="space-y-1 text-xs" style={{ color: "var(--text-muted)" }}>
              {notasDebito > 0 && (
                <p>
                  Además hay <strong>{notasDebito}</strong> nota{notasDebito !== 1 ? "s" : ""} débito en el rango. No se traen porque
                  Ciolix todavía no las causa.
                </p>
              )}
              {sinTipoClaro > 0 && (
                <p>
                  <strong>{sinTipoClaro}</strong> documento{sinTipoClaro !== 1 ? "s" : ""} no traen el tipo en el listado de la DIAN. Se
                  traerán igual y quedarán en el módulo que corresponda al leer el archivo.
                </p>
              )}
            </div>
          )}
          {/* Advertencia de importación incompleta — se muestra cuando la DIAN
              reportó más documentos de los que pudo devolver. Es crítico que el
              contador lo vea ANTES de traer, para que ajuste el rango. */}
          {resultado.advertenciasIncompleto.length > 0 && (
            <div className="rounded-xl border-2 p-4 space-y-2"
              style={{ borderColor: "#F59E0B", backgroundColor: "#FEF3C7" }}
              role="alert">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 shrink-0" style={{ color: "#B45309" }} />
                <p className="text-sm font-bold" style={{ color: "#92400E" }}>
                  Consulta incompleta — la DIAN no entregó todos los documentos
                </p>
              </div>
              {resultado.advertenciasIncompleto.map((adv, i) => (
                <p key={i} className="text-sm pl-7" style={{ color: "#92400E" }}>{adv}</p>
              ))}
              <p className="text-xs pl-7 font-semibold" style={{ color: "#92400E" }}>
                Vuelve a consultar antes de traer; si se repite, acorta el rango de fechas.
              </p>
            </div>
          )}

          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Al traer, cada documento va a su módulo: facturas a Compras/Ventas, notas crédito a NC, y los documentos soporte (y sus ajustes) a Documento Soporte.
          </p>

          {importando && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
                <span>Descargando y clasificando…</span><span>{prog.done}/{prog.total}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full" style={{ backgroundColor: "var(--border-soft)" }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: "var(--brand)" }} />
              </div>
            </div>
          )}

          <Button onClick={importar} disabled={importando || totalATraer === 0} size="lg" className="gap-2 w-full">
            {importando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {importando ? "Trayendo…" : `Traer ${totalATraer} y distribuir`}
          </Button>
        </div>
      )}

      {/* Resumen tras distribuir */}
      {resumen && (
        <div className="rounded-xl border p-4 space-y-4" style={{ borderColor: "var(--success-border)", backgroundColor: "var(--success-bg)" }}>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5" style={{ color: "var(--success-text)" }} />
            <p className="text-sm font-semibold" style={{ color: "var(--success-text)" }}>Listo — los documentos quedaron en su módulo</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {DESTINOS.filter(({ tipo }) => resumen.mostrados.includes(tipo)).map(({ tipo, ruta, label, icon: Icon, color }) => (
              <Link
                key={tipo}
                href={ruta}
                className="flex items-center justify-between rounded-lg border p-3 transition-opacity hover:opacity-80"
                style={{ borderColor: "var(--border-soft)", backgroundColor: "var(--bg-surface)" }}
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4" style={{ color }} />
                  <span className="text-sm" style={{ color: "var(--text-primary)" }}>{label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{resumen.agregadas[tipo]}</span>
                  {resumen.agregadas[tipo] < resumen.encontradas[tipo] && (
                    <span
                      className="text-[10px] tabular-nums"
                      style={{ color: "var(--text-muted)" }}
                      title="La DIAN listó estos documentos más de una vez (reenvíos/eventos de validación); no se duplican en el módulo."
                    >
                      ({resumen.encontradas[tipo]} encontradas, {resumen.encontradas[tipo] - resumen.agregadas[tipo]} repetida{resumen.encontradas[tipo] - resumen.agregadas[tipo] !== 1 ? "s" : ""})
                    </span>
                  )}
                  <ArrowRight className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
                </div>
              </Link>
            ))}
          </div>
          <DescartadasInfo entries={descartadasEntries} />
          <p className="text-xs" style={{ color: "var(--success-text)", opacity: 0.9 }}>
            Entra a cada módulo (verás la tarjeta &quot;Continuar borrador&quot;) para mapear las cuentas y causar.
            Se fusionaron con lo que ya tenías sin duplicar.
          </p>

          {(erroresImport > 0 || conexionCortada) && (
            <div className="rounded-lg border p-3 space-y-2" style={{ borderColor: "var(--warning-border)", backgroundColor: "var(--warning-bg)" }}>
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--warning-text)" }} />
                <p className="text-xs" style={{ color: "var(--warning-text)" }}>
                  {conexionCortada ? (
                    <><strong>Se cortó la conexión con la DIAN</strong> antes de terminar de traer todo el lote.</>
                  ) : (
                    <><strong>{erroresImport} documento(s) no se pudieron traer</strong> (fallo de red o descarga).</>
                  )}{" "}
                  Lo que ya se alcanzó a traer <strong>quedó guardado</strong> (no se perdió). Dale <strong>Reintentar</strong> para
                  completar lo que falta — no se duplica lo que ya entró.
                </p>
              </div>
              <Button onClick={() => { void importar(); }} disabled={importando} size="sm" className="gap-1.5">
                {importando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                {importando ? "Reintentando…" : "Reintentar lo que falta"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
