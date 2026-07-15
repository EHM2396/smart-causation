"use client";
import { create } from "zustand";
import type {
  BatchValidacionResponse,
  Factura,
  FacturaCausadaInfo,
  MapeoItem,
  PasoWizard,
  Sugerencia,
} from "@/lib/types";

interface TutorialMockMapeo {
  cuentaPago: Record<number, string>;
  cuentaGastoGlobal: Record<number, string>;
  verificadas: Record<number, boolean>;
}

interface Paso2Cache {
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
}

interface WizardState {
  paso: PasoWizard;
  tipoComp: string;
  centroCosto: string;
  facturas: Factura[];
  facturasParaCausar: Factura[];
  facturasYaCausadas: FacturaCausadaInfo[];
  mapeos: MapeoItem[];
  reporte: BatchValidacionResponse | null;
  xlsxBlob: Blob | null;
  suggestions: Record<string, Sugerencia>;
  pdfUrls: Record<string, string>;
  paso2Cache: Paso2Cache | null;
  tutorialActivo: boolean;
  tutorialMockMapeo: TutorialMockMapeo | null;

  setPaso: (p: PasoWizard) => void;
  setTipoComp: (t: string) => void;
  setCentroCosto: (c: string) => void;
  setFacturas: (f: Factura[]) => void;
  setFacturasParaCausar: (f: Factura[]) => void;
  setFacturasYaCausadas: (f: FacturaCausadaInfo[]) => void;
  setMapeos: (m: MapeoItem[]) => void;
  setReporte: (r: BatchValidacionResponse) => void;
  setXlsxBlob: (b: Blob) => void;
  setSuggestions: (s: Record<string, Sugerencia>) => void;
  setPdfUrls: (urls: Record<string, string>) => void;
  setPaso2Cache: (cache: Paso2Cache | null) => void;
  setTutorialActivo: (v: boolean) => void;
  setTutorialMockMapeo: (m: TutorialMockMapeo | null) => void;
  reset: () => void;
}

const initial = {
  paso: 1 as PasoWizard,
  tipoComp: "",
  centroCosto: "",
  facturas: [],
  facturasParaCausar: [],
  facturasYaCausadas: [],
  mapeos: [],
  reporte: null,
  xlsxBlob: null,
  suggestions: {},
  pdfUrls: {} as Record<string, string>,
  paso2Cache: null as Paso2Cache | null,
  tutorialActivo: false,
  tutorialMockMapeo: null,
};

export const useWizardStore = create<WizardState>((set) => ({
  ...initial,
  setPaso: (paso) => set({ paso }),
  setTipoComp: (tipoComp) => set({ tipoComp }),
  setCentroCosto: (centroCosto) => set({ centroCosto }),
  setFacturas: (facturas) => set({ facturas }),
  setFacturasParaCausar: (facturasParaCausar) => set({ facturasParaCausar }),
  setFacturasYaCausadas: (facturasYaCausadas) => set({ facturasYaCausadas }),
  setMapeos: (mapeos) => set({ mapeos }),
  setReporte: (reporte) => set({ reporte }),
  setXlsxBlob: (xlsxBlob) => set({ xlsxBlob }),
  setSuggestions: (suggestions) => set({ suggestions }),
  setPdfUrls: (pdfUrls) => set({ pdfUrls }),
  setPaso2Cache: (paso2Cache) => set({ paso2Cache }),
  setTutorialActivo: (tutorialActivo) => set({ tutorialActivo }),
  setTutorialMockMapeo: (tutorialMockMapeo) => set({ tutorialMockMapeo }),
  reset: () => set((state) => {
    Object.values(state.pdfUrls).forEach((url) => { try { URL.revokeObjectURL(url); } catch {} });
    return initial;
  }),
}));
