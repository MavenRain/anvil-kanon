import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const clone = x => structuredClone(x);
const policy = { spec: true, status: true, valid: true, transition: true, defaultStatus: { replicas: 0 } };
const owner = { kind: { customResource: 'vreplicaset' }, name: 'r', uid: 1, controller: true };
const key = { kind: 'Pod', name: 'p', namespace: 'ns' };
const object = { kind: 'Pod', metadata: { name: 'p', namespace: 'ns', uid: 4, resourceVersion: 6, ownerReferences: [owner] }, spec: {}, status: null };
const state = { resources: [{ key, obj: object }], uidCounter: 10, resourceVersionCounter: 20 };
const request = (tag, value) => ({ tag: `${tag}Request`, value });

test('nine API handlers match source admission order, merges, ownership and counters', async t => {
  const { w, json, text } = await load();
  const cases = [];
  const add = (request, s = state, p = policy) => cases.push({ request, state: s, policy: p });
  add(request('get', { key }));
  add(request('get', { key: { ...key, name: 'missing' } }));
  for (const kind of ['Pod', 'ConfigMap', { customResource: 'vreplicaset' }]) {
    for (const namespace of ['ns', 'other']) add(request('list', { kind, namespace }));
  }
  for (const name of ['p', 'new', null]) {
    for (const namespace of ['ns', 'other', null]) {
      for (const generated of [undefined, 'prefix-']) {
        const obj = clone(object);
        obj.metadata.name = name; obj.metadata.namespace = namespace;
        if (generated !== undefined) obj.metadata.generateName = generated;
        for (const flag of [null, 'spec', 'status', 'valid']) {
          const p = { ...policy }; if (flag) p[flag] = false;
          add(request('create', { namespace: 'ns', obj }), state, p);
        }
      }
    }
  }
  const duplicates = clone(state);
  duplicates.resources.push({ key: { ...key, name: 'prefix-0', namespace: 'other' }, obj: object },
    { key: { ...key, name: 'prefix-1' }, obj: object }, { key: { ...key, name: 'prefix-0', kind: 'ConfigMap' }, obj: object });
  const generated = clone(object); delete generated.metadata.name; generated.metadata.generateName = 'prefix-';
  add(request('create', { namespace: 'ns', obj: generated }), duplicates);
  for (const finalizers of [undefined, [], ['hold']]) {
    for (const deletionTimestamp of [undefined, 'old']) {
      const s = clone(state); s.resources[0].obj.metadata.finalizers = finalizers; s.resources[0].obj.metadata.deletionTimestamp = deletionTimestamp;
      for (const preconditions of [undefined, {}, { uid: 4 }, { uid: 5 }, { resourceVersion: 6 }, { resourceVersion: 7 }, { uid: 5, resourceVersion: 7 }]) {
        add(request('delete', { key, preconditions }), s);
      }
    }
  }
  for (const tag of ['update', 'updateStatus']) {
    for (const change of [null, obj => { delete obj.metadata.name; }, obj => { obj.metadata.name = 'other'; },
      obj => { obj.metadata.namespace = 'other'; }, obj => { delete obj.metadata.namespace; },
      obj => { delete obj.metadata.uid; }, obj => { obj.metadata.uid = 5; },
      obj => { delete obj.metadata.resourceVersion; }, obj => { obj.metadata.resourceVersion = 7; },
      obj => { obj.spec = { changed: true }; }, obj => { obj.status = { changed: true }; },
      obj => { obj.metadata.annotations = { note: 'updated' }; },
      obj => { obj.metadata.ownerReferences = [owner, { ...owner, name: 'other' }]; }]) {
      for (const flag of [null, 'spec', 'status', 'valid', 'transition']) {
        const obj = clone(object); if (change) change(obj);
        const p = { ...policy }; if (flag) p[flag] = false;
        add(request(tag, { namespace: 'ns', name: 'p', obj }), state, p);
      }
    }
    for (const finalizers of [[], ['old'], ['new']]) {
      const s = clone(state); s.resources[0].obj.metadata.deletionTimestamp = 'old'; s.resources[0].obj.metadata.finalizers = ['old'];
      const obj = clone(s.resources[0].obj); obj.metadata.finalizers = finalizers; obj.status = { changed: true };
      add(request(tag, { namespace: 'ns', name: 'p', obj }), s);
    }
    const custom = clone(object); custom.kind = { customResource: 'x' }; delete custom.metadata.resourceVersion;
    const s = clone(state); s.resources[0] = { key: { ...key, kind: custom.kind }, obj: custom };
    add(request(tag, { namespace: 'ns', name: 'p', obj: custom }), s);
  }
  for (const tag of ['getThenDelete', 'getThenUpdate', 'getThenUpdateStatus']) {
    for (const ownerRef of [owner, { ...owner, uid: 9 }, { ...owner, controller: false }, { ...owner, controller: null }]) {
      for (const missing of [false, true]) {
        const s = missing ? { ...state, resources: [] } : state;
        const obj = clone(object); obj.metadata.uid = 999; obj.metadata.resourceVersion = 999; obj.spec = { changed: true }; obj.status = { changed: true };
        add(request(tag, tag === 'getThenDelete' ? { key, ownerRef } : { namespace: 'ns', name: 'p', ownerRef, obj }), s);
      }
    }
  }
  for (const fixture of cases) {
    const input = JSON.parse(JSON.stringify(fixture));
    const result = spawnSync(oracle, ['api', JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const expectedText = result.stdout.trim();
    const actualText = text(w.apiInvokeRender(json(input)));
    const parse = s => s.startsWith('error: ') ? s : JSON.parse(s);
    assert.deepEqual(parse(actualText), parse(expectedText), JSON.stringify(input));
    const ref = spawnSync(oracle, ['api-reference', JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(ref.status, 0, ref.stderr);
    assert.deepEqual(parse(text(w.oracleInvokeRender(json(input)))), parse(ref.stdout.trim()), `independent reference: ${JSON.stringify(input)}`);
  }
  t.diagnostic(`${cases.length} differential API-server cases`);
});
