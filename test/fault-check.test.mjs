import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const bound = { maxInFlight: 2, maxObjectsPerKind: 2, maxControllers: 1, uidCeiling: 5, rvCeiling: 5, reconcileCeiling: 1, maxReconcileDepth: 8, monkeyForge: [] };
const options = { desired: 1, desireds: [0, 0], ordinals: [2], drop: false, monkey: false, vct: false, requireFault: true };
const base = { bound, budget: { maxCrashes: 1, maxDrops: 1, maxMonkeyOps: 1 }, options, depth: 1, query: 'always' };
const queryNames = ['always', 'correspondence', 'reconcile', 'responseRv', 'responseMatched', 'store', 'helper', 'unique', 'settles', 'provenance', 'rely', 'forge', 'internal', 'scaleDown', 'localBinding', 'statePredicates'];

function compareOracle(mode, input) {
  const result = spawnSync(oracle, [mode, JSON.stringify(input)], { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test('fault drivers preserve all report fields and separate budget from counter pruning', async t => {
  const { w, json, text, integer } = await load();
  const cases = [];
  for (const query of queryNames) for (const depth of [0, 1, 3]) for (const requireFault of [false, true])
    cases.push({ ...base, query, depth, options: { ...options, requireFault } });
  for (const query of ['correspondence', 'reconcile', 'responseRv', 'responseMatched', 'helper'])
    cases.push({ ...base, query, depth: 6, options: { ...options, drop: true, vct: true } });
  for (const value of [-1, 0, 1]) for (const dim of ['maxCrashes', 'maxDrops', 'maxMonkeyOps'])
    cases.push({ ...base, query: 'rely', depth: 3, budget: { ...base.budget, [dim]: value }, options: { ...options, drop: true, monkey: true } });
  for (const field of ['uidCeiling', 'rvCeiling', 'reconcileCeiling'])
    cases.push({ ...base, depth: 2, bound: { ...bound, [field]: 0 } });
  for (const respecting of [false, true]) {
    const pod = JSON.parse(text(w.faultForgeRender(integer(1), respecting ? w.boolTrue() : w.boolFalse())));
    assert.deepEqual(pod, compareOracle('forge', { desired: 1, respecting }));
    cases.push({ ...base, query: 'forge', depth: 3, bound: { ...bound, monkeyForge: [pod] }, options: { ...options, monkey: true } });
  }
  let crashes = 0, ceilings = 0, budgets = 0, failed = 0;
  for (const input of cases) {
    const expected = compareOracle('fault-check', input);
    const actual = JSON.parse(text(w.faultCheckRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    crashes += actual.maxCrashesSeen > 0; ceilings += actual.prunedByCeiling; budgets += actual.prunedByBudget;
    failed += actual.outcome.tag === 'refuted';
  }
  assert.ok(crashes > 0); assert.ok(ceilings > 0); assert.ok(budgets > 0); assert.ok(failed > 0);
  t.diagnostic(`${cases.length} fault reports match across all 16 drivers, including forged-resource refutation`);
});
