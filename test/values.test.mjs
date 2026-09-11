import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';
const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
test('source defaults preserve option presence and special field defaults', async t => {
  const { w, text } = await load();
  const r = spawnSync(oracle, ['defaults'], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const defaults = JSON.parse(text(w.defaultsRender(0)));
  assert.deepEqual(defaults, JSON.parse(r.stdout));
  t.diagnostic(`${Object.keys(defaults).length} typed defaults match source`);
});
test('text boundary preserves integer tags, float rendering, duplicate keys and escapes', async t => {
  const { w, text, parse, json } = await load();
  const cases = ['null', 'true', '0', '-0', '1.0', '-0.0', '1e20', '1e-4', '1e-5', '1e+16', '1e+15', '1e-400',
    '4611686018427387903', '-4611686018427387904', '4611686018427387904', '-4611686018427387905',
    '{"2":0,"1":1,"2":3}', '{"x":1.0,"x":1}', '"\\ud83d\\ude03"', '"é漢字"', JSON.stringify(String.fromCharCode(...Array.from({length: 32}, (_, i) => i)))];
  for (let i = 1; i <= 100; ++i) { const s = String(Math.sin(i) * 10 ** ((i % 41) - 20)); cases.push(/[.e]/.test(s) ? s : `${s}.0`); }
  for (const input of cases) {
    const r = spawnSync(oracle, ['value', input], { encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr);
    const parsed = parse(input); assert.equal(parsed.ok, true, input);
    assert.equal(text(w.valueRender(parsed.value)), r.stdout.trim(), input);
  }
  for (const input of ['', '{', '[1,]', '{"a":}', '01', '1.', 'true false', '"\\ud800"', '"a\nb"', '1e400', 'NaN', 'Infinity', '-Infinity']) assert.equal(parse(input).ok, false, input);
  assert.throws(() => json(9007199254740992), /BigInt/);
  assert.equal(text(w.valueRender(json(4611686018427387903n))), '4611686018427387903');
  t.diagnostic(`${cases.length} exact rendered values match Yojson.Safe`);
});
