import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const clone = x => structuredClone(x);
const kind = { customResource: 'vstatefulset' };
const owner = { controller: true, blockOwnerDeletion: true, kind, name: 's', uid: 1 };
const spec = { containers: [{ name: 'main', image: 'v1' }] };
const cr = { kind, metadata: { name: 's', namespace: 'ns', uid: 1, resourceVersion: 0 }, spec: {
  replicas: 1, selector: { matchLabels: { app: 'x' } }, template: { metadata: { labels: { app: 'x' } }, spec },
  serviceName: 'headless', volumeClaimTemplates: [{ metadata: { name: 'data' }, spec: null, status: null }] }, status: null };
const pod = { kind: 'Pod', metadata: { name: 'vstatefulset-s-0', namespace: 'ns', uid: 2, resourceVersion: 1, ownerReferences: [owner],
  labels: { 'apps.kubernetes.io/pod-index': '0', 'statefulset.kubernetes.io/pod-name': 'vstatefulset-s-0', app: 'x' } }, spec, status: null };
const pvc = { kind: 'PersistentVolumeClaim', metadata: { name: 'vstatefulset-data-s-0', namespace: 'ns', uid: 3, resourceVersion: 2 }, spec: null, status: null };
const ref = o => ({ kind: o.kind, name: o.metadata.name, namespace: o.metadata.namespace });
const entry = o => ({ key: ref(o), obj: clone(o) });
const base = () => ({ controllerId: 2, cr: clone(cr), state: {
  apiServer: { resources: [entry(cr), entry(pod), entry(pvc)], uidCounter: 4, resourceVersionCounter: 3 },
  controllers: [{ key: 2, value: { controller: { ongoing: [], scheduled: [], reconcileIdAllocator: 1 }, external: null, crashEnabled: false } }],
  network: [], rpcIdAllocator: 1, reqDropEnabled: false, podMonkeyEnabled: false } });
const request = (tag, value, source = 'controller') => ({ src: source === 'controller' ? { tag: source, id: 2, key: ref(cr) } : { tag: source },
  dst: { tag: 'api' }, rpcId: 0, content: { tag: 'request', body: { tag: `${tag}Request`, value } } });
const list = request('list', { kind: 'Pod', namespace: 'ns' });
const response = objects => ({ src: { tag: 'api' }, dst: list.src, rpcId: 0,
  content: { tag: 'response', body: { tag: 'listResponse', value: { res: { ok: objects } } } } });
const reconcile = (x, localState, pendingReqMsg = list) => {
  x.state.controllers[0].value.controller.ongoing = [{ key: ref(cr), value: { triggeringCr: clone(cr), pendingReqMsg, localState, reconcileId: 0 } }];
};

