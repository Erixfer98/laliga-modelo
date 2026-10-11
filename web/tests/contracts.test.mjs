import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

// Ejecuta el módulo real de formatos; transpila sin escribir artefactos.
const source = fs.readFileSync(new URL('../lib/fmt.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const fmt = await import('data:text/javascript;base64,' + Buffer.from(outputText).toString('base64'));

test('los contratos nullable no muestran infinitos ni rompen el render', () => {
  for (const value of [null, NaN, Infinity, -Infinity]) {
    assert.equal(fmt.pct(value), 'No disponible');
    assert.equal(fmt.num(value), 'No disponible');
    assert.equal(fmt.signed(value), 'No disponible');
  }
  assert.equal(fmt.justa(0), 'No disponible');
});

test('cuota justa individual contempla devolución', () => {
  assert.equal(fmt.justa(.4, .2), '2.00');
  assert.equal(fmt.justa(.5, 0), '2.00');
});

test('el resumen local no multiplica probabilidades de una combinada', () => {
  const r = fmt.resumenLocal([{ prob: .9, cuota: 2 }, { prob: .8, cuota: 3 }]);
  assert.equal(r.prob, null);
  assert.equal(r.ev, null);
  assert.equal(r.cuota, 6);
  assert.equal(r.n, 2);
  assert.equal(fmt.resumenLocal([]), null);
});
