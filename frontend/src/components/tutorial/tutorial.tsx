"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { useRouter, usePathname } from "next/navigation";
import {
  BookOpen, ChevronRight, X, Zap, CheckCircle2, ArrowRight, ArrowLeft,
  GripHorizontal, BookMarked, MapPin, Download, Brain,
} from "lucide-react";
import { useWizardStore } from "@/stores/wizard";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/lib/api";
import type { BatchValidacionResponse, Factura } from "@/lib/types";

// ─── Datos de demostración ────────────────────────────────────────────────────

const MOCK_FACTURAS: Factura[] = [
  {
    numero_dian: "FERM44825",
    razon_social: "FERROMATERIALES BELALCAZAR S.A.S.",
    nit: "900732630",
    fecha: "05/02/2026",
    total: 2750000,
    tipo_proveedor: "juridica",
    items: [
      { descripcion: "VARILLA CORRUGADA 1/2 PUERTA TRABAJO", base: 2310924, valor_impuesto: 439076, cod_impuesto: "1", porcentaje: 19 },
    ],
  },
  {
    numero_dian: "SE-241001",
    razon_social: "SOLUCIONES ELECTRICAS DEL PACÍFICO S.A.S.",
    nit: "901456789",
    fecha: "10/02/2026",
    total: 1190000,
    tipo_proveedor: "juridica",
    items: [
      { descripcion: "CABLEADO ESTRUCTURADO CAT 6A METROS", base: 1000000, valor_impuesto: 190000, cod_impuesto: "1", porcentaje: 19 },
    ],
  },
  {
    numero_dian: "FE-2026001",
    razon_social: "TRANSPORTES HERNÁNDEZ E.U.",
    nit: "800234567",
    fecha: "12/02/2026",
    total: 580000,
    tipo_proveedor: "natural",
    items: [
      { descripcion: "SERVICIO DE TRANSPORTE DE MATERIALES", base: 580000, valor_impuesto: 0, cod_impuesto: "22", porcentaje: 0 },
    ],
  },
];

// Factura 0 = Configurada, 1 = Pendiente, 2 = Verificada
// (0 tiene cuentas para que el botón Verificar sea visible al entrar al detalle)
const MOCK_MAPEO = {
  cuentaPago: { 0: "22050501", 2: "22050501" },
  cuentaGastoGlobal: { 0: "52300101", 2: "51300501" },
  verificadas: { 2: true },
};

const MOCK_TIPO_COMP = "DEMO";

const TUTORIAL_REPORTE: BatchValidacionResponse = {
  comprobantes: [
    { consecutivo: 1, numero_dian: "FERM44825", total_debito: 2750000, total_credito: 2750000, diferencia: 0, cuadra: true },
    { consecutivo: 2, numero_dian: "SE-241001",  total_debito: 1190000, total_credito: 1190000, diferencia: 0, cuadra: true },
    { consecutivo: 3, numero_dian: "FE-2026001", total_debito: 580000,  total_credito: 580000,  diferencia: 0, cuadra: true },
  ],
  global_cuadra: true,
  gran_total_debitos: 4520000,
  gran_total_creditos: 4520000,
};

// ─── Pasos ────────────────────────────────────────────────────────────────────

interface Step {
  id: string;
  selector?: string;
  title: string;
  body: string;
  position: "center" | "top" | "bottom" | "left" | "right";
  requiresPaso2?: boolean;
  requiresPaso3?: boolean;
  requiresPaso4?: boolean;
  // Clicks invoice-row-{invoiceRowIdx} antes de buscar el elemento (para entrar a la vista de detalle)
  invoiceRowIdx?: number;
  // Clicks "← Lista" antes de buscar el elemento (para volver a la vista de lista)
  backToList?: boolean;
  isCatalogInfo?: boolean;
  requiresCatalogos?: boolean;
  catalogTab?: string;
  isInfoStep?: boolean;
}

