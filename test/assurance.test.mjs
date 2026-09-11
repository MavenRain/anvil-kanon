import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const clone = x => structuredClone(x);
const kind = { customResource: 'vstatefulset' };
const key = (name, k = kind) => ({ kind: k, name, namespace: 'ns' });
const owner = { controller: true, blockOwnerDeletion: true, kind, name: 's', uid: 1 };
const object = (name, uid = 1, k = kind) => ({ kind: k, metadata: { name, namespace: 'ns', uid, resourceVersion: 0, ownerReferences: [owner] }, spec: null, status: null });
const entry = obj => ({ key: key(obj.metadata.name, obj.kind), obj });
const controller = k => ({ tag: 'controller', id: 2, key: k });
const request = (tag, value, rpcId = 0, k = key('s')) => ({ src: controller(k), dst: { tag: 'api' }, rpcId, content: { tag: 'request', body: { tag: `${tag}Request`, value } } });
const reply = (req, obj) => ({ src: req.dst, dst: req.src, rpcId: req.rpcId, content: { tag: 'response', body: { tag: req.content.body.tag.replace('Request', 'Response'), value: { res: { ok: obj } } } } });
const pendingState = { pending: true }, quietState = { quiet: true };
const base = () => ({ policy: { spec: true, status: true, valid: true, transition: true, defaultStatus: null },
  bound: { maxInFlight: 8, maxObjectsPerKind: 4, maxControllers: 3, uidCeiling: 16, rvCeiling: 32, reconcileCeiling: 8, maxReconcileDepth: 16, monkeyForge: [] },
  controllerId: 2, pendingState, quietState,
  state: { apiServer: { resources: [entry(object('s'))], uidCounter: 4, resourceVersionCounter: 2 },
    controllers: [{ key: 2, value: { controller: { ongoing: [], scheduled: [], reconcileIdAllocator: 2 }, external: null, crashEnabled: false } }],
    network: [], rpcIdAllocator: 2, reqDropEnabled: false, podMonkeyEnabled: false } });
const runtime = x => x.state.controllers[0].value.controller;
const ongoing = (req, name = 's', state = pendingState, id = 0) => ({ key: key(name), value: { triggeringCr: object(name), pendingReqMsg: req, localState: state, reconcileId: id } });

test('assurance families preserve failure results and non-vacuity witnesses', async t => {
  const { w, json, text } = await load();
  const cases = [base()];
  const add = mutate => { const x = base(); mutate(x); cases.push(x); };
  add(x => { x.state.controllers = []; x.state.apiServer.resources = []; });
  for (const uid of [null, -1, 0, 1, 4]) for (const rv of [null, -1, 0, 2]) add(x => {
    const a = object('a', uid), b = object('b', uid);
    a.metadata.resourceVersion = rv; x.state.apiServer.resources = [entry(a), entry(b)];
  });
  for (const field of ['name', 'namespace', 'uid', 'resourceVersion']) add(x => { delete x.state.apiServer.resources[0].obj.metadata[field]; });
  add(x => { x.state.apiServer.resources[0].key.name = 'wrong'; });
  for (const owners of [null, [], [owner], [owner, owner], [{ ...owner, controller: false }]]) add(x => { x.state.apiServer.resources[0].obj.metadata.ownerReferences = owners; });
  for (const uid of [null, 1, 4]) add(x => {
    const obj = object('s', uid); runtime(x).scheduled = [entry(obj)];
    runtime(x).ongoing = [ongoing(null, 's', quietState)]; runtime(x).ongoing[0].value.triggeringCr = obj;
  });
  for (const duplicate of [false, true]) add(x => { runtime(x).ongoing = [ongoing(null, 'a', quietState), ongoing(null, 'b', quietState, duplicate ? 0 : 1)]; });
  const get = request('get', { key: key('p', 'Pod') });
  const pod = object('p', 2, 'Pod');
  const create = request('create', { namespace: 'ns', obj: pod });
  for (const req of [get, create]) {
    for (const local of [pendingState, quietState, null]) for (const flight of ['none', 'request', 'response', 'both', 'duplicate']) add(x => {
      runtime(x).ongoing = [ongoing(req, 's', local)]; const resp = reply(req, pod);
      x.state.network = flight === 'none' ? [] : flight === 'request' ? [req] : flight === 'response' ? [resp] : flight === 'both' ? [req, resp] : [req, req];
    });
    for (const field of ['name', 'namespace', 'kind', 'resourceVersion', 'spec']) add(x => {
      runtime(x).ongoing = [ongoing(req)]; const obj = clone(pod);
      if (field === 'kind') obj.kind = 'ConfigMap'; else if (field === 'spec') obj.spec = { changed: true };
      else obj.metadata[field] = field === 'resourceVersion' ? 2 : 'wrong';
      x.state.apiServer.resources.push(entry(pod)); x.state.network = [reply(req, obj)];
    });
  }
  add(x => { runtime(x).ongoing = [ongoing(null)]; });
  for (const duplicate of [false, true]) add(x => {
    runtime(x).ongoing = [ongoing(get), ongoing({ ...get, rpcId: duplicate ? 0 : 1 }, 't')];
    x.state.network = [get];
  });
  for (const src of [{ tag: 'api' }, { tag: 'external', id: 2 }, { tag: 'builtin' }, { tag: 'monkey' }, { tag: 'controller', id: 99, key: key('s') }, controller(key('s', 'Pod'))]) {
    for (const content of [get.content, create.content, request('delete', { key: key('p', 'Pod'), preconditions: null }).content,
      { tag: 'externalRequest', body: null }, { tag: 'externalResponse', body: null }]) add(x => { x.state.network = [{ ...get, src, content }]; });
  }
  for (const rpc of [-1, 0, 2, 7]) add(x => { const req = { ...get, rpcId: rpc }; runtime(x).ongoing = [ongoing(req)]; x.state.network = [req]; });
  add(x => { runtime(x).ongoing = [ongoing(get)]; x.state.network = [{ ...get, dst: { tag: 'external', id: 2 } }]; });
  add(x => { const req = { ...get, content: { tag: 'externalRequest', body: null }, dst: { tag: 'external', id: 2 } }; runtime(x).ongoing = [ongoing(req)]; x.state.network = [req]; });
  for (const cap of [-1, 0, 1, 2]) add(x => {
    x.bound.maxObjectsPerKind = cap; x.state.apiServer.resources.push(entry(pod));
    x.state.network = [reply(get, { ...pod, spec: { changed: true } })];
  });
  const failed = new Set(), witnessed = new Set();
  for (const input of cases) {
    const result = spawnSync(oracle, ['assurance', JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const expected = JSON.parse(result.stdout);
    const actual = JSON.parse(text(w.assuranceFixtureRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    for (const i of actual) { if (!i.holds) failed.add(i.name); if (i.interesting) witnessed.add(i.name); }
  }
  assert.equal(failed.size, 23, `Missing failure cases: ${JSON.stringify([...failed])}`);
  assert.equal(witnessed.size, 23);
  t.diagnostic(`${cases.length} differential states, all 23 predicates refuted and non-vacuously exercised`);
});
