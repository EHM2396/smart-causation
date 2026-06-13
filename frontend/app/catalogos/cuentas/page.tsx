"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Tab = "impuestos" | "puc" | "tipos" | "ia";

interface Impuesto { cod: string; porcentaje: number; naturaleza?: string; cuenta_debito?: string; cuenta_credito?: string; }
interface Cuenta { codigo: string; nombre: string; fiscal?: boolean; }
interface TipoComp { codigo: string; titulo: string; }
interface Regla { id: number; patron: string; cuenta_destino: string; prioridad: number; activa: boolean; descripcion?: string; }

export default function CatalogosPage() {
  const [tab, setTab] = useState<Tab>("impuestos");
  const [impuestos, setImpuestos] = useState<Impuesto[]>([]);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [tipos, setTipos] = useState<TipoComp[]>([]);
  const [reglas, setReglas] = useState<Regla[]>([]);
  const [loading, setLoading] = useState(false);
  const [busqueda, setBusqueda] = useState("");

  useEffect(() => {
    setLoading(true);
    setBusqueda("");
    if (tab === "impuestos") {
      api.get<Impuesto[]>("/impuestos/").then(r => setImpuestos(r.data)).finally(() => setLoading(false));
    } else if (tab === "puc") {
      api.get<Cuenta[]>("/cuentas/gasto").then(r => setCuentas(r.data)).finally(() => setLoading(false));
    } else if (tab === "tipos") {
      api.get<TipoComp[]>("/tipos-comprobante/").then(r => setTipos(r.data)).finally(() => setLoading(false));
    } else if (tab === "ia") {
      api.get<Regla[]>("/aprendizaje/reglas?solo_activas=false").then(r => setReglas(r.data)).finally(() => setLoading(false));
    }
  }, [tab]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "impuestos", label: "Códigos de Impuesto" },
    { key: "puc", label: "Plan de Cuentas PUC" },
    { key: "tipos", label: "Tipos de Comprobante" },
    { key: "ia", label: "Control IA" },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="border-b border-gray-800 px-8 py-3 flex items-center gap-4">
        <Link href="/dashboard" className="text-gray-400 hover:text-white text-sm transition-colors">← Dashboard</Link>
        <span className="text-gray-700">|</span>
        <h1 className="font-semibold">Catálogos base</h1>
      </div>

      <div className="max-w-6xl mx-auto p-8">
        <p className="text-gray-500 text-sm mb-5">Los registros existentes son de solo lectura. Usa los formularios para agregar nuevos registros.</p>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-800 mb-6">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key ? "border-blue-500 text-blue-400" : "border-transparent text-gray-400 hover:text-white"
              }`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Búsqueda */}
        <div className="mb-4">
          <input type="text" value={busqueda} onChange={e => setBusqueda(e.target.value)}
            placeholder="Buscar..."
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm w-72 focus:outline-none focus:border-blue-500" />
        </div>

        {loading && <p className="text-gray-500 text-sm py-8 text-center">Cargando...</p>}

        {/* IMPUESTOS */}
        {!loading && tab === "impuestos" && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                <th className="text-left px-5 py-3">Código</th>
                <th className="text-right px-5 py-3">%</th>
                <th className="text-left px-5 py-3">Cta. Débito</th>
                <th className="text-left px-5 py-3">Cta. Crédito</th>
                <th className="text-left px-5 py-3">Tipo</th>
              </tr></thead>
              <tbody>
                {impuestos
                  .filter(x => !busqueda || x.cod.includes(busqueda) || (x.naturaleza ?? "").toLowerCase().includes(busqueda.toLowerCase()))
                  .map((imp, i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-5 py-2.5 font-mono text-blue-400">{imp.cod}</td>
                    <td className="px-5 py-2.5 text-right">{imp.porcentaje}</td>
                    <td className="px-5 py-2.5 font-mono text-gray-400">{imp.cuenta_debito || "—"}</td>
                    <td className="px-5 py-2.5 font-mono text-gray-400">{imp.cuenta_credito || "—"}</td>
                    <td className="px-5 py-2.5 text-gray-300">{imp.naturaleza || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* PUC */}
        {!loading && tab === "puc" && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                <th className="text-left px-5 py-3">Código</th>
                <th className="text-left px-5 py-3">Nombre</th>
                <th className="text-left px-5 py-3">Fiscal</th>
              </tr></thead>
              <tbody>
                {cuentas
                  .filter(x => !busqueda || x.codigo.includes(busqueda) || x.nombre.toLowerCase().includes(busqueda.toLowerCase()))
                  .map((c, i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-5 py-2.5 font-mono text-blue-400">{c.codigo}</td>
                    <td className="px-5 py-2.5">{c.nombre}</td>
                    <td className="px-5 py-2.5">{c.fiscal ? <span className="text-yellow-400 text-xs">Fiscal</span> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-5 py-2 border-t border-gray-800 text-xs text-gray-600">{cuentas.length} cuentas</div>
          </div>
        )}

        {/* TIPOS */}
        {!loading && tab === "tipos" && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                <th className="text-left px-5 py-3">Código</th>
                <th className="text-left px-5 py-3">Título</th>
              </tr></thead>
              <tbody>
                {tipos
                  .filter(x => !busqueda || x.codigo.includes(busqueda) || x.titulo.toLowerCase().includes(busqueda.toLowerCase()))
                  .map((t, i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-5 py-2.5 font-mono text-blue-400">{t.codigo}</td>
                    <td className="px-5 py-2.5">{t.titulo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* CONTROL IA */}
        {!loading && tab === "ia" && (
          <div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                  <th className="text-left px-5 py-3">Patrón</th>
                  <th className="text-left px-5 py-3">Cuenta destino</th>
                  <th className="text-right px-5 py-3">Prioridad</th>
                  <th className="text-left px-5 py-3">Estado</th>
                  <th className="text-left px-5 py-3">Descripción</th>
                </tr></thead>
                <tbody>
                  {reglas.length === 0
                    ? <tr><td colSpan={5} className="px-5 py-8 text-center text-gray-500">No hay reglas de clasificación IA configuradas.</td></tr>
                    : reglas
                        .filter(x => !busqueda || x.patron.toLowerCase().includes(busqueda.toLowerCase()) || x.cuenta_destino.includes(busqueda))
                        .map((r, i) => (
                        <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                          <td className="px-5 py-2.5 font-mono text-sm">{r.patron}</td>
                          <td className="px-5 py-2.5 font-mono text-blue-400">{r.cuenta_destino}</td>
                          <td className="px-5 py-2.5 text-right">{r.prioridad}</td>
                          <td className="px-5 py-2.5">
                            {r.activa
                              ? <span className="text-xs bg-green-900 text-green-300 px-2 py-0.5 rounded-full">Activa</span>
                              : <span className="text-xs bg-gray-800 text-gray-500 px-2 py-0.5 rounded-full">Inactiva</span>}
                          </td>
                          <td className="px-5 py-2.5 text-gray-400 text-xs">{r.descripcion || "—"}</td>
                        </tr>
                      ))
                  }
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-xs text-gray-600">Las reglas de clasificación permiten que la IA mapee automáticamente cuentas de gasto según palabras clave en la descripción del ítem.</p>
          </div>
        )}
      </div>
    </div>
  );
}

