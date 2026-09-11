import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { load } from './host.mjs';

function adapters(host) {
  const { w, bytes, integer } = host;
  const opt = (value, absent, present, encode) => value === undefined || value === null
    ? absent() : present(encode(value));
  const ob = value => opt(value, w.noneBool, w.someBool, v => v ? w.boolTrue() : w.boolFalse());
  const os = value => opt(value, w.noneBytes, w.someBytes, bytes);
  const oi = value => opt(value, w.noneInt, w.someInt, integer);
  const kind = k => typeof k === 'object'
    ? w.commonKindCustomResourceValue(bytes(k.customResource)) : w[`commonKind${k}Value`]();
  const owner = o => w.ownerReferenceTMake(ob(o.blockOwnerDeletion), ob(o.controller), kind(o.kind), bytes(o.name), integer(o.uid));
  const map = o => Object.entries(o).reduce((m, [k, v]) => w.stringMapSet(bytes(k), bytes(v), m), w.stringMapEmpty());
  const om = o => opt(o, w.noneStringMap, w.someStringMap, map);
  const owners = xs => [...xs].reverse().reduce((list, o) => w.listOwnerReferenceTPush(owner(o), list), w.listOwnerReferenceTEmpty());
  const strings = xs => [...xs].reverse().reduce((list, s) => w.listBytesPush(bytes(s), list), w.listBytesEmpty());
  const metadata = m => w.objectMetaTMake(os(m.name), os(m.generateName), os(m.namespace), oi(m.resourceVersion), oi(m.uid),
    om(m.labels), om(m.annotations), opt(m.ownerReferences, w.noneOwners, w.someOwners, owners),
    opt(m.finalizers, w.noneStrings, w.someStrings, strings), os(m.deletionTimestamp));
  return { metadata, owner, map, om };
}

const baseOwner = { controller: true, blockOwnerDeletion: true, kind: { customResource: 'vreplicaset' }, name: 'vrs1', uid: 7 };
const base = { name: 'pod1', namespace: 'ns', resourceVersion: 1, uid: 2,
  labels: { app: 'example' }, ownerReferences: [baseOwner] };
const seed = { left: base, right: base, owner: baseOwner, other: baseOwner,
  selector: { matchLabels: { app: 'example' } }, labels: { app: 'example', extra: 'x' } };
const cases = [seed];
for (const field of ['name', 'namespace', 'resourceVersion', 'uid', 'ownerReferences', 'labels']) {
  const left = { ...base }; delete left[field];
  cases.push({ ...seed, left });
}
cases.push(
  { ...seed, left: { ...base, ownerReferences: [] } },
  { ...seed, left: { ...base, ownerReferences: [baseOwner, baseOwner] } },
  { ...seed, owner: { ...baseOwner, uid: 8 } },
  { ...seed, owner: { ...baseOwner, controller: false } },
  { ...seed, owner: { ...baseOwner, controller: null } },
  { ...seed, other: { ...baseOwner, kind: { customResource: 'another' } } },
  { ...seed, selector: {}, labels: {} },
  { ...seed, selector: { matchLabels: {} }, labels: {} },
  { ...seed, labels: { app: 'wrong' } },
  { ...seed, left: {}, right: { finalizers: [] } },
  { ...seed, left: { finalizers: ['a', 'a'] }, right: { finalizers: ['a'] } },
  { ...seed, left: { labels: { z: '1', a: '2' } }, right: { labels: { a: '2', z: '1' } } },
  { ...seed, left: { ...base, name: '', namespace: '', uid: -1, resourceVersion: -1 } },
);

test('metadata, owner, and selector predicates agree with OCaml on adversarial cases', async () => {
  const host = await load();
  const { w } = host;
  const { metadata, owner, map, om } = adapters(host);
  const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
  for (const [index, input] of cases.entries()) {
    const result = spawnSync(oracle, [JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.error?.message ?? result.stderr);
    const left = metadata(input.left), right = metadata(input.right);
    const own = owner(input.owner), other = owner(input.other);
    const actual = {
      wellFormed: Boolean(w.objectMetaWellFormedFlag(left)),
      metadataEqual: Boolean(w.objectMetaEqualFlag(left, right)),
      ownerEqual: Boolean(w.ownerEqualFlag(own, other)),
      ownerEqualWithoutUid: Boolean(w.ownerEqualWithoutUidFlag(own, other)),
      controller: Boolean(w.ownerIsControllerFlag(own)),
      contains: Boolean(w.objectMetaOwnersContainFlag(left, own)),
      onlyContains: Boolean(w.objectMetaOwnersOnlyContainFlag(left, own)),
      selectorMatches: Boolean(w.selectorMatchesFlag(w.labelSelectorTMake(om(input.selector.matchLabels)), map(input.labels))),
    };
    assert.deepEqual(actual, JSON.parse(result.stdout), `oracle case ${index}`);
  }
});

test('metadata map updates preserve absent versus present-empty maps', async () => {
  const host = await load();
  const { w, bytes } = host;
  const { metadata } = adapters(host);
  const empty = w.objectMetaDefault();
  assert.equal(w.objectMetaEqualFlag(w.objectMetaWithoutLabel(bytes('k'), empty), empty), 1);
  const added = w.objectMetaAddLabel(bytes('k'), bytes('v'), empty);
  assert.equal(w.objectMetaEqualFlag(added, metadata({ labels: { k: 'v' } })), 1);
  const removed = w.objectMetaWithoutLabel(bytes('k'), added);
  assert.equal(w.objectMetaEqualFlag(removed, metadata({ labels: {} })), 1);
  assert.equal(w.objectMetaEqualFlag(removed, empty), 0);
  const annotated = w.objectMetaAddAnnotation(bytes('a'), bytes('b'), added);
  assert.equal(w.objectMetaEqualFlag(annotated, metadata({ labels: { k: 'v' }, annotations: { a: 'b' } })), 1);
});
