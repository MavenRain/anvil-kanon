import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const bound = { maxInFlight: 2, maxObjectsPerKind: 2, maxControllers: 1, uidCeiling: 4, rvCeiling: 4, reconcileCeiling: 1, maxReconcileDepth: 8, monkeyForge: [] };
const base = { bound, stateful: false, query: 'always', desired: 1, desireds: [0, 0], depth: 2, forceFalse: false };

test('cluster checker reports preserve bounded verdicts, gates, counter maxima and pruning', async t => {
  const { w, json, text } = await load();
  const cases = [];
  for (const stateful of [false, true]) for (const query of ['always', 'esr', 'settled', 'temporal', 'unique'])
    for (const depth of [-1, 0, 1, 3]) cases.push({ ...base, stateful, query, depth });
  for (const stateful of [false, true]) for (const query of ['esr', 'settled', 'temporal']) for (const desired of [0, 1])
    cases.push({ ...base, stateful, query, desired, depth: 40 });
  for (const field of ['uidCeiling', 'rvCeiling', 'reconcileCeiling']) for (const value of [0, 1])
    cases.push({ ...base, query: 'settled', depth: 8, bound: { ...bound, [field]: value } });
  cases.push({ ...base, stateful: true, query: 'temporal', depth: 40, forceFalse: true });
  let decisive = 0, pruned = 0, refuted = 0, nonvacuous = 0;
  for (const input of cases) {
    const result = spawnSync(oracle, ['cluster-check', JSON.stringify(input)], { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 });
    assert.equal(result.status, 0, result.stderr);
    const expected = JSON.parse(result.stdout);
    const actual = JSON.parse(text(w.clusterCheckRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    decisive += actual.outcome.decisive === true; pruned += actual.pruned;
    refuted += actual.outcome.tag === 'refuted'; nonvacuous += actual.gateStates > 0;
  }
  assert.ok(decisive > 0); assert.ok(pruned > 0); assert.ok(refuted > 0); assert.ok(nonvacuous > 0);
  t.diagnostic(`${cases.length} complete reports match the pinned checker, including falsified temporal goal`);
});
