"use client";
import { create } from "zustand";
import type {
  BatchValidacionResponse,
  Factura,
  MapeoItem,
  PasoWizard,
  Sugerencia,
} from "@/lib/types";

interface WizardState {
  paso: PasoWizard;
  tipoComp: string;
  centroCosto: string;
  facturas: Factura[];
  mapeos: MapeoItem[];
  reporte: BatchValidacionResponse | null;
  xlsxBlob: Blob | null;
  suggestions: Record<string, Sugerencia>;

  setPaso: (p: PasoWizard) => void;
  setTipoComp: (t: string) => void;
  setCentroCosto: (c: string) => void;
  setFacturas: (f: Factura[]) => void;
  setMapeos: (m: MapeoItem[]) => void;
  setReporte: (r: BatchValidacionResponse) => void;
  setXlsxBlob: (b: Blob) => void;
  setSuggestions: (s: Record<string, Sugerencia>) => void;
  reset: () => void;
}

const initial = {
  paso: 1 as PasoWizard,
  tipoComp: "",
  centroCosto: "",
  facturas: [],
  mapeos: [],
  reporte: null,
  xlsxBlob: null,
  suggestions: {},
};

export const useWizardStore = create<WizardState>((set) => ({
  ...initial,
  setPaso: (paso) => set({ paso }),
  setTipoComp: (tipoComp) => set({ tipoComp }),
  setCentroCosto: (centroCosto) => set({ centroCosto }),
  setFacturas: (facturas) => set({ facturas }),
  setMapeos: (mapeos) => set({ mapeos }),
  setReporte: (reporte) => set({ reporte }),
  setXlsxBlob: (xlsxBlob) => set({ xlsxBlob }),
  setSuggestions: (suggestions) => set({ suggestions }),
  reset: () => set(initial),
}));
