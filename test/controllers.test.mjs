import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const clone = x => structuredClone(x);
const kind = name => ({ customResource: name });
const owner = (name, resource, uid) => ({ blockOwnerDeletion: true, controller: true, kind: kind(resource), name, uid });
const template = { metadata: { labels: { app: 'demo' }, annotations: { note: 'template' } }, spec: { containers: [{ name: 'main', image: 'v1' }] } };
const vrs = { kind: kind('vreplicaset'), metadata: { name: 'r', namespace: 'ns', uid: 20,
  ownerReferences: [owner('d', 'vdeployment', 10)] }, spec: { replicas: 2, selector: { matchLabels: { app: 'demo' } }, template }, status: { replicas: 2 } };
const deployment = { kind: kind('vdeployment'), metadata: { name: 'd', namespace: 'ns', uid: 10, resourceVersion: 7 },
  spec: { replicas: 3, selector: { matchLabels: { app: 'demo' } }, template }, status: null };
const stateful = { kind: kind('vstatefulset'), metadata: { name: 's', namespace: 'ns', uid: 30 },
  spec: { replicas: 2, selector: { matchLabels: { app: 'demo' } }, template, serviceName: 'headless' }, status: null };
const pod = (name, parent = 'r', resource = 'vreplicaset', uid = 20) => ({ kind: 'Pod', metadata: {
  name, namespace: 'ns', uid: 50, labels: { app: 'demo' }, ownerReferences: [owner(parent, resource, uid)] }, spec: template.spec, status: null });