const STEPS: Step[] = [
  // ── Bienvenida ──────────────────────────────────────────────────────────────
  {
    id: "welcome",
    title: "¡Bienvenido a Ciolix!",
    body: "Esta plataforma automatiza la causación de facturas DIAN con inteligencia artificial y genera el archivo listo para importar en SIIGO. Te haré un recorrido por los dos módulos principales.",
    position: "center",
  },
  // ── Catálogos ───────────────────────────────────────────────────────────────
  {
    id: "catalogo-intro",
    title: "Prerequisito: Catálogos",
    body: "Antes de causar debes configurar tres catálogos: Códigos de Impuesto, Plan de Cuentas PUC y Tipos de Comprobante. Sin estos datos los selectores aparecerán vacíos. ¡Vamos a revisarlos!",
    position: "center",
    isCatalogInfo: true,
    requiresCatalogos: true,
  },
  {
    id: "tab-impuestos",
    selector: "[data-tutorial='tab-impuestos']",
    title: "1 · Códigos de Impuesto",
    body: "Aquí registras IVA 19%, retención en la fuente, ICA y demás códigos tributarios. Descarga la plantilla Excel, llena los datos y cárgala con 'Cargar desde Excel'. El sistema también acepta exportaciones directas de SIIGO.",
    position: "bottom",
    requiresCatalogos: true,
    catalogTab: "tab-impuestos",
  },
  {
    id: "tab-cuentas",
    selector: "[data-tutorial='tab-cuentas']",
    title: "2 · Plan de Cuentas PUC",
    body: "El PUC contiene las cuentas para gastos y pagos. Dos opciones: usa nuestra plantilla Excel, o exporta desde SIIGO (Contabilidad → Plan de Cuentas → Exportar) e impórtalo tal cual. El sistema detecta ambos formatos automáticamente.",
    position: "bottom",
    requiresCatalogos: true,
    catalogTab: "tab-cuentas",
  },
  {
    id: "tab-tipos",
    selector: "[data-tutorial='tab-tipos']",
    title: "3 · Tipos de Comprobante",
    body: "Define los comprobantes contables que usas (ej. Comprobante de Egreso, código 12). Igual que el PUC: usa nuestra plantilla o exporta desde SIIGO (Configuración → Tipos de Comprobante) e impórtalo directamente.",
    position: "bottom",
    requiresCatalogos: true,
    catalogTab: "tab-tipos",
  },
  {
    id: "tab-ia",
    selector: "[data-tutorial='tab-ia']",
    title: "4 · Control IA",
    body: "Aquí ves las reglas que el sistema ha aprendido y el historial de decisiones automáticas. Con el tiempo, la IA mejora sus sugerencias de cuentas basándose en las correcciones que hagas.",
    position: "bottom",
    requiresCatalogos: true,
    catalogTab: "tab-ia",
  },
  // ── Causación paso 1 ────────────────────────────────────────────────────────
  {
    id: "back-to-causacion",
    title: "¡Catálogos listos! Ahora a Causación",
    body: "Con los catálogos cargados ya puedes causar facturas. Vamos al módulo principal donde cargarás los archivos DIAN y configurarás las cuentas contables para cada factura.",
    position: "center",
  },
  {
    id: "dropzone",
    selector: "[data-tutorial='dropzone']",
    title: "5 · Carga tus facturas DIAN",
    body: "Arrastra aquí los archivos .xlsx exportados del portal DIAN o haz clic para seleccionarlos. Puedes cargar múltiples archivos a la vez — el sistema los fusiona automáticamente.",
    position: "bottom",
  },
  {
    id: "parse-btn",
    selector: "[data-tutorial='parse-btn']",
    title: "6 · Parsear facturas",
    body: "Este botón analiza los archivos y extrae todas las facturas: NIT del proveedor, fecha, ítems con impuesto y montos. También detecta si alguna ya fue causada anteriormente para evitar duplicados.",
    position: "top",
  },
  {
    id: "tipo-comprobante",
    selector: "[data-tutorial='tipo-comprobante']",
    title: "7 · Tipo de comprobante",
    body: "Selecciona el tipo de comprobante contable antes de mapear. Este campo es OBLIGATORIO — sin él el sistema no te dejará avanzar al paso 2. Ejemplo: Comprobante de Egreso (código 12).",
    position: "bottom",
  },
  // ── Causación paso 2 ────────────────────────────────────────────────────────
  {
    id: "invoice-list",
    selector: "[data-tutorial='invoice-list']",
    title: "8 · Lista de facturas (3 estados)",
    body: "Aquí aparecen las facturas con tres posibles badges: 🟠 Pendiente = sin cuentas configuradas; 🟢 Configurada = cuentas asignadas pero no verificada; ✅ Verificada = revisada y lista para generar el archivo.",
    position: "top",
    requiresPaso2: true,
    backToList: true,
  },
  {
    id: "invoice-detail",
    selector: "[data-tutorial='invoice-header']",
    title: "9 · Detalle de la factura",
    body: "Al hacer clic en una factura entras al detalle. Aquí ves NIT, razón social, fecha de emisión, tipo de proveedor (jurídica / natural) y el total de la factura.",
    position: "bottom",
    requiresPaso2: true,
    invoiceRowIdx: 0,
  },
  {
    id: "cuenta-gasto-global",
    selector: "[data-tutorial='cuenta-gasto']",
    title: "10 · Cuenta de gasto — zona GLOBAL",
    body: "La zona azul 'GLOBAL' aplica una cuenta de gasto/costo a TODOS los ítems de la factura con un solo campo. Ideal cuando todos los ítems van a la misma cuenta. También puedes agregar Retefuente o ReteICA globalmente.",
    position: "bottom",
    requiresPaso2: true,
  },
  {
    id: "cuenta-gasto-items",
    selector: "[data-tutorial='items-table']",
    title: "11 · Cuenta de gasto — ítem por ítem",
    body: "Si los ítems de la factura pertenecen a cuentas distintas, puedes asignar la cuenta individualmente en esta tabla. La IA analiza la descripción de cada ítem y sugiere automáticamente la cuenta más apropiada.",
    position: "top",
    requiresPaso2: true,
  },
  {
    id: "cuenta-pago",
    selector: "[data-tutorial='cuenta-pago']",
    title: "12 · Datos del proveedor y cuenta de pago",
    body: "En esta sección confirmas el NIT y tipo de proveedor. El campo 'Cuenta de pago' define el pasivo: elige Proveedores o CxP si la factura queda pendiente de pago (lo más común en B2B), o Caja/Bancos si fue pago de contado.",
    position: "bottom",
    requiresPaso2: true,
  },
  {
    id: "verificar-btn",
    selector: "[data-tutorial='verificar-btn']",
    title: "13 · Verificar la factura",
    body: "Cuando todas las cuentas estén configuradas, haz clic en ✓ Verificar (barra superior). Esto bloquea la factura para evitar cambios accidentales y la marca como lista para generar. Puedes quitar la verificación si necesitas editar.",
    position: "bottom",
    requiresPaso2: true,
    invoiceRowIdx: 0,
  },
  {
    id: "validar-partida-btn",
    selector: "[data-tutorial='validar-partida-btn']",
    title: "14 · Avanzar a Validar partida doble",
    body: "Con las facturas configuradas, vuelve a la lista y haz clic aquí. El sistema verificará que los débitos = créditos en cada comprobante antes de generar el archivo SIIGO.",
    position: "bottom",
    requiresPaso2: true,
    backToList: true,
  },
  // ── Paso 3 ──────────────────────────────────────────────────────────────────
  {
    id: "paso3-validar",
    selector: "[data-tutorial='validar-reporte']",
    title: "Paso 3 · Tabla de partida doble",
    body: "El sistema valida automáticamente que débitos = créditos en cada comprobante. Si todo cuadra verás ✅ en cada fila y el gran total también cuadra en la última fila.",
    position: "bottom",
    requiresPaso3: true,
  },
  {
    id: "paso3-generar",
    selector: "[data-tutorial='generar-btn']",
    title: "Paso 3 · Generar archivo SIIGO",
    body: "Cuando todos los comprobantes cuadran, este botón se activa. Al hacer clic genera el archivo Excel listo para importar en SIIGO y avanza al paso final.",
    position: "top",
    requiresPaso3: true,
  },
  // ── Paso 4 ──────────────────────────────────────────────────────────────────
  {
    id: "paso4-descargar",
    selector: "[data-tutorial='descargar-btn']",
    title: "Paso 4 · Descargar archivo SIIGO",
    body: "Este botón descarga el Excel para importar en SIIGO. Ve a SIIGO → Contabilidad → Importar comprobantes y selecciona este archivo. Contiene todos los comprobantes con sus consecutivos.",
    position: "top",
    requiresPaso4: true,
  },
  {
    id: "paso4-aprendizaje",
    selector: "[data-tutorial='guardar-aprendizaje-btn']",
    title: "Paso 4 · Guardar aprendizaje (MUY IMPORTANTE)",
    body: "Después de importar en SIIGO, vuelve aquí y haz clic en este botón. Registra las decisiones de cuentas que tomaste para que la IA las use como referencia y mejore sus sugerencias en futuras causaciones.",
    position: "top",
    requiresPaso4: true,
  },
  // ── Fin ─────────────────────────────────────────────────────────────────────
  {
    id: "done",
    title: "¡Ya conoces Ciolix!",
    body: "Tienes todo lo necesario para causar facturas DIAN. Recuerda el flujo: Catálogos → Cargar facturas → Mapear cuentas → Verificar → Validar partida → Generar SIIGO → Confirmar aprendizaje.",
    position: "center",
    isInfoStep: true,
  },
];

