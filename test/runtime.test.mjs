import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';
const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const policy = { spec: true, status: true, valid: true, transition: true, defaultStatus: { replicas: 0 } };
test('executable server seeding preserves stamping and explicit rejection errors', async t => {
  const { w, json, text } = await load();
  const object = { kind: 'Pod', metadata: { name: 'p', namespace: 'ns' }, spec: {}, status: null };
  const cases = [{ policy, seed: [] }, { policy, seed: [object] }, { policy, seed: [object, object] }];
  for (const metadata of [{}, { name: 'p' }, { namespace: 'ns', generateName: 'x' }, { name: 'p', namespace: 'ns', uid: 99, resourceVersion: 100 }, { name: 'p', namespace: 'ns', deletionTimestamp: 'old' }]) cases.push({ policy, seed: [{ ...object, metadata }] });
  for (const flag of ['spec', 'status', 'valid']) cases.push({ policy: { ...policy, [flag]: false }, seed: [object] });
  cases.push({ policy, seed: [object, { ...object, metadata: { generateName: 'generated-' } }] });
  for (const input of cases) {
    const r = spawnSync(oracle, ['exec-create', JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr);
    assert.deepEqual(JSON.parse(text(w.execCreateRender(json(input)))), JSON.parse(r.stdout), JSON.stringify(input));
  }
  t.diagnostic(`${cases.length} source seeding results match`);
});
test('executable reconciliation, requeue and joint fixpoint preserve complete trajectories', async t => {
  const { w, json, text } = await load();
  const cases = [];
  for (const kind of ['vrs', 'stateful', 'deployment']) for (const desired of [0, 1, 3]) {
    const seed = { mode: kind === 'stateful' ? 'statefulFaults' : kind, desired, desireds: [1, 0], ordinals: [], existing: 0, fair: true, crash: false, drop: false, monkey: false, vct: kind === 'stateful' };
    const state = JSON.parse(text(w.scenarioFixtureRender(json(seed)))).apiServer;
    const entry = state.resources[0];
    const base = { policy, state, models: [kind], fuel: 100, rounds: 10, namespace: 'ns', cr: entry.obj, queue: [entry.key, entry.key, { ...entry.key, name: 'absent' }] };
    for (const mode of ['reconcile', 'controller', 'fixpoint']) for (const fuel of [-1, 0, 1, 2, 10, 100]) cases.push({ ...base, mode, fuel });
    cases.push({ ...base, mode: 'controller', rounds: 0 });
    if (kind === 'deployment') for (const rounds of [0, 1, 2, 10]) for (const models of [['deployment', 'vrs'], ['vrs', 'deployment']]) cases.push({ ...base, mode: 'fixpoint', models, rounds });
  }
  for (const mode of ['vrsMulti', 'statefulMulti']) {
    const seed = { mode, desired: 1, desireds: [1, 0, 2], ordinals: [], existing: 0, fair: true, crash: false, drop: false, monkey: false, vct: false };
    const state = JSON.parse(text(w.scenarioFixtureRender(json(seed)))).apiServer;
    cases.push({ policy, state, mode: 'controller', models: [mode === 'vrsMulti' ? 'vrs' : 'stateful'], fuel: 100, rounds: 3, namespace: 'ns', queue: state.resources.map(x => x.key).reverse() });
  }
  let converged = 0, incomplete = 0, joint = 0;
  for (const input of cases) {
    const r = spawnSync(oracle, ['runtime', JSON.stringify(input)], { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 });
    assert.equal(r.status, 0, r.stderr);
    const expected = JSON.parse(r.stdout);
    const actual = JSON.parse(text(w.runtimeRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    assert.ok(actual.checks.every(Boolean));
    converged += actual.result.ok?.converged === true;
    incomplete += actual.result.ok?.incomplete === 0;
    joint += input.models.length === 2 && input.cr.spec.replicas === 3 && actual.result.ok?.converged === true;
  }
  assert.ok(converged > 0); assert.ok(incomplete > 0); assert.ok(joint > 0);
  t.diagnostic(`${cases.length} complete runtime trajectories, with independent API agreement on every request`);
});
