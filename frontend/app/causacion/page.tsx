"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface CuentaOpcion { codigo: string; nombre: string; }
interface Impuesto { cod: string; porcentaje: number; nombre?: string; naturaleza?: string; cuenta_debito?: string; cuenta_credito?: string; }
interface TipoComp { codigo: string; titulo: string; }
interface ItemFactura { descripcion: string; base: number; cod_impuesto?: string; porcentaje?: number; valor_impuesto?: number; }
interface Factura { numero_dian: string; razon_social: string; nit: string; fecha: string; total: number; tipo_proveedor?: string; items: ItemFactura[]; _archivo?: string; }
interface MapeoItem { descripcion: string; cuenta_gasto: string; cod_impuesto: string; porcentaje: number; cuenta_impuesto_deb: string; cuenta_impuesto_cre: string; base: number; valor_impuesto: number; cuenta_pago: string; }
interface FacturaHist { consecutivo: number; numero_dian: string; razon_social: string; fecha_factura: string; }

export default function CausacionPage() {
  const [paso, setPaso] = useState<1 | 2 | 3 | 4>(1);
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [cuentasGasto, setCuentasGasto] = useState<CuentaOpcion[]>([]);
  const [cuentasPago, setCuentasPago] = useState<CuentaOpcion[]>([]);
  const [impuestos, setImpuestos] = useState<Impuesto[]>([]);
  const [tiposComp, setTiposComp] = useState<TipoComp[]>([]);
  const [tipoComp, setTipoComp] = useState("12");
  const [centroCosto, setCentroCosto] = useState("");
  const [mapeos, setMapeos] = useState<MapeoItem[][]>([]);
  const [cuentasPagoFac, setCuentasPagoFac] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<{ consecutivo: number; numero_dian: string; archivo_nombre: string } | null>(null);
  const [historial, setHistorial] = useState<FacturaHist[]>([]);
  const [historialOpen, setHistorialOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Cargar tipos de comprobante e historial al montar
  useEffect(() => {
    api.get<TipoComp[]>("/tipos-comprobante/").then(r => {
      setTiposComp(r.data);
      if (r.data.length) setTipoComp(r.data[0].codigo);
    }).catch(() => {});
    api.get<FacturaHist[]>("/causacion/historial").then(r => setHistorial(r.data)).catch(() => {});
  }, []);

  const handleSubir = async () => {
    const files = fileRef.current?.files;
    if (!files || files.length === 0) return;
    setLoading(true); setError(null);
    const allFacturas: Factura[] = [];
    const errores: string[] = [];

    for (const file of Array.from(files)) {
      const fd = new FormData();
      fd.append("archivo", file);
      try {
        const res = await api.post<Factura[]>("/causacion/parsear", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        allFacturas.push(...res.data.map(f => ({ ...f, _archivo: file.name })));
      } catch (e: unknown) {
        errores.push(`${file.name}: ${(e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? String(e)}`);
      }
    }

    if (errores.length) setError(errores.join("\n"));
    if (allFacturas.length === 0) { setLoading(false); return; }

    const [cg, cp, imp] = await Promise.all([
      api.get<CuentaOpcion[]>("/cuentas/gasto"),
      api.get<CuentaOpcion[]>("/cuentas/pago"),
      api.get<Impuesto[]>("/impuestos/"),
    ]);
    setCuentasGasto(cg.data); setCuentasPago(cp.data); setImpuestos(imp.data);
    setFacturas(allFacturas);

    const mapeoInit: MapeoItem[][] = allFacturas.map(fac =>
      fac.items.map(item => ({
        descripcion: item.descripcion, cuenta_gasto: "", cod_impuesto: item.cod_impuesto ?? "",
        porcentaje: item.porcentaje ?? 0, cuenta_impuesto_deb: "", cuenta_impuesto_cre: "",
        base: item.base, valor_impuesto: item.valor_impuesto ?? 0, cuenta_pago: "",
      }))
    );
    for (let i = 0; i < allFacturas.length; i++) {
      for (let j = 0; j < allFacturas[i].items.length; j++) {
        try {
          const sug = await api.post<{ cuenta_sugerida: string | null }>("/causacion/sugerir-cuenta", {
            nit: allFacturas[i].nit, descripcion: allFacturas[i].items[j].descripcion,
          });
          if (sug.data.cuenta_sugerida) mapeoInit[i][j].cuenta_gasto = sug.data.cuenta_sugerida;
        } catch { /* sin sugerencia */ }
      }
    }
    setMapeos(mapeoInit);
    setCuentasPagoFac(allFacturas.map(() => ""));
    setLoading(false); setPaso(2);
  };

  const handleGenerar = async () => {
    setLoading(true); setError(null);
    try {
      const res = await api.post("/causacion/generar", {
        factura: facturas[0],
        mapeos_confirmados: mapeos[0].map(m => ({ ...m, cuenta_pago: cuentasPagoFac[0] || m.cuenta_pago })),
        tipo_comprobante: tipoComp, centro_costo: centroCosto, prefijo: "FC",
      });
      setResultado(res.data);
      api.get<FacturaHist[]>("/causacion/historial").then(r => setHistorial(r.data)).catch(() => {});
      setPaso(4);
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Error al generar");
    }
    setLoading(false);
  };

  const handleDescargar = async () => {
    if (!resultado) return; setLoading(true);
    try {
      const res = await api.post("/causacion/generar-descarga", {
        factura: facturas[0],
        mapeos_confirmados: mapeos[0].map(m => ({ ...m, cuenta_pago: cuentasPagoFac[0] || m.cuenta_pago })),
        tipo_comprobante: tipoComp, centro_costo: centroCosto, prefijo: "FC",
      }, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a"); a.href = url; a.download = resultado.archivo_nombre; a.click();
      URL.revokeObjectURL(url);
    } catch { setError("Error al descargar el archivo"); }
    setLoading(false);
  };

  const updateMapeo = (i: number, j: number, field: keyof MapeoItem, value: string | number) => {
    setMapeos(prev => {
      const next = prev.map(fila => fila.map(m => ({ ...m })));
      (next[i][j] as Record<string, unknown>)[field] = value;
      // Si cambia el impuesto, actualizar cuentas automÃ¡ticamente
      if (field === "cod_impuesto") {
        const imp = impuestos.find(x => x.cod === value);
        if (imp) {
          next[i][j].porcentaje = imp.porcentaje;
          next[i][j].cuenta_impuesto_deb = imp.cuenta_debito ?? "";
          next[i][j].cuenta_impuesto_cre = imp.cuenta_credito ?? "";
        }
      }
      return next;
    });
  };

  // â”€â”€ Sidebar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const sidebar = (
    <aside className="w-64 shrink-0 border-r border-gray-800 p-5 space-y-5 bg-gray-900/40">
      <div>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">ConfiguraciÃ³n</h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Tipo de comprobante</label>
            <select value={tipoComp} onChange={e => setTipoComp(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm">
              {tiposComp.length
                ? tiposComp.map(t => <option key={t.codigo} value={t.codigo}>{t.codigo} - {t.titulo}</option>)
                : <option value="12">12 - Comprobante de egreso</option>}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Centro de costo</label>
            <input type="text" value={centroCosto} onChange={e => setCentroCosto(e.target.value)}
              placeholder="VacÃ­o si no aplica"
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm" />
          </div>
        </div>
      </div>

      <div className="border-t border-gray-800 pt-4">
        <button onClick={() => setHistorialOpen(v => !v)}
          className="w-full flex items-center justify-between text-sm text-gray-300 hover:text-white transition-colors">
          <span>Historial de facturas</span>
          <span className="text-gray-600">{historialOpen ? "â–²" : "â–¼"}</span>
        </button>
        {historialOpen && (
          <div className="mt-3 overflow-auto max-h-64">
            {historial.length === 0
              ? <p className="text-xs text-gray-600">No hay facturas causadas aÃºn.</p>
              : (
                <table className="w-full text-xs">
                  <thead><tr className="text-gray-500 border-b border-gray-700">
                    <th className="text-left pb-1">Consec.</th>
                    <th className="text-left pb-1">NÂ° DIAN</th>
                  </tr></thead>
                  <tbody>
                    {historial.map((f, i) => (
                      <tr key={i} className="border-b border-gray-800/50">
                        <td className="py-1 text-blue-400">{f.consecutivo}</td>
                        <td className="py-1 text-gray-400 truncate max-w-[100px]">{f.numero_dian}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
          </div>
        )}
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Top bar */}
      <div className="border-b border-gray-800 px-6 py-3 flex items-center gap-4">
        <Link href="/dashboard" className="text-gray-400 hover:text-white text-sm transition-colors">â† Dashboard</Link>
        <span className="text-gray-700">|</span>
        <h1 className="font-semibold">CausaciÃ³n SIIGO</h1>
        <div className="ml-auto flex items-center gap-2">
          {[1,2,3,4].map(n => (
            <div key={n} className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium border
              ${paso === n ? "bg-blue-600 border-blue-600" : paso > n ? "bg-green-600 border-green-600" : "border-gray-700 text-gray-500"}`}>
              {paso > n ? "âœ“" : n}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-1">
        {sidebar}

        <main className="flex-1 p-8 overflow-auto">
          {error && (
            <div className="mb-5 bg-red-950 border border-red-800 rounded-lg p-3">
              <pre className="text-red-400 text-sm whitespace-pre-wrap">{error}</pre>
            </div>
          )}

          {/* PASO 1 */}
          {paso === 1 && (
            <div>
              <h2 className="text-2xl font-bold mb-1">Paso 1 - Cargar facturas DIAN</h2>
              <p className="text-gray-400 text-sm mb-6">Sube el archivo xlsx exportado del portal DIAN. Puede contener mÃºltiples facturas.</p>
              <p className="text-sm text-gray-400 mb-2">Selecciona uno o varios archivos .xlsx</p>
              <label htmlFor="file-input"
                className="flex items-center gap-3 w-full border border-gray-700 rounded-lg px-5 py-4 cursor-pointer hover:border-blue-600 transition-colors bg-gray-900">
                <span className="text-blue-400 text-lg">â¬†</span>
                <span className="text-gray-400 text-sm">25MB per file Â· XLSX</span>
              </label>
              <input ref={fileRef} id="file-input" type="file" accept=".xlsx" multiple className="hidden" />
              <button onClick={handleSubir} disabled={loading}
                className="mt-5 px-7 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg font-medium text-sm transition-colors">
                {loading ? "Procesando..." : "Parsear facturas"}
              </button>
            </div>
          )}

          {/* PASO 2 */}
          {paso === 2 && facturas.length > 0 && (
            <div>
              <h2 className="text-2xl font-bold mb-1">Paso 2 - Revisar y confirmar cuentas</h2>
              <p className="text-gray-400 text-sm mb-5">{facturas.length} factura(s). Aprendido = del historial. Sugerido = del plan de cuentas. Manual = sin informaciÃ³n previa.</p>

              {facturas.map((fac, i) => (
                <div key={i} className="mb-5 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                  <div className="bg-gray-800/60 px-5 py-3 flex flex-wrap gap-5 text-xs text-gray-300">
                    <span><span className="text-gray-500">NÂ° DIAN:</span> <span className="font-mono">{fac.numero_dian}</span></span>
                    <span><span className="text-gray-500">Proveedor:</span> {fac.razon_social}</span>
                    <span><span className="text-gray-500">NIT:</span> {fac.nit}</span>
                    <span><span className="text-gray-500">Fecha:</span> {fac.fecha}</span>
                    <span className="ml-auto font-semibold text-green-400">${fac.total?.toLocaleString("es-CO")}</span>
                  </div>
                  <div className="p-5 space-y-4">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Cuenta de pago (activo/pasivo â€” buscar por cÃ³digo o nombre)</label>
                      <select value={cuentasPagoFac[i] || ""} onChange={e => { const n=[...cuentasPagoFac]; n[i]=e.target.value; setCuentasPagoFac(n); }}
                        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm">
                        <option value="">-- Seleccionar cuenta de pago --</option>
                        {cuentasPago.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} - {c.nombre}</option>)}
                      </select>
                    </div>
                    <div className="space-y-2">
                      {fac.items.map((item, j) => (
                        <div key={j} className="bg-gray-800 rounded-lg p-4">
                          <div className="flex justify-between items-start gap-3 mb-3">
                            <p className="text-sm font-medium">{item.descripcion}</p>
                            <div className="text-right shrink-0 text-xs">
                              <div className="text-gray-400">Base: <span className="text-white">${item.base?.toLocaleString("es-CO")}</span></div>
                              {item.valor_impuesto ? <div className="text-gray-400">Imp: <span className="text-yellow-400">${item.valor_impuesto.toLocaleString("es-CO")}</span></div> : null}
                            </div>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                              <label className="block text-xs text-gray-500 mb-1">
                                Cuenta gasto/costo
                                {mapeos[i]?.[j]?.cuenta_gasto && <span className="text-blue-400 ml-1">âœ“ {mapeos[i][j].cuenta_gasto}</span>}
                              </label>
                              <select value={mapeos[i]?.[j]?.cuenta_gasto || ""} onChange={e => updateMapeo(i, j, "cuenta_gasto", e.target.value)}
                                className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm">
                                <option value="">-- Seleccionar cuenta --</option>
                                {cuentasGasto.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} - {c.nombre}</option>)}
                              </select>
                            </div>
                            <div>
                              <label className="block text-xs text-gray-500 mb-1">CÃ³digo impuesto</label>
                              <select value={mapeos[i]?.[j]?.cod_impuesto || ""} onChange={e => updateMapeo(i, j, "cod_impuesto", e.target.value)}
                                className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm">
                                <option value="">Sin impuesto</option>
                                {impuestos.map(imp => <option key={imp.cod} value={imp.cod}>{imp.cod} â€” {imp.naturaleza ?? ""} {imp.porcentaje}%</option>)}
                              </select>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
              <div className="flex gap-3">
                <button onClick={() => setPaso(1)} className="px-5 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">â† Volver</button>
                <button onClick={() => setPaso(3)} className="px-7 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors">Validar partida doble â†’</button>
              </div>
            </div>
          )}

          {/* PASO 3 */}
          {paso === 3 && (
            <div>
              <h2 className="text-2xl font-bold mb-1">Paso 3 - Confirmar y generar</h2>
              <p className="text-gray-400 text-sm mb-5">Revisa el resumen antes de generar el archivo SIIGO.</p>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-5 text-sm space-y-2 max-w-md">
                <div className="flex justify-between"><span className="text-gray-400">Facturas</span><span>{facturas.length}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Total Ã­tems</span><span>{facturas.reduce((s,f)=>s+f.items.length,0)}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Tipo comprobante</span><span>{tipoComp}</span></div>
                {centroCosto && <div className="flex justify-between"><span className="text-gray-400">Centro de costo</span><span>{centroCosto}</span></div>}
                <div className="border-t border-gray-700 pt-2 flex justify-between font-semibold">
                  <span className="text-gray-400">Total</span>
                  <span className="text-green-400">${facturas.reduce((s,f)=>s+f.total,0).toLocaleString("es-CO")}</span>
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setPaso(2)} className="px-5 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">â† Revisar cuentas</button>
                <button onClick={handleGenerar} disabled={loading}
                  className="px-7 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
                  {loading ? "Generando..." : "âœ“ Generar importaciÃ³n SIIGO"}
                </button>
              </div>
            </div>
          )}

          {/* PASO 4 */}
          {paso === 4 && resultado && (
            <div className="py-8">
              <div className="text-5xl mb-4 text-center">âœ…</div>
              <h2 className="text-2xl font-bold mb-1 text-center">Â¡CausaciÃ³n generada!</h2>
              <p className="text-gray-400 text-sm text-center mb-6">El archivo estÃ¡ listo para importar en SIIGO.</p>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 max-w-sm mx-auto mb-6 text-sm space-y-2">
                <div className="flex justify-between"><span className="text-gray-400">Consecutivo SIIGO</span><span className="font-bold text-blue-400">{resultado.consecutivo}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">NÃºmero DIAN</span><span className="font-mono">{resultado.numero_dian}</span></div>
                <div className="flex justify-between"><span className="text-gray-400">Archivo</span><span className="text-green-400 text-xs">{resultado.archivo_nombre}</span></div>
              </div>
              <div className="flex gap-3 justify-center flex-wrap">
                <button onClick={handleDescargar} disabled={loading}
                  className="px-7 py-2.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg font-medium text-sm transition-colors">
                  {loading ? "Descargando..." : "â¬‡ Descargar importacion_SIIGO.xlsx"}
                </button>
                <button onClick={() => { setPaso(1); setFacturas([]); setResultado(null); setError(null); }}
                  className="px-5 py-2.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">Nueva causaciÃ³n</button>
                <Link href="/dashboard" className="px-5 py-2.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">Dashboard</Link>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
