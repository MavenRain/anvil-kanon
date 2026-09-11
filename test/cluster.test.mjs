import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const clone = x => structuredClone(x);
const kind = name => ({ customResource: name });
const owner = (name, resource, uid) => ({ controller: true, blockOwnerDeletion: true, kind: kind(resource), name, uid });
const template = { metadata: { labels: { app: 'x' } }, spec: { containers: [{ name: 'main', image: 'v1' }] } };
const crs = [
  { kind: kind('vreplicaset'), metadata: { name: 'r', namespace: 'ns', uid: 1, resourceVersion: 0, ownerReferences: [owner('d', 'vdeployment', 2)] }, spec: { replicas: 2, selector: { matchLabels: { app: 'x' } }, template }, status: null },
  { kind: kind('vdeployment'), metadata: { name: 'd', namespace: 'ns', uid: 2, resourceVersion: 0 }, spec: { replicas: 2, selector: { matchLabels: { app: 'x' } }, template }, status: null },
  { kind: kind('vstatefulset'), metadata: { name: 's', namespace: 'ns', uid: 3 }, spec: { replicas: 2, selector: { matchLabels: { app: 'x' } }, template, serviceName: 'headless' }, status: null },
];
const ref = obj => ({ kind: obj.kind, name: obj.metadata.name, namespace: obj.metadata.namespace });
const entry = obj => ({ key: ref(obj), obj });
const policy = { spec: true, status: true, valid: true, transition: true, defaultStatus: null };
const bound = { maxInFlight: 8, maxObjectsPerKind: 4, maxControllers: 3, uidCeiling: 16, rvCeiling: 32, reconcileCeiling: 8, maxReconcileDepth: 16, monkeyForge: [] };
const emptyController = () => ({ ongoing: [], scheduled: [], reconcileIdAllocator: 0 });
const base = () => ({ apiServer: { resources: crs.map(entry), uidCounter: 10, resourceVersionCounter: 1 },
  controllers: crs.map((_, key) => ({ key, value: { controller: emptyController(), external: null, crashEnabled: true } })),
  network: [], rpcIdAllocator: 0, reqDropEnabled: true, podMonkeyEnabled: true });
const host = (id, key) => ({ tag: 'controller', id, key });
const message = (src, dst, rpcId, content) => ({ src, dst, rpcId, content });
const request = (tag, value) => ({ tag: 'request', body: { tag: `${tag}Request`, value } });
const response = (tag, value) => ({ tag: 'response', body: { tag: `${tag}Response`, value: { res: { ok: value } } } });

