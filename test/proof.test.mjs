import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';
const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const bound = { maxInFlight: 2, maxObjectsPerKind: 2, maxControllers: 1, uidCeiling: 4, rvCeiling: 4, reconcileCeiling: 1, maxReconcileDepth: 8, monkeyForge: [] };
test('entailment kernel checks formula shapes, specs, and obligations', async t => {
  const { w, text } = await load();
  const r = spawnSync(oracle, ['kernel'], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const actual = JSON.parse(text(w.kernelFixtures(0)));
  assert.deepEqual(actual, JSON.parse(r.stdout));
  assert.ok(actual.some(x => x.ok)); assert.ok(actual.some(x => x.error));
  t.diagnostic(`${actual.length} kernel results match Comp_cat.Rule`);
});
test('conditional liveness derivations and finite discharge reports match OCaml', async t => {
  const { w, json, text } = await load();
  const cases = [];
  for (const stateful of [false, true]) for (const desired of [0, 1, 2]) {
    const b = { ...bound, rvCeiling: stateful ? 5 : 4 };
    cases.push({ stateful, desired, bound: b });
    for (const cap of [{ reconcileCeiling: 0 }, { uidCeiling: 1 }, { maxInFlight: 0 }]) cases.push({ stateful, desired, bound: { ...b, ...cap } });
  }
  let success = 0, rejected = 0, stable = 0;
  for (const input of cases) {
    const r = spawnSync(oracle, ['proof', JSON.stringify(input)], { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
    assert.equal(r.status, 0, r.stderr);
    const expected = JSON.parse(r.stdout);
    const actual = JSON.parse(text(w.proofRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    success += actual.matches.ok === true; rejected += Boolean(actual.matches.error); stable += actual.tail.holds;
  }
  assert.ok(success > 0); assert.ok(rejected > 0); assert.ok(stable > 0);
  t.diagnostic(`${cases.length} proof results match, including rejected and successful obligations`);
});
