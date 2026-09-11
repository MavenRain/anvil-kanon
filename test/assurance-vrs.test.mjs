import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const clone = x => structuredClone(x);
const kind = { customResource: 'vreplicaset' };
const owner = { controller: true, blockOwnerDeletion: true, kind, name: 'r', uid: 1 };
const spec = { containers: [{ name: 'main', image: 'v1' }] };
const cr = { kind, metadata: { name: 'r', namespace: 'ns', uid: 1, resourceVersion: 0 },
  spec: { replicas: 1, selector: { matchLabels: { app: 'x' } }, template: { metadata: { labels: { app: 'x' } }, spec } }, status: { replicas: 1 } };
const pod = { kind: 'Pod', metadata: { name: 'vreplicaset-p', namespace: 'ns', uid: 2, resourceVersion: 1, ownerReferences: [owner], labels: { app: 'x' } }, spec, status: null };
const ref = obj => ({ kind: obj.kind, name: obj.metadata.name, namespace: obj.metadata.namespace });
const entry = obj => ({ key: ref(obj), obj: clone(obj) });
const base = () => ({ controllerId: 0, cr: clone(cr), state: {
  apiServer: { resources: [entry(cr), entry(pod)], uidCounter: 4, resourceVersionCounter: 3 },
  controllers: [{ key: 0, value: { controller: { ongoing: [], scheduled: [], reconcileIdAllocator: 1 }, external: null, crashEnabled: false } }],
  network: [], rpcIdAllocator: 1, reqDropEnabled: false, podMonkeyEnabled: false } });
const host = { tag: 'controller', id: 0, key: ref(cr) };
const request = (tag, value, src = host) => ({ src, dst: { tag: 'api' }, rpcId: 0, content: { tag: 'request', body: { tag: `${tag}Request`, value } } });
const list = request('list', { kind: 'Pod', namespace: 'ns' });
const reply = objects => ({ src: { tag: 'api' }, dst: host, rpcId: 0, content: { tag: 'response', body: { tag: 'listResponse', value: { res: { ok: objects } } } } });
const runtime = x => x.state.controllers[0].value.controller;
const reconcile = (x, localState, pendingReqMsg = list) => {
  runtime(x).ongoing = [{ key: ref(cr), value: { triggeringCr: clone(cr), pendingReqMsg, localState, reconcileId: 0 } }];
};

