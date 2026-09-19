"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Clock, AlertTriangle } from "lucide-react";

/** Banner de estado de la cuenta de prueba (Free). No aparece en cuentas de pago. */
export function TrialBanner() {
  const { data } = useQuery({ queryKey: ["consumo-causacion"], queryFn: api.consumoCausacion, retry: false, staleTime: 60_000 });
  if (!data?.prueba) return null;

  const dias = data.dias_restantes ?? 0;
  const usadas = data.usadas_mes ?? 0;
  const cupo = data.cupo_mes ?? 0;
  const restantes = data.restantes ?? 0;
  const vencida = !!data.vencida || restantes <= 0 || dias < 0;

  const color = vencida ? "var(--error-text)" : (restantes <= 10 || dias <= 3) ? "var(--warning-text)" : "var(--info-text)";
  const bg = vencida ? "var(--error-bg)" : (restantes <= 10 || dias <= 3) ? "var(--warning-bg)" : "var(--info-bg)";
  const border = vencida ? "var(--error-border)" : (restantes <= 10 || dias <= 3) ? "var(--warning-border)" : "var(--info-border)";

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-sm lg:px-8"
      style={{ backgroundColor: bg, borderBottom: `1px solid ${border}`, color }}>
      {vencida ? <AlertTriangle className="h-4 w-4 shrink-0" /> : <Clock className="h-4 w-4 shrink-0" />}
      {vencida ? (
        <span className="font-medium">Tu prueba gratuita terminó. Adquiere un plan para seguir causando.</span>
      ) : (
        <>
          <span className="font-semibold">Prueba gratuita</span>
          <span>·</span>
          <span><strong>{usadas}</strong> / {cupo} causaciones</span>
          <span>·</span>
          <span>{dias === 0 ? "vence hoy" : `${dias} día${dias !== 1 ? "s" : ""} restante${dias !== 1 ? "s" : ""}`}</span>
        </>
      )}
    </div>
  );
}