const pvc = { kind: 'PersistentVolumeClaim', metadata: { name: 'vstatefulset-data-s-0', namespace: 'ns' }, spec: null, status: null };
const response = (tag, payload, error = false) => ({ tag: `${tag}Response`, value: { res: { [error ? 'error' : 'ok']: payload } } });
const step = (tag, fields = {}) => ({ step: { step: tag }, ...fields });
const steps = {
  vrs: ['init', 'afterListPods', 'afterCreatePod', 'afterDeletePod', 'afterUpdateVrsStatus', 'done', 'error'],
  deployment: ['init', 'afterListVrs', 'afterCreateNewVrs', 'afterScaleNewVrs', 'afterEnsureNewVrs', 'afterScaleDownOldVrs', 'done', 'error'],
  stateful: ['init', 'afterListPod', 'getPvc', 'afterGetPvc', 'createPvc', 'afterCreatePvc', 'skipPvc', 'createNeeded', 'afterCreateNeeded',
    'updateNeeded', 'afterUpdateNeeded', 'deleteCondemned', 'afterDeleteCondemned', 'deleteOutdated', 'afterDeleteOutdated', 'done', 'error'],
};
function expected(operation, name, input) {
  const result = spawnSync(oracle, [operation, name, JSON.stringify(input)], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const text = result.stdout.trim();
  return text.startsWith('error: ') ? text : JSON.parse(text);
}
function parse(text) { return text.startsWith('error: ') ? text : JSON.parse(text); }

test('complete controller packs agree with source, including defaults and malformed fields', async t => {
  const h = await load();
  let count = 0;
  for (const [name, tags] of Object.entries(steps)) {
    const states = [null, true, {}, [], { step: 'init' }, step('unknown')];
    for (const tag of tags) {
      const s = step(tag);
      if (['afterCreatePod', 'afterDeletePod'].includes(tag)) s.step.diff = 2;
      states.push(s);
    }
    if (name === 'vrs') states.push(step('afterDeletePod', { filteredPods: [pod('vreplicaset-r-0')] }), step('init', { filteredPods: [null] }));
    if (name === 'deployment') states.push(step('afterEnsureNewVrs', { newVrs: vrs, oldVrsList: [vrs], oldVrsIndex: 1 }));
    if (name === 'stateful') states.push(step('updateNeeded', { needed: [null, pod('vstatefulset-s-1', 's', 'vstatefulset', 30)],
      neededIndex: 1, condemned: [pod('vstatefulset-s-3', 's', 'vstatefulset', 30)], condemnedIndex: 0, pvcs: [pvc], pvcIndex: 1 }),
      step('init', { needed: [7] }), step('init', { neededIndex: '0' }), step('init', { pvcs: {} }));
    for (const s of states) {
      assert.deepEqual(parse(h.text(h.w[`${name}StateDecodeRender`](h.json(s)))), expected('pack', name, s), `${name} ${JSON.stringify(s)}`);
      count++;
    }
  }
  t.diagnostic(`${count} differential state codec cases`);
});

test('all controller steps reject wrong response tags and handle every API error', async t => {
  const h = await load();
  let count = 0;
  const crs = { vrs, deployment, stateful };
  const tags = ['get', 'list', 'create', 'delete', 'update', 'updateStatus', 'getThenDelete', 'getThenUpdate', 'getThenUpdateStatus'];
  const errors = ['badRequest', 'conflict', 'forbidden', 'invalid', 'objectNotFound', 'objectAlreadyExists', 'notSupported',
    'internalError', 'timeout', 'serverTimeout', 'transactionAbort', 'other'];
  for (const [name, states] of Object.entries(steps)) {
    for (const tag of states) {
      const s = step(tag);
      if (['afterCreatePod', 'afterDeletePod'].includes(tag)) s.step.diff = 0;
      const responses = [null, ...tags.flatMap(tag => [response(tag, tag === 'list' ? [] : ['delete', 'getThenDelete'].includes(tag) ? {} : pod('p')),
        ...errors.map(e => response(tag, e, true))])];
      for (const resp of responses) {
        const input = { cr: crs[name], state: s, response: resp };
        assert.deepEqual(parse(h.text(h.w[`${name}InvokeRender`](h.json(input.cr), h.json(resp), h.json(s)))),
          expected('invoke', name, input), `${name} ${tag} ${JSON.stringify(resp)}`);
        count++;
      }
    }
  }
  t.diagnostic(`${count} differential transition/error cases`);
});

test('controller requests preserve scaling, ownership, storage, and ordinal behavior', async t => {
  const h = await load();
  const cases = [];
  const add = (name, cr, state, resp = null) => cases.push({ name, cr, state, response: resp });
  const pods = [pod('vreplicaset-r-0'), pod('vreplicaset-r-1'), pod('vreplicaset-r-2')];
  for (const desired of [0, 1, 2, 3, 4, -1]) {
    const cr = clone(vrs); cr.spec.replicas = desired;
    add('vrs', cr, step('afterListPods'), response('list', pods));
    add('vrs', cr, step('afterListPods'), response('list', []));
  }
  for (const diff of [0, 1, 2, 4]) {
    add('vrs', vrs, { step: { step: 'afterCreatePod', diff } }, response('create', pods[0]));
    add('vrs', vrs, { step: { step: 'afterDeletePod', diff }, filteredPods: pods }, response('getThenDelete', {}));
  }
  for (const change of [p => { p.metadata.name = 'foreign'; }, p => { p.metadata.deletionTimestamp = 'now'; },
    p => { p.metadata.ownerReferences[0].uid = 99; }, p => { p.metadata.labels.app = 'other'; }]) {
    const foreign = clone(pods[0]); change(foreign);
    add('vrs', vrs, step('afterListPods'), response('list', [foreign]));
  }
  for (const ready of [null, 0, 1, 2]) {
    for (const desired of [0, 1, 2, 3, 4]) {
      const cr = clone(deployment); cr.spec.replicas = desired;
      const child = clone(vrs); child.status = ready === null ? null : { replicas: ready };
      add('deployment', cr, step('afterListVrs'), response('list', [child]));
    }
  }
  add('deployment', deployment, step('afterListVrs'), response('list', []));
  const old = clone(vrs); old.metadata.name = 'old'; old.metadata.uid = 21; old.spec.template.spec.containers[0].image = 'old';
  for (const index of [0, 1, 2, 3]) add('deployment', deployment,
    step('afterEnsureNewVrs', { newVrs: vrs, oldVrsList: [old, vrs], oldVrsIndex: index }));
  add('deployment', deployment, step('afterListVrs'), response('list', [old, vrs]));
  const canonical = [0, 1, 3, 7].map(i => pod(`vstatefulset-s-${i}`, 's', 'vstatefulset', 30));
  for (const replicas of [0, 1, 2, 4, -1]) {
    const cr = clone(stateful); cr.spec.replicas = replicas;
    add('stateful', cr, step('afterListPod'), response('list', canonical));
    add('stateful', cr, step('afterListPod'), response('list', []));
  }
  for (const suffix of ['00', '01', '+1', '-1', '0x1', '1_0', '1x', '', '0', '10']) {
    add('stateful', stateful, step('afterListPod'), response('list', [pod(`vstatefulset-s-${suffix}`, 's', 'vstatefulset', 30)]));
  }
  const storage = clone(stateful);
  storage.spec.volumeClaimTemplates = [{ metadata: { name: 'data', labels: { app: 'overridden', pvc: 'yes' } },
    spec: { accessModes: ['ReadWriteOnce'], resources: { requests: { storage: '1Gi' } } } }, { metadata: { name: 'logs' } }];
  storage.spec.template.spec.volumes = [{ name: 'data', emptyDir: {} }, { name: 'other', emptyDir: {} }];
  add('stateful', storage, step('afterListPod'), response('list', []));
  for (const index of [0, 1, 2]) add('stateful', storage, step('createNeeded', { needed: [null, null], neededIndex: index }));
  add('stateful', storage, step('updateNeeded', { needed: [canonical[0]], neededIndex: 0 }));
  for (const tag of ['getPvc', 'createPvc', 'skipPvc', 'afterCreatePvc']) {
    for (const index of [0, 1, 2]) add('stateful', storage, step(tag, { needed: [null], pvcs: [pvc], pvcIndex: index }), response('create', pvc));
  }
  for (const tag of ['deleteCondemned', 'afterDeleteCondemned', 'deleteOutdated']) {
    const stale = clone(canonical[0]); stale.spec.containers[0].image = 'stale';
    add('stateful', storage, step(tag, { needed: [stale, null], condemned: canonical, condemnedIndex: 0 }), response('getThenDelete', {}));
  }
  for (const name of ['vrs', 'deployment', 'stateful']) {
    const original = { vrs, deployment, stateful }[name];
    for (const missing of ['name', 'namespace', 'uid']) {
      const cr = clone(original); delete cr.metadata[missing];
      add(name, cr, step('init'));
      add(name, cr, step(name === 'vrs' ? 'afterListPods' : name === 'deployment' ? 'afterListVrs' : 'afterListPod'), response('list', []));
      add(name, cr, step('done'));
    }
    const deleting = clone(original); deleting.metadata.deletionTimestamp = 'now'; add(name, deleting, step('init'));
  }
  for (const { name, ...input } of cases) {
    const actual = parse(h.text(h.w[`${name}InvokeRender`](h.json(input.cr), h.json(input.response), h.json(input.state))));
    assert.deepEqual(actual, expected('invoke', name, input), JSON.stringify({ name, ...input }));
  }
  t.diagnostic(`${cases.length} differential ownership/scaling/storage cases`);
});