async function comparator() {
  const { w, json, text } = await load();
  return input => {
    const result = spawnSync(oracle, ['cluster', JSON.stringify(input)], { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 });
    assert.equal(result.status, 0, result.stderr);
    const expected = JSON.parse(result.stdout);
    const actual = JSON.parse(text(w.clusterFixtureRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    return actual;
  };
}

test('cluster successors match all host actions, faults, duplicate messages and bound caps', async t => {
  const compare = await comparator();
  const cases = [];
  const add = (state, b = bound, echoExternal = false) => cases.push({ state, bound: b, policy, echoExternal });
  for (let flags = 0; flags < 8; flags++) {
    const s = base(); s.reqDropEnabled = Boolean(flags & 1); s.podMonkeyEnabled = Boolean(flags & 2);
    for (const actor of s.controllers) actor.value.crashEnabled = Boolean(flags & 4);
    add(s);
  }
  const missingActors = base(); missingActors.controllers = []; add(missingActors);
  for (let id = 0; id < 3; id++) {
    const scheduled = base(); scheduled.controllers[id].value.controller.scheduled = [entry(crs[id])]; add(scheduled);
    const ongoing = base(); ongoing.controllers[id].value.controller.reconcileIdAllocator = 1;
    ongoing.controllers[id].value.controller.ongoing = [{ key: ref(crs[id]), value: {
      triggeringCr: crs[id], pendingReqMsg: null, localState: { step: { step: 'init' } }, reconcileId: 0 } }];
    add(ongoing);
    for (const localState of [{ invalid: 'corrupt state' }, { step: { step: 'done' } }, { step: { step: 'error' } }]) {
      const s = clone(ongoing); s.controllers[id].value.controller.ongoing[0].value.localState = localState; add(s);
    }
  }
  const pending = message(host(0, ref(crs[0])), { tag: 'api' }, 0, request('list', { kind: 'Pod', namespace: 'ns' }));
  const reply = message({ tag: 'api' }, host(0, ref(crs[0])), 0, response('list', []));
  for (const messages of [[pending], [pending, pending], [reply], [pending, reply], [reply, reply]]) {
    const s = base(); s.network = messages; s.rpcIdAllocator = 1;
    s.controllers[0].value.controller.ongoing = [{ key: ref(crs[0]), value: { triggeringCr: crs[0], pendingReqMsg: pending,
      localState: { step: { step: 'afterListPods' } }, reconcileId: 0 } }];
    s.controllers[0].value.controller.reconcileIdAllocator = 1;
    add(s);
    for (const cap of [-1, 0, 1, 2]) add(s, { ...bound, maxInFlight: cap });
  }
  for (const field of ['rpcId', 'dst', 'content']) {
    const bad = clone(reply);
    if (field === 'rpcId') bad.rpcId = 7;
    if (field === 'dst') bad.dst.key = ref(crs[1]);
    if (field === 'content') bad.content = response('get', crs[0]);
    const s = base(); s.network = [bad]; s.controllers[0].value.controller.ongoing = [{ key: ref(crs[0]), value: {
      triggeringCr: crs[0], pendingReqMsg: pending, localState: { step: { step: 'afterListPods' } }, reconcileId: 0 } }]; add(s);
  }
  const garbage = base();
  const orphanPod = { kind: 'Pod', metadata: { name: 'orphan', namespace: 'ns', uid: 20,
    ownerReferences: [owner('gone', 'vreplicaset', 99)] }, spec: template.spec, status: null };
  for (const kind of ['ConfigMap', 'Pod', 'Secret']) for (const name of ['a', 'b', 'c']) {
    const obj = clone(orphanPod); obj.kind = kind; obj.metadata.name = name; garbage.apiServer.resources.push(entry(obj));
  }
  for (const maxObjectsPerKind of [-1, 0, 1, 2, 4]) add(garbage, { ...bound, maxObjectsPerKind });
  for (const maxControllers of [-1, 0, 1, 2, 3]) add(base(), { ...bound, maxControllers });
  add(base(), { ...bound, maxObjectsPerKind: 0, monkeyForge: [orphanPod] });
  const external = base(); external.controllers[2].value.external = { state: null };
  external.network = [message(host(2, ref(crs[2])), { tag: 'external', id: 2 }, 4, { tag: 'externalRequest', body: { hello: 'world' } })];
  add(external, bound, true); add(external);
  for (const input of cases) compare(input);
  t.diagnostic(`${cases.length} full successor-list differential fixtures`);
});

test('each controller completes a reconcile through its real API and network driver', async t => {
  const compare = await comparator();
  let transitions = 0;
  for (let id = 0; id < 3; id++) {
    let state = base(); state.reqDropEnabled = false; state.podMonkeyEnabled = false;
    for (const actor of state.controllers) actor.value.crashEnabled = false;
    state.controllers[id].value.controller.scheduled = [entry(crs[id])];
    let finished = false;
    for (let turn = 0; turn < 40; turn++) {
      const successors = compare({ state, bound, policy, echoExternal: false });
      const chosen = successors.find(x => x.step.tag === 'controller' && x.step.id === id)
        ?? successors.find(x => x.step.tag === 'api');
      assert.ok(chosen, `controller ${id} stalled at ${JSON.stringify(state)}`);
      const previous = state.controllers.find(x => x.key === id).value.controller;
      state = chosen.state; transitions++;
      const actor = state.controllers.find(x => x.key === id).value;
      if (!actor.controller.ongoing.length && !actor.controller.scheduled.length) {
        assert.equal(previous.ongoing[0].value.localState.step.step, 'done', `controller ${id} ended with an error`);
        finished = true; break;
      }
    }
    assert.ok(finished, `controller ${id} did not finish`);
    if (id === 0) assert.equal(state.apiServer.resources.filter(x => x.key.kind === 'Pod').length, 2);
    if (id === 2) assert.equal(state.apiServer.resources.filter(x => x.key.kind === 'Pod').length, 2);
  }
  t.diagnostic(`${transitions} matched end-to-end transitions`);
});
