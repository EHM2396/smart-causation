"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const schema = z.object({
  nombre_organizacion: z
    .string()
    .min(3, "Mínimo 3 caracteres")
    .max(100, "Máximo 100 caracteres"),
});
type FormData = z.infer<typeof schema>;

export default function OnboardingPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setLoading(true);
    setError(null);
    try {
      await api.post("/auth/setup-organization", data);
      router.push("/dashboard");
      router.refresh();
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "No se pudo crear la organización. Intenta de nuevo.";
      if (msg.includes("ya tiene una organización")) {
        router.push("/dashboard");
        return;
      }
      setError(msg);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 p-4">
      <Card className="w-full max-w-md bg-gray-900 border-gray-800">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl text-white">Bienvenido 👋</CardTitle>
          <CardDescription className="text-gray-400">
            Cuéntanos el nombre de tu despacho o empresa contable para
            configurar tu espacio de trabajo.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="nombre_organizacion" className="text-gray-300">
                Nombre del despacho / empresa
              </Label>
              <Input
                id="nombre_organizacion"
                placeholder="ej. Contadores Pérez & Asociados"
                className="bg-gray-800 border-gray-700 text-white"
                {...register("nombre_organizacion")}
              />
              {errors.nombre_organizacion && (
                <p className="text-red-400 text-xs">
                  {errors.nombre_organizacion.message}
                </p>
              )}
            </div>

            {error && (
              <div className="bg-red-950 border border-red-800 rounded p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700"
              disabled={loading}
            >
              {loading ? "Configurando..." : "Empezar a usar la plataforma →"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
