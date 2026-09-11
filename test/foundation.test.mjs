import assert from 'node:assert/strict';
import test from 'node:test';
import { load } from './host.mjs';

test('bytes preserve arbitrary binary content and lexicographic ordering', async () => {
  const { w, bytes, buffer } = await load();
  const values = [Buffer.alloc(0), Buffer.from([0, 255, 128, 34]), Buffer.from('é'), Buffer.from('z')];
  for (const a of values) for (const b of values) {
    assert.equal(w.bytesEqFlag(bytes(a), bytes(b)), Number(a.equals(b)));
    assert.equal(w.bytesLessFlag(bytes(a), bytes(b)), Number(Buffer.compare(a, b) < 0));
    assert.deepEqual(buffer(w.bytesAppend(bytes(a), bytes(b))), Buffer.concat([a, b]));
  }
});

test('signed integers retain negatives and decimal boundaries', async () => {
  const { w, text, integer } = await load();
  for (const n of [0, 1, -1, 9, 10, 99, 100, -100, 2147483647, -2147483648, Number.MAX_SAFE_INTEGER,
    4611686018427387903n, -4611686018427387904n]) {
    assert.equal(text(w.intText(integer(n))), String(n));
  }
  assert.throws(() => integer(4611686018427387904n), RangeError);
  assert.throws(() => integer(-4611686018427387905n), RangeError);
  const values = [-4611686018427387904n, -4611686018427387903n, -1n, 0n, 1n, 4611686018427387902n, 4611686018427387903n];
  for (const a of values) for (const b of values) {
    assert.equal(text(w.intText(w.intAdd(integer(a), integer(b)))), String(BigInt.asIntN(63, a + b)));
    assert.equal(text(w.intText(w.intSub(integer(a), integer(b)))), String(BigInt.asIntN(63, a - b)));
  }
  for (const a of values) assert.equal(text(w.intText(w.intNegate(integer(a)))), String(BigInt.asIntN(63, -a)));
});

test('JSON rendering preserves all fields, Unicode, escapes, and object order', async () => {
  const { w, json, text } = await load();
  for (const value of [null, true, false, -19, 0.25, 'a\n\t\u0000"\\é', [], {},
    { z: [null, { a: 1 }], a: 'x' }]) {
    assert.deepEqual(JSON.parse(text(w.valueRender(json(value)))), value);
  }
  assert.equal(w.valueEqFlag(json({ a: 1, b: 2 }), json({ a: 1, b: 2 })), 1);
  assert.equal(w.valueEqFlag(json({ a: 1, b: 2 }), json({ b: 2, a: 1 })), 0);
  assert.equal(w.valueEqFlag(json([1, 2]), json([2, 1])), 0);
});

test('maps replace duplicate keys and compare by content across insertion orders', async () => {
  const { w, bytes } = await load();
  const map = pairs => pairs.reduce((m, [k, v]) => w.stringMapSet(bytes(k), bytes(v), m), w.stringMapEmpty());
  const a = map([['z', '3'], ['a', 'old'], ['a', '1']]);
  const b = map([['a', '1'], ['z', '3']]);
  assert.equal(w.stringMapSize(a), 2);
  assert.equal(w.stringMapEqFlag(a, b), 1);
  assert.equal(w.stringMapSubsetFlag(map([['a', '1']]), a), 1);
  assert.equal(w.stringMapSubsetFlag(map([['a', 'wrong']]), a), 0);
  assert.equal(w.stringMapSize(w.stringMapRemove(bytes('missing'), a)), 2);
  assert.equal(w.stringMapEqFlag(w.stringMapRemove(bytes('z'), a), map([['a', '1']])), 1);
});

test('kind variants remain distinct, including custom-resource payloads', async () => {
  const { w, bytes } = await load();
  const constructors = ['ConfigMap', 'DaemonSet', 'PersistentVolumeClaim', 'Pod', 'Role',
    'RoleBinding', 'StatefulSet', 'Service', 'ServiceAccount', 'Secret'];
  const ranks = constructors.map(k => w.commonKindRank(w[`commonKind${k}Value`]()));
  ranks.push(w.commonKindRank(w.commonKindCustomResourceValue(bytes('vreplicaset'))));
  assert.equal(new Set(ranks).size, 11);
});
