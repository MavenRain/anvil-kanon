import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
const cli = fileURLToPath(new URL('../bin/anvil.mjs', import.meta.url));
test('operator and JSON commands work outside the repository working directory', () => {
  for (const controller of ['vrs', 'stateful', 'deployment']) {
    const r = spawnSync(process.execPath, [cli, 'operator', controller, '3'], { cwd: '/tmp', encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr);
    const report = JSON.parse(r.stdout);
    assert.equal(report.success, true); assert.equal(report.pods, 3); assert.equal(report.oracleAgreed, true);
    if (controller === 'stateful') assert.equal(report.pvcs, 3);
  }
  for (const [command, file] of [['cluster-check', 'checker'], ['fault-check', 'fault-checker'], ['proof', 'proof']]) {
    const input = readFileSync(new URL(`../examples/${file}.json`, import.meta.url), 'utf8');
    const r = spawnSync(process.execPath, [cli, command], { input, cwd: '/tmp', encoding: 'utf8' });
    assert.equal(r.status, 0, r.stderr); assert.doesNotThrow(() => JSON.parse(r.stdout));
  }
  const bad = spawnSync(process.execPath, [cli, 'api'], { input: '{', cwd: '/tmp', encoding: 'utf8' });
  assert.equal(bad.status, 1); assert.equal(JSON.parse(bad.stderr).kind, 'Value');
});