// ─── Posicionamiento del tooltip ──────────────────────────────────────────────

const PADDING = 14;
const TOOLTIP_W = 370;

interface Rect { top: number; left: number; width: number; height: number; bottom: number; right: number; }

function getTooltipPosition(rect: Rect | null, position: Step["position"]): React.CSSProperties {
  if (!rect || position === "center") {
    return { position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: TOOLTIP_W };
  }
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const TOOLTIP_H = 280;
  let top = 0;
  let left = Math.min(rect.left, vw - TOOLTIP_W - 16);
  left = Math.max(left, 16);
  if (position === "bottom") {
    top = rect.bottom + PADDING + 8;
    // Si no cabe abajo, colocar arriba
    if (top + TOOLTIP_H > vh - 16) top = rect.top - PADDING - 8 - TOOLTIP_H;
  } else if (position === "top") {
    top = rect.top - PADDING - 8 - TOOLTIP_H;
    // Si no cabe arriba, colocar abajo
    if (top < 16) top = rect.bottom + PADDING + 8;
  } else if (position === "right") {
    top = Math.min(rect.top, vh - TOOLTIP_H - 16);
    left = Math.min(rect.right + PADDING + 8, vw - TOOLTIP_W - 16);
  } else if (position === "left") {
    top = Math.min(rect.top, vh - TOOLTIP_H - 16);
    left = Math.max(rect.left - TOOLTIP_W - PADDING - 8, 16);
  }
  top = Math.max(16, Math.min(top, vh - TOOLTIP_H - 16));
  return { position: "fixed", top, left, width: TOOLTIP_W };
}

