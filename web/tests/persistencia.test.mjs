import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
async function module(name) {
  const source = fs.readFileSync(
    new URL(`../lib/${name}.ts`, import.meta.url),
    "utf8",
  );
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
  });
  return import(
    "data:text/javascript;base64," + Buffer.from(outputText).toString("base64")
  );
}
const { restaurar } = await module("persistencia");
const { identidadSeleccion, gruposBoleto } = await module("selecciones");
const initial = {
  liga: "laliga",
  met: "goles",
  partidos: {},
  boleto: [],
  banca: 1000,
};
const leg = {
  partido: "A vs B",
  metrica: "Goles",
  mercado: "Total Over 2.5",
  prob: 0.6,
  cuota: 1.9,
  cal: "Buena",
  cls: "bue",
  lo: 0.4,
  hi: 0.7,
  push: 0,
  justa: 1.666,
  seleccion: {
    liga: "laliga",
    local: "A",
    visitante: "B",
    metrica: "goles",
    version: "v1",
    regla: { tipo: "ou", lado: "total", linea: 2.5, over: true },
  },
};
test("kuota-v1 conserva íntegramente boleto, identidad, versión, banca y enfrentamiento", () => {
  const saved = {
    ...initial,
    partidos: { laliga: { local: "A", visitante: "B" } },
    boleto: [leg],
    banca: 750,
  };
  assert.deepEqual(
    restaurar(JSON.stringify(saved), initial, ["laliga"], ["goles"]),
    saved,
  );
});
test("selecciones antiguas permanecen visibles para que el motor decida su validez", () => {
  const old = { ...leg };
  delete old.seleccion;
  assert.deepEqual(
    restaurar(
      JSON.stringify({ ...initial, boleto: [old] }),
      initial,
      ["laliga"],
      ["goles"],
    ).boleto,
    [old],
  );
});
test("datos ilegibles o corruptos no provocan errores de render", () => {
  for (const raw of [null, "{", "null", "[]", '"hola"'])
    assert.deepEqual(restaurar(raw, initial, ["laliga"], ["goles"]), initial);
  const saved = restaurar(
    JSON.stringify({
      liga: "inexistente",
      met: "otra",
      partidos: { laliga: null },
      boleto: [null, {}],
      banca: -1,
    }),
    initial,
    ["laliga"],
    ["goles"],
  );
  assert.deepEqual(saved, initial);
});
test("identidad de mercado respeta línea y versión, sin depender del orden JSON", () => {
  const reordered = {
    version: "v1",
    regla: { over: true, linea: 2.5, lado: "total", tipo: "ou" },
    metrica: "goles",
    visitante: "B",
    local: "A",
    liga: "laliga",
  };
  assert.equal(
    identidadSeleccion(leg.seleccion),
    identidadSeleccion(reordered),
  );
  assert.notEqual(
    identidadSeleccion(leg.seleccion),
    identidadSeleccion({ ...reordered, version: "v2" }),
  );
  assert.notEqual(
    identidadSeleccion(leg.seleccion),
    identidadSeleccion({
      ...reordered,
      regla: { ...reordered.regla, linea: 3 },
    }),
  );
});
test("agrupar boleto conserva índices originales y no fusiona ligas distintas", () => {
  const other = {
    ...leg,
    partido: "C vs D",
    seleccion: { ...leg.seleccion, local: "C", visitante: "D" },
  };
  const same = {
    ...leg,
    metrica: "Corners",
    seleccion: { ...leg.seleccion, metrica: "corners" },
  };
  const anotherLeague = {
    ...leg,
    seleccion: { ...leg.seleccion, liga: "premier" },
  };
  const groups = gruposBoleto([leg, other, same, anotherLeague]);
  assert.equal(groups.length, 3);
  assert.deepEqual(
    groups[0].legs.map((l) => l.index),
    [0, 2],
  );
  assert.equal(groups[1].legs[0].index, 1);
  assert.equal(groups[2].legs[0].index, 3);
});
