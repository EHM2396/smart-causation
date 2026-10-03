// Cuenta contable del IVA según la NATURALEZA del documento:
//
//   compra  factura → IVA descontable           (cta_compras del impuesto)
//   compra  NC      → IVA por devoluciones en compras (PUC 2408, por tarifa)
//   venta   factura → IVA GENERADO              (cta_ventas; si falta, la cuenta
//                                                "IVA generado" del PUC 2408)
//   venta   NC      → REVERSA del IVA generado: cta_dev_ventas → cuenta de IVA
//                     por devoluciones en VENTAS del PUC → la propia cuenta de IVA
//                     generado (al débito disminuye el IVA generado)
//
// Nunca cruza compras con ventas: una venta no toma una cuenta de IVA
// descontable de compras, ni una NC de venta la de devoluciones en compras. Y la
// búsqueda por nombre se limita a la 2408 (IVA por pagar): antes, una NC de
// venta podía terminar con "Devoluciones en ventas" (4175, un ingreso) o con
// "IVA devolución en compras" como cuenta del IVA.
//
// Módulo sin dependencias, para poder probarlo con `node --test`.

export interface CuentaPUC {
  codigo: string;
  nombre?: string | null;
}

export interface ImpuestoIva {
  tarifa: number | null;
  cta_compras: string | null;
  cta_ventas: string | null;
  cta_dev_ventas: string | null;
}

const PREFIJO_IVA = "2408";

const norm = (s: string | null | undefined) =>
  (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Cuenta de IVA (2408) cuyo nombre tiene TODAS las palabras de `incluye` y
 * NINGUNA de `excluye`; entre ellas prefiere la que menciona la tarifa. */
export function buscarCuentaIva(
  puc: CuentaPUC[],
  tarifa: number | null | undefined,
  incluye: string[],
  excluye: string[] = [],
): string {
  const candidatas = puc.filter((c) => {
    if (!String(c.codigo ?? "").startsWith(PREFIJO_IVA)) return false;
    const n = norm(c.nombre);
    return incluye.every((p) => n.includes(p)) && !excluye.some((p) => n.includes(p));
  });
  if (!candidatas.length) return "";
  if (tarifa) {
    // "19" no debe coincidir con "119" ni "5" con "15".
    const pct = new RegExp(`(^|\\D)${Math.round(tarifa)}(\\D|$)`);
    const conTarifa = candidatas.find((c) => pct.test(norm(c.nombre)));
    if (conTarifa) return conTarifa.codigo;
  }
  return candidatas[0].codigo;
}

const ivaGenerado = (puc: CuentaPUC[], tarifa: number | null | undefined) =>
  buscarCuentaIva(puc, tarifa, ["generad"], ["devoluc", "descontab", "compra"]);

/** Cuenta de IVA por defecto para un impuesto en el módulo actual. "" = no se
 * pudo determinar (el contador la elige). */
export function cuentaIvaPorDefecto(
  imp: ImpuestoIva | null | undefined,
  modo: { esVenta: boolean; esNC: boolean },
  puc: CuentaPUC[],
): string {
  if (!imp) return "";
  const tarifa = imp.tarifa ?? 0;
  if (modo.esVenta) {
    if (modo.esNC) {
      return imp.cta_dev_ventas
        || buscarCuentaIva(puc, tarifa, ["devoluc", "venta"], ["compra"])
        || imp.cta_ventas
        || ivaGenerado(puc, tarifa)
        || "";
    }
    return imp.cta_ventas || ivaGenerado(puc, tarifa) || "";
  }
  if (modo.esNC) {
    if (!tarifa) return "";
    return buscarCuentaIva(puc, tarifa, ["devoluc", "compra"], ["venta"])
      || buscarCuentaIva(puc, tarifa, ["devoluc"], ["venta"]);
  }
  return imp.cta_compras ?? "";
}
