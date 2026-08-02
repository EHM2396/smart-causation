import Image from "next/image";

/**
 * Logo de marca con variante clara y oscura.
 *
 * El tema se resuelve en CSS (`dark:` = html[data-theme="dark"]), no en JS,
 * para que el logo correcto ya esté pintado en el primer frame y no haya
 * parpadeo al hidratar.
 *
 * - `completo`: logo horizontal compacto, el mismo del sidebar.
 * - `login`:    versión grande para las pantallas de acceso.
 * - `impresion`: solo la versión negra, para PDF sobre papel blanco.
 */
const VARIANTES = {
  completo: {
    claro: "/brand/Logo-completo-negro.webp",
    oscuro: "/brand/Logo-blanco.webp",
    ancho: 120,
    alto: 36,
  },
  login: {
    claro: "/brand/Logo inicio sesion.png",
    oscuro: "/brand/Logo inicio sesion blanco.png",
    ancho: 160,
    alto: 64,
  },
} as const;

export function LogoCiolix({
  variante = "completo",
  ancho,
  alto,
  priority = false,
}: {
  variante?: keyof typeof VARIANTES;
  ancho?: number;
  alto?: number;
  priority?: boolean;
}) {
  const v = VARIANTES[variante];
  const w = ancho ?? v.ancho;
  const h = alto ?? v.alto;
  const estilo = {
    objectFit: "contain" as const,
    width: "auto",
    height: "auto",
    maxWidth: `${w}px`,
    maxHeight: `${h}px`,
  };

  return (
    <>
      <Image
        src={v.claro}
        alt="Ciolix"
        width={w}
        height={h}
        className="block dark:hidden"
        style={estilo}
        priority={priority}
      />
      <Image
        src={v.oscuro}
        alt="Ciolix"
        width={w}
        height={h}
        className="hidden dark:block"
        style={estilo}
        priority={priority}
      />
    </>
  );
}

/**
 * Logo para el encabezado impreso de los documentos legales.
 * Siempre la versión negra: la impresión fuerza fondo blanco, así que la
 * versión clara del logo saldría invisible.
 */
export function LogoCiolixImpresion() {
  return (
    <Image
      src="/brand/Logo-completo-negro.webp"
      alt="Ciolix"
      width={120}
      height={36}
      style={{ objectFit: "contain", width: "auto", height: "auto", maxHeight: "32px" }}
    />
  );
}
