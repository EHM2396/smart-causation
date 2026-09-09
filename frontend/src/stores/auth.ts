import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { LoginResponse } from "@/lib/types";
import { BRAND } from "@/lib/brand";

interface AuthState {
  token: string | null;
  empresaId: number | null;
  empresaNombre: string | null;
  // El usuario eligió activamente la empresa con la que va a trabajar.
  // Para usuarios con >1 empresa se exige elegir antes de operar.
  empresaConfirmada: boolean;
  usuario: {
    id: number;
    email: string;
    nombre: string;
    rol: string;
    tutorial_pendiente: boolean;
  } | null;
  _hydrated: boolean;
  login: (data: LoginResponse) => void;
  logout: () => void;
  setEmpresa: (id: number, nombre: string) => void;
  limpiarEmpresa: () => void;   // deja el selector sin empresa (obliga a elegir de nuevo)
  setTutorialPendiente: (v: boolean) => void;
  _setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      empresaId: null,
      empresaNombre: null,
      empresaConfirmada: false,
      usuario: null,
      _hydrated: false,
      login: (data) =>
        set({
          token: data.access_token,
          empresaId: data.empresa_id,
          empresaNombre: data.empresa_nombre,
          empresaConfirmada: false,   // se decide tras cargar las empresas del usuario
          usuario: {
            id: data.usuario_id,
            email: data.email,
            nombre: data.nombre,
            rol: data.rol,
            tutorial_pendiente: data.tutorial_pendiente ?? true,
          },
        }),
      logout: () =>
        set({ token: null, empresaId: null, empresaNombre: null, empresaConfirmada: false, usuario: null }),
      setEmpresa: (id, nombre) =>
        set({ empresaId: id, empresaNombre: nombre, empresaConfirmada: true }),
      limpiarEmpresa: () =>
        set({ empresaId: null, empresaNombre: null, empresaConfirmada: false }),
      setTutorialPendiente: (v) =>
        set((s) => s.usuario ? { usuario: { ...s.usuario, tutorial_pendiente: v } } : {}),
      _setHydrated: () => set({ _hydrated: true }),
    }),
    {
      name: BRAND.storageKey,
      onRehydrateStorage: () => (state) => {
        state?._setHydrated();
      },
    }
  )
);
