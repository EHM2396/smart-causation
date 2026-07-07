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
  setTutorialActivo: (tutorialActivo) => set({ tutorialActivo }),
  setTutorialMockMapeo: (tutorialMockMapeo) => set({ tutorialMockMapeo }),
  reset: () => set(initial),
}));
