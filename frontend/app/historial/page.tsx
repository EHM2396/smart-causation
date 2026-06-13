"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface FacturaCausada {
  consecutivo: number;
  numero_dian: string;
  razon_social: string;
  fecha_factura: string;
}

export default function HistorialPage() {
  const [facturas, setFacturas] = useState<FacturaCausada[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busqueda, setBusqueda] = useState("");

  useEffect(() => {
    api.get<FacturaCausada[]>("/causacion/historial")
      .then(r => setFacturas(r.data))
      .catch(() => setError("No se pudo cargar el historial"))
      .finally(() => setLoading(false));
  }, []);

  const filtradas = facturas.filter(f =>
    !busqueda ||
    f.numero_dian?.toLowerCase().includes(busqueda.toLowerCase()) ||
    f.razon_social?.toLowerCase().includes(busqueda.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="border-b border-gray-800 px-8 py-4 flex items-center gap-4">
        <Link href="/dashboard" className="text-gray-400 hover:text-white transition-colors text-sm">← Dashboard</Link>
        <h1 className="text-xl font-semibold">Historial de Causaciones</h1>
      </div>

      <div className="max-w-5xl mx-auto p-8">
        <div className="flex items-center justify-between mb-6 gap-4">
          <input
            type="text"
            placeholder="Buscar por número DIAN o proveedor..."
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm w-80 focus:outline-none focus:border-blue-500"
          />
          <Link href="/causacion" className="px-5 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">
            + Nueva causación
          </Link>
        </div>

        {loading && <p className="text-gray-500 text-center py-12">Cargando historial...</p>}
        {error && <p className="text-red-400 text-center py-12">{error}</p>}

        {!loading && !error && (
          filtradas.length === 0 ? (
            <div className="text-center py-16 text-gray-500">
              <p className="text-lg">No hay facturas causadas aún</p>
              <p className="text-sm mt-2">Las facturas procesadas aparecerán aquí</p>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase">
                    <th className="text-left px-6 py-3">Consecutivo</th>
                    <th className="text-left px-6 py-3">Número DIAN</th>
                    <th className="text-left px-6 py-3">Proveedor</th>
                    <th className="text-left px-6 py-3">Fecha factura</th>
                  </tr>
                </thead>
                <tbody>
                  {filtradas.map((f, i) => (
                    <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-3 font-mono text-blue-400">{f.consecutivo}</td>
                      <td className="px-6 py-3 font-mono text-gray-300">{f.numero_dian}</td>
                      <td className="px-6 py-3 text-gray-200">{f.razon_social}</td>
                      <td className="px-6 py-3 text-gray-400">{f.fecha_factura}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-6 py-3 border-t border-gray-800 text-xs text-gray-600">
                {filtradas.length} factura(s)
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}