test('VReplicaSet always and eventual invariant partitions match the source', async t => {
  const { w, json, text } = await load();
  const cases = [base()];
  const add = mutate => { const x = base(); mutate(x); cases.push(x); };
  for (const replicas of [-1, 0, 1, 2, null]) for (const status of [null, { replicas: 0 }, { replicas: 1 }, { replicas: 2 }]) add(x => {
    x.cr.spec.replicas = replicas; x.state.apiServer.resources[0].obj.status = status;
  });
  for (const field of ['name', 'namespace', 'uid', 'resourceVersion', 'ownerReferences', 'labels', 'deletionTimestamp']) for (const value of [null, ...(field === 'uid' || field === 'resourceVersion' ? [0, 1, 4] : [])]) add(x => {
    x.state.apiServer.resources[1].obj.metadata[field] = value;
  });
  add(x => { x.state.apiServer.resources[1].obj.metadata.ownerReferences = [owner, owner]; });
  for (const pending of [null, list]) add(x => { reconcile(x, { step: { step: 'done' } }, pending); });
  for (const step of ['init', 'afterListPods', 'afterCreatePod', 'afterDeletePod', 'afterUpdateVrsStatus', 'done', 'error']) {
    for (const filteredPods of [null, [], [pod]]) for (const pending of [null, list, request('getThenUpdateStatus', { namespace: 'ns', name: 'r', ownerRef: owner, obj: cr })]) add(x => {
      reconcile(x, { step: { step, ...(['afterCreatePod', 'afterDeletePod'].includes(step) ? { diff: 0 } : {}) }, filteredPods }, pending);
      x.state.network = [reply([pod])];
    });
  }
  for (const field of ['name', 'namespace', 'uid', 'resourceVersion', 'ownerReferences']) for (const value of [null, ...(field === 'name' || field === 'namespace' ? ['wrong'] : [])]) add(x => {
    const p = clone(pod); p.metadata[field] = value;
    reconcile(x, { step: { step: 'afterListPods' }, filteredPods: [p] }); x.state.network = [reply([p])];
  });
  for (const local of [null, { corrupt: true }, { step: { step: 'unknown' } }]) add(x => { reconcile(x, local); });
  for (const field of ['uid', 'spec', 'kind']) add(x => {
    reconcile(x, { step: { step: 'done' } }, null); const bad = clone(cr);
    if (field === 'uid') bad.metadata.uid = 4;
    if (field === 'spec') bad.spec = { ...bad.spec, replicas: 2 };
    if (field === 'kind') bad.kind = 'Pod';
    runtime(x).scheduled = [{ key: ref(cr), obj: bad }]; runtime(x).ongoing[0].value.triggeringCr = bad;
  });
  add(x => {
    reconcile(x, { step: { step: 'done' } }, null); const second = clone(runtime(x).ongoing[0]); second.key.name = 'other'; runtime(x).ongoing.push(second);
  });
  for (const target of [pod, cr, { ...pod, kind: 'ConfigMap' }]) for (const source of [host, { ...host, id: 1 }, { tag: 'builtin' }, { tag: 'monkey' }, { tag: 'external', id: 0 }]) {
    const operations = [
      ['get', { key: ref(target) }], ['list', { kind: target.kind, namespace: 'ns' }], ['create', { namespace: 'ns', obj: target }],
      ['delete', { key: ref(target), preconditions: null }], ['delete', { key: ref(target), preconditions: { uid: 1 } }],
      ['delete', { key: ref(target), preconditions: { uid: 2, resourceVersion: 1 } }], ['delete', { key: ref(target), preconditions: { uid: 4, resourceVersion: 0 } }],
      ['update', { namespace: 'ns', name: target.metadata.name, obj: target }], ['updateStatus', { namespace: 'ns', name: target.metadata.name, obj: target }],
      ['getThenDelete', { key: ref(target), ownerRef: owner }],
      ['getThenUpdate', { namespace: 'ns', name: target.metadata.name, obj: target, ownerRef: owner }],
      ['getThenUpdateStatus', { namespace: 'ns', name: target.metadata.name, obj: target, ownerRef: owner }],
    ];
    for (const [tag, value] of operations) for (const variant of ['original', 'foreign', 'unowned']) add(x => {
      const body = clone(value);
      if (variant === 'foreign') {
        if (body.key) body.key.namespace = 'wrong'; if (body.namespace) body.namespace = 'wrong';
        if (body.ownerRef) body.ownerRef.uid = 99;
      }
      if (variant === 'unowned' && body.obj) { body.obj.metadata.ownerReferences = null; body.obj.metadata.resourceVersion = 0; }
      x.state.network = [request(tag, body, source)];
    });
  }
  for (const objects of [[pod, pod], [{ ...pod, spec: 'bad' }], [cr], [{ ...pod, metadata: { ...pod.metadata, labels: { changed: 'yes' } } }]]) add(x => {
    reconcile(x, { step: { step: 'afterListPods' }, filteredPods: [pod] }); x.state.network = [reply(objects)];
  });
  const failed = new Set(), witnessed = new Set();
  for (const input of cases) {
    const result = spawnSync(oracle, ['assurance-vrs', JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const expected = JSON.parse(result.stdout);
    const actual = JSON.parse(text(w.vrsAssuranceFixtureRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    for (const i of actual) { if (!i.holds) failed.add(i.name); if (i.interesting) witnessed.add(i.name); }
  }
  assert.equal(failed.size, 16, `Missing failure cases: ${JSON.stringify([...failed])}`);
  assert.equal(witnessed.size, 16);
  t.diagnostic(`${cases.length} differential states, all 16 predicates refuted and non-vacuously exercised`);
});