// ─── Tutorial component ───────────────────────────────────────────────────────

export function Tutorial() {
  const [mounted, setMounted] = useState(false);
  const [phase, setPhase] = useState<"prompt" | "tour" | "idle">("idle");
  const [stepIdx, setStepIdx] = useState(0);
  const [targetRect, setTargetRect] = useState<Rect | null>(null);

  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, ox: 0, oy: 0 });

  const router = useRouter();
  const pathname = usePathname();

  const {
    setFacturas, setTipoComp, setPaso, paso,
    setTutorialActivo, setTutorialMockMapeo,
    setReporte, setXlsxBlob,
  } = useWizardStore();
  const { usuario, setTutorialPendiente } = useAuthStore();

  useEffect(() => {
    setMounted(true);
    if (usuario?.tutorial_pendiente) {
      setTimeout(() => setPhase("prompt"), 800);
    }
  }, [usuario?.id, usuario?.tutorial_pendiente]);

  // Listeners de drag global
  useEffect(() => {
    if (!isDragging) return;
    const onMove = (e: MouseEvent) => {
      setDragOffset({
        x: dragStart.current.ox + (e.clientX - dragStart.current.x),
        y: dragStart.current.oy + (e.clientY - dragStart.current.y),
      });
    };
    const onUp = () => setIsDragging(false);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [isDragging]);

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    dragStart.current = { x: e.clientX, y: e.clientY, ox: dragOffset.x, oy: dragOffset.y };
    setIsDragging(true);
  };

  const currentStep = STEPS[stepIdx];

  // Actualizar posición del target
  // – Para pasos con invoiceRowIdx: click la fila primero, luego busca el elemento
  // – Para pasos con backToList: click "← Lista" primero, luego busca el elemento
  // – Para el resto: busca el elemento directamente
  useEffect(() => {
    if (phase !== "tour" || !currentStep.selector) {
      setTargetRect(null);
      return;
    }

    let clickTimer: ReturnType<typeof setTimeout> | undefined;
    let findTimer: ReturnType<typeof setTimeout> | undefined;
    let innerTimer: ReturnType<typeof setTimeout> | undefined;

    const doCapture = (selector: string) => {
      const el = document.querySelector(selector);
      if (!el) { setTargetRect(null); return; }
      el.scrollIntoView({ behavior: "auto", block: "nearest" });
      innerTimer = setTimeout(() => {
        const r = el.getBoundingClientRect();
        setTargetRect({ top: r.top, left: r.left, width: r.width, height: r.height, bottom: r.bottom, right: r.right });
      }, 80);
    };

    if (currentStep.invoiceRowIdx !== undefined) {
      // Hace click en la fila de la factura (puede ser no-op si ya estamos en detalle)
      const rowIdx = currentStep.invoiceRowIdx;
      clickTimer = setTimeout(() => {
        document.querySelector<HTMLElement>(`[data-tutorial='invoice-row-${rowIdx}']`)?.click();
      }, 150);
      // Busca el elemento después de que React re-renderice
      findTimer = setTimeout(() => doCapture(currentStep.selector!), 700);
    } else if (currentStep.backToList) {
      // Hace click en "← Lista" (puede ser no-op si ya estamos en la lista)
      clickTimer = setTimeout(() => {
        document.querySelector<HTMLElement>("[data-tutorial='back-to-list-btn']")?.click();
      }, 150);
      findTimer = setTimeout(() => doCapture(currentStep.selector!), 700);
    } else {
      findTimer = setTimeout(() => doCapture(currentStep.selector!), 420);
    }

    return () => {
      clearTimeout(clickTimer);
      clearTimeout(findTimer);
      clearTimeout(innerTimer);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, stepIdx, pathname]);

  // Navegación a /catalogos
  useEffect(() => {
    if (phase !== "tour" || !currentStep.requiresCatalogos) return;

    if (pathname !== "/catalogos") {
      router.push("/catalogos");
      return;
    }
    if (currentStep.catalogTab) {
      const t = setTimeout(() => {
        document.querySelector<HTMLElement>(`[data-tutorial='${currentStep.catalogTab}']`)?.click();
      }, 350);
      return () => clearTimeout(t);
    }
  }, [phase, stepIdx, currentStep, pathname, router]);

  // Gestión del wizard (causacion)
  useEffect(() => {
    if (phase !== "tour" || currentStep.requiresCatalogos) return;

    // Pasos con selector en causacion (excepto paso3/paso4)
    if (currentStep.selector && !currentStep.requiresPaso2 && !currentStep.requiresPaso3 && !currentStep.requiresPaso4) {
      if (pathname !== "/causacion") { router.push("/causacion"); return; }
    }

    if (currentStep.requiresPaso4) {
      if (pathname !== "/causacion") { router.push("/causacion"); return; }
      if (paso !== 4) {
        setReporte(TUTORIAL_REPORTE);
        setXlsxBlob(new Blob(["tutorial-demo"], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
        setPaso(4);
      }
    } else if (currentStep.requiresPaso3) {
      if (pathname !== "/causacion") { router.push("/causacion"); return; }
      if (paso !== 3) {
        setPaso(3);
      }
    } else if (currentStep.requiresPaso2) {
      if (pathname !== "/causacion") { router.push("/causacion"); return; }
      if (paso !== 2) {
        setTutorialMockMapeo(MOCK_MAPEO);
        setFacturas(MOCK_FACTURAS);
        setTipoComp(MOCK_TIPO_COMP);
        setPaso(2);
      }
      // Los clicks a invoice-row o back-to-list están en el efecto de scroll
    } else if (currentStep.isInfoStep) {
      // Paso final informativo: reset al paso 1 con fondo limpio
      if (paso !== 1) {
        setFacturas([]);
        setTipoComp("");
        setTutorialMockMapeo(null);
        setPaso(1);
      }
    } else if (currentStep.id !== "back-to-causacion") {
      // Pasos de paso1 (dropzone, parse-btn, tipo-comprobante)
      if (pathname !== "/causacion") { router.push("/causacion"); return; }
      if (paso !== 1) {
        setFacturas([]);
        setTipoComp("");
        setTutorialMockMapeo(null);
        setPaso(1);
      }
    }
  }, [phase, stepIdx, currentStep, paso, pathname, router, setFacturas, setTipoComp, setPaso, setTutorialMockMapeo, setReporte, setXlsxBlob]);

  const startTutorial = useCallback(() => {
    setStepIdx(0);
    setPhase("tour");
    setTipoComp("");
    setPaso(1);
    setTutorialActivo(true);
  }, [setTipoComp, setPaso, setTutorialActivo]);

  const finish = useCallback(() => {
    setPhase("idle");
    setFacturas([]);
    setTipoComp("");
    setTutorialMockMapeo(null);
    setPaso(1);
    setTutorialActivo(false);
    api.actualizarTutorial(false).catch(() => {});
    setTutorialPendiente(false);
    if (typeof window !== "undefined" && !window.location.pathname.includes("causacion")) {
      router.push("/causacion");
    }
  }, [setFacturas, setTipoComp, setTutorialMockMapeo, setPaso, setTutorialActivo, setTutorialPendiente, router]);

  const next = useCallback(() => {
    if (stepIdx >= STEPS.length - 1) { finish(); return; }
    setStepIdx(s => s + 1);
  }, [stepIdx, finish]);

  const prev = useCallback(() => {
    if (stepIdx <= 0) return;
    setStepIdx(s => s - 1);
  }, [stepIdx]);

  if (!mounted || phase === "idle") return null;

  const baseStyle = getTooltipPosition(targetRect, currentStep.position);
  const existingTransform = (baseStyle.transform as string) ?? "";
  const tooltipStyle: React.CSSProperties = {
    ...baseStyle,
    transform: dragOffset.x !== 0 || dragOffset.y !== 0
      ? `${existingTransform} translate(${dragOffset.x}px, ${dragOffset.y}px)`.trim()
      : existingTransform || undefined,
    userSelect: "none",
  };

  const progress = Math.round(((stepIdx + 1) / STEPS.length) * 100);

  const stepIcon = currentStep.isCatalogInfo
    ? <BookMarked style={{ height: 14, width: 14, color: "rgb(245,158,11)" }} />
    : currentStep.requiresCatalogos
    ? <MapPin style={{ height: 14, width: 14, color: "rgb(99,102,241)" }} />
    : currentStep.id === "paso4-aprendizaje"
    ? <Brain style={{ height: 14, width: 14, color: "rgb(16,185,129)" }} />
    : currentStep.id === "paso4-descargar"
    ? <Download style={{ height: 14, width: 14, color: "rgb(59,130,246)" }} />
    : null;

  const iconBg = currentStep.isCatalogInfo
    ? "rgba(245,158,11,0.12)"
    : currentStep.requiresCatalogos
    ? "rgba(99,102,241,0.12)"
    : currentStep.id === "paso4-aprendizaje"
    ? "rgba(16,185,129,0.12)"
    : currentStep.id === "paso4-descargar"
    ? "rgba(59,130,246,0.12)"
    : null;

  const isLastStep = stepIdx === STEPS.length - 1;

  const content = (
    <>
      {/* Overlay con spotlight */}
      <div style={{ position: "fixed", inset: 0, zIndex: 9000, pointerEvents: phase === "tour" ? "auto" : "none" }}>
        {phase === "tour" && targetRect ? (
          <svg width="100%" height="100%" style={{ position: "fixed", inset: 0, display: "block", pointerEvents: "none" }}>
            <defs>
              <mask id="sc-spotlight">
                <rect width="100%" height="100%" fill="white" />
                <rect x={targetRect.left - PADDING} y={targetRect.top - PADDING}
                  width={targetRect.width + PADDING * 2} height={targetRect.height + PADDING * 2}
                  rx="10" fill="black" />
              </mask>
            </defs>
            <rect width="100%" height="100%" fill="rgba(0,0,0,0.72)" mask="url(#sc-spotlight)" />
            <rect x={targetRect.left - PADDING} y={targetRect.top - PADDING}
              width={targetRect.width + PADDING * 2} height={targetRect.height + PADDING * 2}
              rx="10" fill="none" stroke="#3b82f6" strokeWidth="2.5"
              style={{ filter: "drop-shadow(0 0 8px rgba(59,130,246,0.6))" }} />
          </svg>
        ) : (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.72)", pointerEvents: "none" }} />
        )}
      </div>

      {/* Prompt bienvenida */}
      {phase === "prompt" && (
        <div style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: 16, zIndex: 9001 }}>
          <div style={{
            position: "relative", width: "100%", maxWidth: 440, borderRadius: 20, overflow: "hidden",
            backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-soft)",
            boxShadow: "0 32px 64px rgba(0,0,0,0.6)",
          }}>
            <div style={{ padding: "2rem 2rem 1.5rem", textAlign: "center", background: "linear-gradient(160deg, rgba(59,130,246,0.12), rgba(99,102,241,0.08))" }}>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  height: 64, width: 64, borderRadius: 16,
                  background: "linear-gradient(135deg, #3b82f6, #6366f1)",
                  boxShadow: "0 8px 24px rgba(59,130,246,0.45)",
                }}>
                  <BookOpen style={{ height: 32, width: 32, color: "#fff" }} />
                </div>
              </div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                ¡Bienvenido a Ciolix!
              </h2>
              <p style={{ marginTop: 8, fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                ¿Deseas hacer un recorrido rápido para conocer cómo funciona la plataforma?
              </p>
            </div>
            <div style={{ padding: "1.5rem 2rem", display: "flex", flexDirection: "column", gap: 10 }}>
              <button onClick={startTutorial} style={{
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                width: "100%", borderRadius: 12, padding: "12px 16px",
                fontWeight: 600, fontSize: "0.875rem",
                backgroundColor: "var(--brand)", color: "#fff", border: "none", cursor: "pointer",
              }}>
                <BookOpen style={{ height: 16, width: 16 }} />
                Sí, muéstrame el tutorial
                <ChevronRight style={{ height: 16, width: 16, marginLeft: "auto" }} />
              </button>
              <button onClick={finish} style={{
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                width: "100%", borderRadius: 12, padding: "10px 16px",
                fontSize: "0.875rem", color: "var(--text-muted)",
                backgroundColor: "transparent", border: "none", cursor: "pointer",
              }}>
                <Zap style={{ height: 14, width: 14 }} />
                Saltar, ya conozco la plataforma
              </button>
            </div>
            <div style={{
              padding: "10px 2rem", textAlign: "center", fontSize: "0.75rem",
              color: "var(--text-muted)", borderTop: "1px solid var(--border-soft)",
            }}>
              Puedes volver a ver el tutorial desde Perfil → Reiniciar tutorial
            </div>
          </div>
        </div>
      )}

      {/* Tooltip del tour */}
      {phase === "tour" && (
        <div style={{
          ...tooltipStyle, zIndex: 9001, borderRadius: 16,
          backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-soft)",
          boxShadow: "0 24px 48px rgba(0,0,0,0.55)", overflow: "hidden",
        }}>
          {/* Barra de progreso */}
          <div style={{ height: 3, backgroundColor: "var(--border-soft)" }}>
            <div style={{
              height: "100%", width: `${progress}%`,
              background: "linear-gradient(90deg, #3b82f6, #6366f1)",
              transition: "width 0.4s ease",
            }} />
          </div>

          {/* Handle de arrastre */}
          <div onMouseDown={handleDragStart} style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: "6px 0 2px", cursor: isDragging ? "grabbing" : "grab",
            color: "var(--text-muted)", opacity: 0.5,
          }} title="Arrastrar para mover">
            <GripHorizontal style={{ height: 14, width: 14 }} />
          </div>

          <div style={{ padding: "8px 20px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {stepIcon && iconBg && (
                  <div style={{
                    display: "flex", alignItems: "center", justifyContent: "center",
                    height: 28, width: 28, borderRadius: 8, flexShrink: 0,
                    backgroundColor: iconBg,
                  }}>
                    {stepIcon}
                  </div>
                )}
                <h3 style={{ fontSize: "0.875rem", fontWeight: 700, lineHeight: 1.4, color: "var(--text-primary)", margin: 0 }}>
                  {currentStep.title}
                </h3>
              </div>
              <button onClick={finish} style={{
                flexShrink: 0, borderRadius: 8, padding: 4,
                color: "var(--text-muted)", backgroundColor: "transparent", border: "none", cursor: "pointer",
              }} title="Saltar tutorial">
                <X style={{ height: 16, width: 16 }} />
              </button>
            </div>

            {/* Descripción */}
            <p style={{ fontSize: "0.875rem", lineHeight: 1.6, color: "var(--text-secondary)", margin: 0 }}>
              {currentStep.body}
            </p>

            {/* Footer */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                {stepIdx + 1} / {STEPS.length}
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                {stepIdx > 0 && (
                  <button onClick={prev} style={{
                    display: "flex", alignItems: "center", gap: 6,
                    borderRadius: 12, padding: "8px 14px",
                    fontSize: "0.875rem", fontWeight: 500,
                    backgroundColor: "var(--bg-elevated)",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border-soft)",
                    cursor: "pointer",
                  }}>
                    <ArrowLeft style={{ height: 16, width: 16 }} />
                    Anterior
                  </button>
                )}
                <button onClick={next} style={{
                  display: "flex", alignItems: "center", gap: 6,
                  borderRadius: 12, padding: "8px 16px",
                  fontSize: "0.875rem", fontWeight: 600,
                  backgroundColor: "var(--brand)", color: "#fff", border: "none", cursor: "pointer",
                }}>
                  {isLastStep ? (
                    <><CheckCircle2 style={{ height: 16, width: 16 }} /> ¡Entendido!</>
                  ) : (
                    <>Siguiente <ArrowRight style={{ height: 16, width: 16 }} /></>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );

  return createPortal(content, document.body);
}
