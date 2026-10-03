// Cuenta de IVA según la naturaleza del documento (lib/cuenta-iva.ts).
// Corre con `npm test` (node --test). Sin dependencias: Node ejecuta el .ts directo.
import { test } from "node:test";
import assert from "node:assert/strict";
import { buscarCuentaIva, cuentaIvaPorDefecto } from "../src/lib/cuenta-iva.ts";

const PUC = [
  { codigo: "24080101", nombre: "IVA generado 19%" },
  { codigo: "24080105", nombre: "IVA generado 5%" },
  { codigo: "24081001", nombre: "IVA descontable 19%" },
  { codigo: "24082001", nombre: "IVA por devoluciones en compras 19%" },
  { codigo: "24082501", nombre: "IVA por devoluciones en ventas 19%" },
  { codigo: "41750501", nombre: "Devoluciones en ventas" },
];
const IVA19 = { tarifa: 19, cta_compras: "24081001", cta_ventas: null, cta_dev_ventas: null };
const VENTA = { esVenta: true, esNC: false };
const NC_VENTA = { esVenta: true, esNC: true };
const COMPRA = { esVenta: false, esNC: false };
const NC_COMPRA = { esVenta: false, esNC: true };

test("compra → IVA descontable del catálogo (sin cambios)", () => {
  assert.equal(cuentaIvaPorDefecto(IVA19, COMPRA, PUC), "24081001");
});

test("venta → IVA generado del catálogo de impuestos", () => {
  assert.equal(cuentaIvaPorDefecto({ ...IVA19, cta_ventas: "24080101" }, VENTA, PUC), "24080101");
});

test("venta sin cuenta en el catálogo → IVA generado del PUC, nunca el descontable", () => {
  assert.equal(cuentaIvaPorDefecto(IVA19, VENTA, PUC), "24080101");
  assert.equal(cuentaIvaPorDefecto({ ...IVA19, tarifa: 5 }, VENTA, PUC), "24080105");
});

test("Prueba 2: NC de venta → IVA por devoluciones en VENTAS, nunca el de compras ni un ingreso", () => {
  const cuenta = cuentaIvaPorDefecto(IVA19, NC_VENTA, PUC);
  assert.equal(cuenta, "24082501");
});

test("NC de venta usa primero la cuenta de devolución configurada en el impuesto", () => {
  assert.equal(cuentaIvaPorDefecto({ ...IVA19, cta_dev_ventas: "24089999" }, NC_VENTA, PUC), "24089999");
});

test("NC de venta sin cuenta de devolución en ventas → disminuye el IVA generado", () => {
  const sinDevVentas = PUC.filter((c) => c.codigo !== "24082501");
  // Con el IVA generado del catálogo de impuestos…
  assert.equal(cuentaIvaPorDefecto({ ...IVA19, cta_ventas: "24080101" }, NC_VENTA, sinDevVentas), "24080101");
  // …o, si tampoco está, el "IVA generado" del PUC. Jamás devoluciones en compras ni 4175.
  const cuenta = cuentaIvaPorDefecto(IVA19, NC_VENTA, sinDevVentas);
  assert.equal(cuenta, "24080101");
});

test("NC de compra → IVA por devoluciones en compras, nunca el de ventas", () => {
  assert.equal(cuentaIvaPorDefecto(IVA19, NC_COMPRA, PUC), "24082001");
});

test("la búsqueda por nombre solo mira cuentas de IVA (2408)", () => {
  assert.equal(buscarCuentaIva(PUC, 19, ["devoluc", "venta"]), "24082501");
  assert.equal(buscarCuentaIva([{ codigo: "41750501", nombre: "Devoluciones en ventas 19" }], 19, ["devoluc"]), "");
});

test("la tarifa 5 no coincide con 15 ni 19 con 119", () => {
  const puc = [
    { codigo: "24080115", nombre: "IVA generado 15%" },
    { codigo: "24080105", nombre: "IVA generado 5%" },
  ];
  assert.equal(buscarCuentaIva(puc, 5, ["generad"]), "24080105");
});

test("sin impuesto no hay cuenta", () => {
  assert.equal(cuentaIvaPorDefecto(null, VENTA, PUC), "");
});
