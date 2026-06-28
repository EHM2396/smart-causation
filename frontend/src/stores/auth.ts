import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { LoginResponse } from "@/lib/types";

interface AuthState {
  token: string | null;
  empresaId: number | null;
  empresaNombre: string | null;
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
  setTutorialPendiente: (v: boolean) => void;
  _setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      empresaId: null,
      empresaNombre: null,
      usuario: null,
      _hydrated: false,
      login: (data) =>
        set({
          token: data.access_token,
          empresaId: data.empresa_id,
          empresaNombre: data.empresa_nombre,
          usuario: {
            id: data.usuario_id,
            email: data.email,
            nombre: data.nombre,
            rol: data.rol,
            tutorial_pendiente: data.tutorial_pendiente ?? true,
          },
        }),
      logout: () =>
        set({ token: null, empresaId: null, empresaNombre: null, usuario: null }),
      setTutorialPendiente: (v) =>
        set((s) => s.usuario ? { usuario: { ...s.usuario, tutorial_pendiente: v } } : {}),
      _setHydrated: () => set({ _hydrated: true }),
    }),
    {
      name: "smart-causacion-auth",
      onRehydrateStorage: () => (state) => {
        state?._setHydrated();
      },
    }
  )
);
