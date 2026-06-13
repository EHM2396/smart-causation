import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#080810] text-white font-sans overflow-x-hidden">
      {/* ── Nav ─────────────────────────────────────────────────── */}
      <header className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-[#080810]/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-xs font-bold">
              SC
            </div>
            <span className="font-semibold tracking-tight text-sm">SmartCausación</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm text-gray-400">
            <a href="#como-funciona" className="hover:text-white transition-colors">Cómo funciona</a>
            <a href="#caracteristicas" className="hover:text-white transition-colors">Características</a>
            <a href="#precios" className="hover:text-white transition-colors">Precios</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm text-gray-400 hover:text-white transition-colors px-4 py-2"
            >
              Iniciar sesión
            </Link>
            <Link
              href="/register"
              className="text-sm bg-blue-600 hover:bg-blue-500 transition-colors px-4 py-2 rounded-lg font-medium"
            >
              Registrarse gratis
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────── */}
      <section className="relative pt-40 pb-32 px-6 text-center overflow-hidden">
        {/* Glow de fondo */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[500px] bg-blue-600/10 rounded-full blur-[120px]" />
          <div className="absolute top-1/3 left-1/3 w-[400px] h-[300px] bg-cyan-500/5 rounded-full blur-[80px]" />
        </div>

        <div className="relative max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-blue-950/60 border border-blue-800/50 text-blue-300 text-xs font-medium px-3 py-1.5 rounded-full mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            Inteligencia artificial aplicada a contabilidad colombiana
          </div>

          <h1 className="text-5xl md:text-7xl font-bold leading-[1.05] tracking-tight mb-6">
            Causación contable{" "}
            <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
              en segundos
            </span>
          </h1>

          <p className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Carga tu archivo DIAN, la IA lo interpreta y genera el archivo listo
            para importar en SIIGO. Sin digitación manual, sin errores.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/register"
              className="px-8 py-3.5 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold text-base transition-all hover:shadow-[0_0_30px_rgba(59,130,246,0.4)]"
            >
              Empezar gratis →
            </Link>
            <a
              href="#como-funciona"
              className="px-8 py-3.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl font-medium text-base transition-colors"
            >
              Ver cómo funciona
            </a>
          </div>
        </div>

        {/* Mockup terminal */}
        <div className="relative mt-20 max-w-3xl mx-auto">
          <div className="bg-[#0d0d1a] border border-white/10 rounded-2xl overflow-hidden shadow-2xl shadow-black/60">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5 bg-white/[0.02]">
              <div className="w-3 h-3 rounded-full bg-red-500/70" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
              <div className="w-3 h-3 rounded-full bg-green-500/70" />
              <span className="ml-3 text-xs text-gray-600 font-mono">smart-causacion — causacion.py</span>
            </div>
            <div className="p-6 font-mono text-sm text-left space-y-2">
              <div><span className="text-gray-600">$</span> <span className="text-blue-400">subir_factura</span> <span className="text-amber-300">FV_20240615_001.xml</span></div>
              <div className="text-gray-500">→ Analizando 47 ítems con IA...</div>
              <div className="text-gray-500">→ Mapeando cuentas PUC automáticamente...</div>
              <div className="text-green-400">✓ 47/47 ítems causados correctamente</div>
              <div className="text-gray-500">→ Generando archivo SIIGO...</div>
              <div className="text-cyan-400">✓ Archivo listo: <span className="underline">causacion_20240615.xlsx</span></div>
              <div className="mt-2 text-gray-600 text-xs">Tiempo total: 3.2s — Ahorro estimado: 45 min de trabajo manual</div>
            </div>
          </div>
          {/* Glow bajo el mockup */}
          <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 w-3/4 h-20 bg-blue-600/20 blur-3xl" />
        </div>
      </section>

      {/* ── Cómo funciona ────────────────────────────────────────── */}
      <section id="como-funciona" className="py-28 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Tres pasos. Listo.
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              De archivo DIAN a importación SIIGO sin tocar una sola celda de Excel.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                num: "01",
                title: "Carga la factura",
                desc: "Sube el XML o PDF de tu factura electrónica DIAN. También acepta archivos por lotes.",
                color: "from-blue-600 to-blue-400",
              },
              {
                num: "02",
                title: "La IA la interpreta",
                desc: "Nuestro modelo identifica ítems, impuestos, retenciones y los mapea automáticamente a tu plan de cuentas PUC.",
                color: "from-cyan-600 to-cyan-400",
              },
              {
                num: "03",
                title: "Descarga e importa",
                desc: "Obtén el archivo listo para importar en SIIGO. El sistema aprende con cada causación para ser cada vez más preciso.",
                color: "from-violet-600 to-violet-400",
              },
            ].map((step) => (
              <div
                key={step.num}
                className="bg-[#0d0d1a] border border-white/8 rounded-2xl p-7 hover:border-white/15 transition-colors"
              >
                <div
                  className={`text-4xl font-bold bg-gradient-to-r ${step.color} bg-clip-text text-transparent mb-4`}
                >
                  {step.num}
                </div>
                <h3 className="text-lg font-semibold mb-2">{step.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Características ──────────────────────────────────────── */}
      <section id="caracteristicas" className="py-28 px-6 bg-[#0a0a14]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Todo lo que necesita tu despacho
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              Construido para contadores colombianos que manejan múltiples clientes.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            {[
              {
                icon: "🧠",
                title: "IA que aprende de ti",
                desc: "Cada corrección que haces entrena el modelo. Con el tiempo, la tasa de acierto supera el 98% en tus proveedores habituales.",
              },
              {
                icon: "🏢",
                title: "Multi-empresa",
                desc: "Gestiona todos tus clientes desde una sola cuenta. Cada empresa tiene su propio catálogo de cuentas y configuración aislada.",
              },
              {
                icon: "📊",
                title: "Catálogo PUC integrado",
                desc: "Plan de cuentas PUC colombiano precargado. Mapea las cuentas de tus proveedores una vez y el sistema lo recuerda siempre.",
              },
              {
                icon: "🔒",
                title: "Datos seguros y aislados",
                desc: "Cada empresa opera en un espacio completamente separado. Tus datos nunca se mezclan con los de otros usuarios.",
              },
              {
                icon: "⚡",
                title: "Procesamiento por lotes",
                desc: "Carga decenas de facturas a la vez. La cola procesadora las trabaja en paralelo y te notifica cuando están listas.",
              },
              {
                icon: "📁",
                title: "Exportación SIIGO nativa",
                desc: "El archivo de salida sigue exactamente el formato que SIIGO espera. Sin ajustes manuales, importación en un clic.",
              },
            ].map((f) => (
              <div
                key={f.title}
                className="flex gap-5 p-6 bg-[#0d0d1a] border border-white/8 rounded-xl hover:border-white/15 transition-colors"
              >
                <div className="text-2xl mt-0.5 shrink-0">{f.icon}</div>
                <div>
                  <h3 className="font-semibold mb-1">{f.title}</h3>
                  <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Precios ──────────────────────────────────────────────── */}
      <section id="precios" className="py-28 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Precios simples y transparentes
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              Sin costos ocultos. Cambia o cancela cuando quieras.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 items-start">
            {/* Gratis */}
            <div className="bg-[#0d0d1a] border border-white/8 rounded-2xl p-7">
              <div className="text-sm text-gray-400 font-medium mb-1">Gratis</div>
              <div className="text-4xl font-bold mb-1">$0</div>
              <div className="text-gray-500 text-sm mb-6">Para siempre</div>
              <ul className="space-y-3 mb-8 text-sm text-gray-300">
                {["1 empresa", "Hasta 30 facturas/mes", "Catálogo PUC básico", "Exportación SIIGO"].map((item) => (
                  <li key={item} className="flex items-center gap-2">
                    <span className="text-green-400">✓</span> {item}
                  </li>
                ))}
                {["IA avanzada", "Soporte prioritario"].map((item) => (
                  <li key={item} className="flex items-center gap-2 opacity-40">
                    <span className="text-gray-600">✕</span> {item}
                  </li>
                ))}
              </ul>
              <Link
                href="/register"
                className="block text-center py-2.5 border border-white/15 rounded-lg text-sm hover:bg-white/5 transition-colors"
              >
                Empezar gratis
              </Link>
            </div>

            {/* Pro — destacado */}
            <div className="bg-gradient-to-b from-blue-950/80 to-[#0d0d1a] border border-blue-600/50 rounded-2xl p-7 relative shadow-[0_0_40px_rgba(59,130,246,0.15)]">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-xs font-semibold px-3 py-1 rounded-full">
                Más popular
              </div>
              <div className="text-sm text-blue-300 font-medium mb-1">Pro</div>
              <div className="flex items-end gap-1 mb-1">
                <span className="text-4xl font-bold">$99.000</span>
              </div>
              <div className="text-gray-500 text-sm mb-6">COP / mes por empresa</div>
              <ul className="space-y-3 mb-8 text-sm text-gray-300">
                {[
                  "Empresas ilimitadas",
                  "Facturas ilimitadas",
                  "IA avanzada con aprendizaje",
                  "Multi-usuario por empresa",
                  "Catálogos personalizados",
                  "Soporte por WhatsApp",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2">
                    <span className="text-blue-400">✓</span> {item}
                  </li>
                ))}
              </ul>
              <Link
                href="/register"
                className="block text-center py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-semibold transition-colors"
              >
                Probar 14 días gratis
              </Link>
            </div>

            {/* Empresa */}
            <div className="bg-[#0d0d1a] border border-white/8 rounded-2xl p-7">
              <div className="text-sm text-gray-400 font-medium mb-1">Empresa</div>
              <div className="text-4xl font-bold mb-1">A medida</div>
              <div className="text-gray-500 text-sm mb-6">Para grandes despachos</div>
              <ul className="space-y-3 mb-8 text-sm text-gray-300">
                {[
                  "Todo lo de Pro",
                  "Integración por API",
                  "Onboarding dedicado",
                  "SLA garantizado",
                  "Facturación en COP o USD",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2">
                    <span className="text-cyan-400">✓</span> {item}
                  </li>
                ))}
              </ul>
              <a
                href="mailto:hola@smartcausacion.co"
                className="block text-center py-2.5 border border-white/15 rounded-lg text-sm hover:bg-white/5 transition-colors"
              >
                Hablar con ventas
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA final ────────────────────────────────────────────── */}
      <section className="py-28 px-6 text-center relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-blue-600/10 blur-[100px]" />
        </div>
        <div className="relative max-w-2xl mx-auto">
          <h2 className="text-4xl md:text-5xl font-bold mb-5 leading-tight">
            Deja que la IA se encargue<br />de la causación
          </h2>
          <p className="text-gray-400 text-lg mb-10">
            Únete a los contadores que ya ahoran horas cada semana. Sin tarjeta de crédito.
          </p>
          <Link
            href="/register"
            className="inline-block px-10 py-4 bg-blue-600 hover:bg-blue-500 rounded-xl font-bold text-lg transition-all hover:shadow-[0_0_40px_rgba(59,130,246,0.5)]"
          >
            Crear cuenta gratis →
          </Link>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-[10px] font-bold text-white">
              SC
            </div>
            <span>SmartCausación</span>
          </div>
          <p>© 2025 SmartCausación. Hecho en Colombia 🇨🇴</p>
          <div className="flex gap-6">
            <a href="#" className="hover:text-gray-400 transition-colors">Privacidad</a>
            <a href="#" className="hover:text-gray-400 transition-colors">Términos</a>
            <a href="mailto:hola@smartcausacion.co" className="hover:text-gray-400 transition-colors">Contacto</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

