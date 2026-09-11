import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
function expected(mode, input) {
  const p = spawnSync(oracle, [mode, JSON.stringify(input)], { encoding: 'utf8' });
  assert.equal(p.status, 0, p.stderr);
  return p.stdout.trim();
}
const base = { mode: 'vrs', desired: 1, desireds: [1, 2], ordinals: [2, 3], existing: 2, fair: true, crash: false, drop: false, monkey: false, vct: false };

test('all scenario seeds preserve admission, controller IDs, counters and fault flags', async t => {
  const { w, json, text } = await load();
  const modes = ['vrs', 'vrsMulti', 'vrsPods', 'vrsOrphan', 'stateful', 'statefulFaults', 'statefulPods', 'statefulMulti', 'statefulMultiFaults', 'deployment'];
  let count = 0;
  for (const mode of modes) for (const desired of [-1, 0, 1, 2]) for (const fair of [false, true]) for (const vct of [false, true]) {
    const input = { ...base, mode, desired, fair, vct, crash: !fair, monkey: fair, drop: !vct };
    assert.deepEqual(JSON.parse(text(w.scenarioFixtureRender(json(input)))), JSON.parse(expected('scenario', input)), JSON.stringify(input)); count++;
  }
  for (const mode of ['vrsMulti', 'statefulMulti', 'statefulMultiFaults']) for (const desireds of [[], [0], [2, -1, 1]]) {
    const input = { ...base, mode, desireds };
    assert.deepEqual(JSON.parse(text(w.scenarioFixtureRender(json(input)))), JSON.parse(expected('scenario', input))); count++;
  }
  for (const ordinals of [[], [-1], [0], [1, 1], [3, 2]]) {
    const input = { ...base, mode: 'statefulPods', ordinals };
    assert.deepEqual(JSON.parse(text(w.scenarioFixtureRender(json(input)))), JSON.parse(expected('scenario', input))); count++;
  }
  const negative = { ...base, mode: 'vrsPods', existing: -1 };
  assert.equal(text(w.scenarioFixtureRender(json(negative))), expected('scenario', negative));
  t.diagnostic(`${count} differential seeds plus explicit invalid-count error`);
});

test('scale-down seed integrity checks live ownership, distinct ordinals and replica bounds', async () => {
  const { w, json, text } = await load();
  const state = JSON.parse(text(w.scenarioFixtureRender(json({ ...base, mode: 'statefulPods' }))));
  const cases = [];
  for (const ordinals of [[], [2], [2, 3], [2, 2], [0], [-1], [99]]) cases.push({ state, ordinals });
  for (const field of ['uid', 'name', 'kind', 'controller', 'blockOwnerDeletion']) {
    const changed = structuredClone(state);
    const pod = changed.apiServer.resources.find(e => e.obj.kind === 'Pod').obj;
    pod.metadata.ownerReferences[0][field] = field === 'uid' ? 99 : field === 'kind' ? 'Pod' : field === 'name' ? 'wrong' : false;
    cases.push({ state: changed, ordinals: [2, 3] });
  }
  for (const input of cases) assert.equal(text(w.scenarioIntactRender(json(input))), expected('intact', input));
});
