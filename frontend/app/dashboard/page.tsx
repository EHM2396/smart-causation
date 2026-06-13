import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  // Modo dev: saltar validaciones de Supabase
  const devBypass = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true";

  let profileNombre: string | null = null;

  if (!devBypass) {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) redirect("/login");

    const { data: profile } = await supabase
      .from("profiles")
      .select("organization_id, nombre")
      .eq("id", user.id)
      .single();

    if (!profile?.organization_id) redirect("/onboarding");
    profileNombre = profile?.nombre ?? null;
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">
          Hola{profileNombre ? `, ${profileNombre}` : ""} 👋
        </h1>
        <p className="text-gray-400 mb-8">
          Tu plataforma de causación contable inteligente
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href="/causacion"
            className="block p-6 bg-gray-900 border border-gray-800 rounded-lg hover:border-blue-600 transition-colors"
          >
            <h2 className="text-xl font-semibold mb-1">📄 Nueva Causación</h2>
            <p className="text-gray-400 text-sm">
              Carga un archivo DIAN y genera tu importación SIIGO
            </p>
          </a>

          <a
            href="/historial"
            className="block p-6 bg-gray-900 border border-gray-800 rounded-lg hover:border-blue-600 transition-colors"
          >
            <h2 className="text-xl font-semibold mb-1">🗂️ Historial</h2>
            <p className="text-gray-400 text-sm">
              Facturas causadas anteriormente
            </p>
          </a>

          <a
            href="/catalogos/cuentas"
            className="block p-6 bg-gray-900 border border-gray-800 rounded-lg hover:border-blue-600 transition-colors"
          >
            <h2 className="text-xl font-semibold mb-1">📚 Catálogos</h2>
            <p className="text-gray-400 text-sm">
              Plan de cuentas PUC, impuestos y comprobantes
            </p>
          </a>

          <a
            href="/catalogos/cuentas"
            className="block p-6 bg-gray-900 border border-gray-800 rounded-lg hover:border-blue-600 transition-colors"
          >
            <h2 className="text-xl font-semibold mb-1">🤖 Control IA</h2>
            <p className="text-gray-400 text-sm">
              Gestiona la asistencia IA por proveedor
            </p>
          </a>
        </div>
      </div>
    </main>
  );
}
