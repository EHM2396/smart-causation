// Orden cronológico del borrador (lib/orden-documentos.ts).
// Corre con `npm test` (node --test). Sin dependencias: Node ejecuta el .ts directo.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  compararDocumentos,
  fechaEmisionKey,
  ordenarPorFechaEmision,
  reordenarBorrador,
} from "../src/lib/orden-documentos.ts";

const doc = (numero_dian, fecha, extra = {}) => ({ numero_dian, fecha, items: [], ...extra });
const numeros = (lista) => lista.map((f) => f.numero_dian);

test("la fecha de emisión acepta DD/MM/YYYY y YYYY-MM-DD; inválida va al final", () => {
  assert.equal(fechaEmisionKey("03/08/2026"), 20260803);
  assert.equal(fechaEmisionKey("2026-08-03"), 20260803);
  assert.equal(fechaEmisionKey("sin fecha"), Number.POSITIVE_INFINITY);
});

test("Prueba 3: septiembre importado antes que agosto → agosto queda primero", () => {
  const incorporadas = [doc("FE20", "10/09/2026"), doc("FE21", "12/09/2026"), doc("FE7", "03/08/2026")];
  assert.deepEqual(numeros(ordenarPorFechaEmision(incorporadas)), ["FE7", "FE20", "FE21"]);
});

test("mismo día: factura antes que su nota, luego prefijo y consecutivo numérico", () => {
  const incorporadas = [
    doc("NC3", "20/08/2026", { tipo_documento: "nota_credito" }),
    doc("FE10", "20/08/2026"),
    doc("FE9", "20/08/2026"),
    doc("FC2", "20/08/2026"),
  ];
  assert.deepEqual(numeros(ordenarPorFechaEmision(incorporadas)), ["FC2", "FE9", "FE10", "NC3"]);
});

test("el consecutivo solo se lee: ceros a la izquierda y números largos", () => {
  assert.ok(compararDocumentos(doc("FE0009", "01/01/2026"), doc("FE10", "01/01/2026")) < 0);
  assert.ok(compararDocumentos(doc("SETP990000000000000009", "01/01/2026"), doc("SETP990000000000000010", "01/01/2026")) < 0);
  const lista = [doc("FE0012", "01/01/2026")];
  assert.equal(ordenarPorFechaEmision(lista)[0].numero_dian, "FE0012");
});

test("reordenar el borrador mueve sugerencias y configuración con cada factura", () => {
  const sSep = { cuenta: "41353501" };
  const sAgo0 = { cuenta: "41552001" };
  const sAgo1 = { cuenta: "41552002" };
  const borrador = {
    facturas: [doc("FE20", "10/09/2026"), doc("FE7", "03/08/2026")],
    suggestions: { "0_0": sSep, "1_0": sAgo0, "1_1": sAgo1 },
    paso2: {
      facturaCount: 2,
      cuentaPago: { 0: "130505-sep", 1: "130505-ago" },
      cuentaGastoItem: { "0_0": "g-sep", "1_1": "g-ago" },
      verificadas: { 1: true },
      baseOverride: {},
    },
  };
  const r = reordenarBorrador(borrador);

  assert.deepEqual(numeros(r.facturas), ["FE7", "FE20"]);
  assert.deepEqual(r.suggestions, { "1_0": sSep, "0_0": sAgo0, "0_1": sAgo1 });
  assert.deepEqual(r.paso2.cuentaPago, { 0: "130505-ago", 1: "130505-sep" });
  assert.deepEqual(r.paso2.cuentaGastoItem, { "1_0": "g-sep", "0_1": "g-ago" });
  assert.deepEqual(r.paso2.verificadas, { 0: true });
  assert.equal(r.paso2.facturaCount, 2);
});

test("un borrador ya ordenado no se toca", () => {
  const borrador = { facturas: [doc("FE7", "03/08/2026"), doc("FE20", "10/09/2026")], suggestions: {}, paso2: null };
  assert.equal(reordenarBorrador(borrador), borrador);
});

test("las claves de facturas inexistentes se descartan al reordenar", () => {
  const borrador = {
    facturas: [doc("FE20", "10/09/2026"), doc("FE7", "03/08/2026")],
    suggestions: { "0_0": { cuenta: "a" }, "5_0": { cuenta: "huérfana" } },
    paso2: null,
  };
  assert.deepEqual(Object.keys(reordenarBorrador(borrador).suggestions), ["1_0"]);
});
