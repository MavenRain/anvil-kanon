import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { load } from './host.mjs';

const oracle = process.env.ANVIL_ORACLE ?? fileURLToPath(new URL('../build/oracle-source/_build/default/port_oracle/port_oracle.exe', import.meta.url));
const modes = ['always', 'eventually', 'next', 'alwaysEventually', 'eventuallyAlways', 'alternating', 'true', 'false'];

test('generic BFS and lasso checker agree on cycles, real self-loops, depth and fairness', async t => {
  const { w, json, text } = await load();
  const cases = [];
  for (let edges = 0; edges < 16; edges++) {
    const graph = [[], []];
    for (let a = 0; a < 2; a++) for (let b = 0; b < 2; b++) if (edges & (1 << (a * 2 + b))) graph[a].push(b);
    for (const depth of [0, 1, 2, 3]) for (const mode of modes) for (const fair of [false, true]) {
      cases.push({ graph, init: [0], depth, mode, target: [1], second: [0], fair });
    }
  }
  const graphs = [
    [[0, 1], [1, 2], [2]],
    [[0, 1, 2], [1, 2], [2, 3], [3]],
    [[1, 2], [0], [0]],
    [[0, 1, 2], [0, 1], [0, 2]],
    [[], [], []],
    [[1, 1, 0], [1]],
  ];
  for (const graph of graphs) for (const depth of [-1, 0, 1, 2, 3, 4, 5]) {
    for (const mode of modes) cases.push({ graph, init: [0, 0], depth, mode, target: [1], second: [2], fair: false });
  }
  for (const mode of modes) cases.push({ graph: [], init: [], depth: 0, mode, target: [], second: [], fair: false });
  // Safety witnesses have the source's explicit stutter-closed precondition.
  for (const graph of [[[0, 1], [1, 2], [2]], [[0, 1, 2], [1], [2]]]) {
    for (const depth of [0, 1, 2, 3, 5]) for (const mode of ['safety', 'reaches']) {
      cases.push({ graph, init: [0], depth, mode, target: [0, 1], second: [], fair: false });
    }
  }
  for (const input of cases) {
    const result = spawnSync(oracle, ['graph', JSON.stringify(input)], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const expected = JSON.parse(result.stdout);
    const actual = JSON.parse(text(w.graphInvokeRender(json(input))));
    assert.deepEqual(actual, expected, JSON.stringify(input));
    if (actual.outcome.tag === 'refuted') {
      const { stem, loop } = actual.outcome;
      assert.ok(loop.length > 0);
      const path = [...stem, ...loop, loop[0]];
      for (let i = 1; i < path.length; i++) assert.ok(input.graph[path[i - 1]].includes(path[i]), `fabricated edge: ${JSON.stringify(input)}`);
    }
  }
  t.diagnostic(`${cases.length} differential model-checking cases`);
});
