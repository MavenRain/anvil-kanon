import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';
const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
test('generic actions and state machines preserve enabled results and forward predicates', async () => {
  const { w, json, text } = await load();
  for (const state of [-2, 0, 1, 3]) for (const input of [-1, 0, 2]) for (const next of [state + input, 99]) {
    const fixture = { state, input, next };
    const r = spawnSync(oracle, ['action', JSON.stringify(fixture)], { encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr);
    assert.deepEqual(JSON.parse(text(w.actionRender(json(fixture)))), JSON.parse(r.stdout));
  }
});