test('VStatefulSet assurance preserves ownership, identity, response and local-state clauses', async t => {
  const { w, json, text } = await load();
  const cases = [base()];
  const add = mutate => { const x = base(); mutate(x); cases.push(x); };
  for (const replicas of [-1, 0, 1, 2]) add(x => { x.cr.spec.replicas = replicas; });
  for (const field of ['name', 'namespace', 'uid', 'labels', 'ownerReferences']) {
    for (const value of [null, ...(field === 'name' ? ['other', 'vstatefulset-s-01', 'vstatefulset-s--1', 'vstatefulset-s-1'] : [])]) add(x => {
      x.state.apiServer.resources[1].obj.metadata[field] = value;
    });
  }
  add(x => { x.state.apiServer.resources[1].obj.spec = { containers: [{ name: 'main', image: 'v2' }] }; });
  add(x => { x.state.apiServer.resources[1].obj.metadata.labels['apps.kubernetes.io/pod-index'] = '1'; });
  add(x => { x.state.apiServer.resources = []; });
  for (const field of ['finalizers', 'deletionTimestamp', 'ownerReferences']) for (const index of [1, 2]) add(x => {
    x.state.apiServer.resources[index].obj.metadata[field] = field === 'finalizers' ? [] : field === 'deletionTimestamp' ? 'now' : [owner, owner];
  });
  for (const name of ['vstatefulset-data-s-0', 'vstatefulset-data-s-1', 'vstatefulset-long-data-s-0', 'vstatefulset--s-0', 'bad']) add(x => {
    const obj = x.state.apiServer.resources[2].obj; obj.metadata.name = name; obj.metadata.ownerReferences = [owner];
    x.state.apiServer.resources[2].key = ref(obj);
  });
  for (const target of [pod, pvc, { ...pvc, kind: 'ConfigMap' }]) {
    for (const source of ['controller', 'monkey']) for (const field of ['none', 'name', 'namespace', 'generateName', 'finalizers', 'ownerReferences']) add(x => {
      const obj = clone(target);
      if (field === 'name') obj.metadata.name = 'wrong';
      if (field === 'namespace') obj.metadata.namespace = 'elsewhere';
      if (field === 'generateName') obj.metadata.generateName = 'generated-';
      if (field === 'finalizers') obj.metadata.finalizers = [];
      if (field === 'ownerReferences') obj.metadata.ownerReferences = [owner, owner];
      x.state.network = [request('create', { namespace: 'ns', obj }, source)];
    });
  }
  for (const source of ['controller', 'monkey']) {
    const operations = [
      ['get', { key: ref(pvc) }], ['get', { key: ref(pod) }], ['list', { kind: 'Pod', namespace: 'ns' }], ['list', { kind, namespace: 'ns' }],
      ['delete', { key: ref(pod), preconditions: null }], ['update', { name: pod.metadata.name, namespace: 'ns', obj: pod }],
      ['updateStatus', { name: pod.metadata.name, namespace: 'ns', obj: pod }],
      ['getThenDelete', { key: ref(pod), ownerRef: owner }],
      ['getThenUpdate', { name: pod.metadata.name, namespace: 'ns', obj: pod, ownerRef: owner }],
      ['getThenUpdateStatus', { name: pod.metadata.name, namespace: 'ns', obj: pod, ownerRef: owner }],
    ];
    for (const [tag, value] of operations) for (const valid of [true, false]) add(x => {
      const body = clone(value);
      if (!valid) {
        if (body.key) body.key.namespace = 'wrong';
        if (body.namespace) body.namespace = 'wrong';
        if (body.ownerRef) body.ownerRef.name = 'wrong';
      }
      x.state.network = [request(tag, body, source)];
    });
  }
  const steps = ['init', 'afterListPod', 'getPvc', 'afterGetPvc', 'createPvc', 'afterCreatePvc', 'skipPvc', 'createNeeded', 'afterCreateNeeded', 'updateNeeded',
    'afterUpdateNeeded', 'deleteCondemned', 'afterDeleteCondemned', 'deleteOutdated', 'afterDeleteOutdated', 'done', 'error'];
  for (const step of steps) for (const needed of [[], [null], [pod]]) for (const neededIndex of [-1, 0, 1, 2]) add(x => {
    reconcile(x, { step: { step }, needed, neededIndex, condemned: [], condemnedIndex: 0, pvcs: [], pvcIndex: 0 });
  });
  for (const name of ['vstatefulset-s-0', 'vstatefulset-s-1', 'vstatefulset-other-1']) for (const index of [-1, 0, 1, 2]) add(x => {
    const condemned = { ...pod, metadata: { ...pod.metadata, name } };
    reconcile(x, { step: { step: 'deleteCondemned' }, needed: [pod], neededIndex: 1, condemned: [condemned], condemnedIndex: index });
  });
  for (const local of [null, { corrupt: true }, { step: { step: 'unknown' } }]) add(x => { reconcile(x, local); });
  for (const pending of [null, list, request('get', { key: ref(pod) }), { ...list, dst: { tag: 'monkey' } }]) {
    for (const objects of [[], [pod], [pod, pod], [{ ...pod, metadata: { ...pod.metadata, namespace: 'wrong' } }], [{ ...pod, spec: 'bad' }], [cr]]) add(x => {
      reconcile(x, { step: { step: 'afterListPod' } }, pending); x.state.network = [response(objects)];
    });
  }
  const failed = new Set(), witnessed = new Set();
  for (const input of cases) {
    const result = spawnSync(oracle, ['assurance-stateful', JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const expected = JSON.parse(result.stdout);
    const actual = JSON.parse(text(w.statefulAssuranceFixtureRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    for (const i of actual) { if (!i.holds) failed.add(i.name); if (i.interesting) witnessed.add(i.name); }
  }
  assert.equal(failed.size, 18, `Missing failure cases: ${JSON.stringify([...failed])}`);
  assert.equal(witnessed.size, 18);
  t.diagnostic(`${cases.length} differential states, all 18 predicates refuted and non-vacuously exercised`);
});
