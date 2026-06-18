"use client";
import { create } from "zustand";
import type {
  BatchValidacionResponse,
  Factura,
  MapeoItem,
  PasoWizard,
} from "@/lib/types";

interface WizardState {
  paso: PasoWizard;
  tipoComp: string;
  centroCosto: string;
  facturas: Factura[];
  mapeos: MapeoItem[];
  reporte: BatchValidacionResponse | null;
  xlsxBlob: Blob | null;

  setPaso: (p: PasoWizard) => void;
  setTipoComp: (t: string) => void;
  setCentroCosto: (c: string) => void;
  setFacturas: (f: Factura[]) => void;
  setMapeos: (m: MapeoItem[]) => void;
  setReporte: (r: BatchValidacionResponse) => void;
  setXlsxBlob: (b: Blob) => void;
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
  reset: () => set(initial),
}));
