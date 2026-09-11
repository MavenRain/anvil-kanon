#!/usr/bin/env node
import { load } from '../runtime/host.mjs';

const commands = {
  api: 'apiInvokeRender', 'api-reference': 'oracleInvokeRender', graph: 'graphInvokeRender',
  cluster: 'clusterFixtureRender', assurance: 'assuranceFixtureRender',
  'assurance-stateful': 'statefulAssuranceFixtureRender', 'assurance-vrs': 'vrsAssuranceFixtureRender',
  scenario: 'scenarioFixtureRender', intact: 'scenarioIntactRender', 'cluster-check': 'clusterCheckRender',
  'fault-check': 'faultCheckRender', proof: 'proofRender', runtime: 'runtimeRender',
  'exec-create': 'execCreateRender',
};
async function main() {
  const [command, ...args] = process.argv.slice(2);
  if (!command || command === '--help') {
    console.log('Usage: node bin/anvil.mjs operator [vrs|stateful|deployment] [desired]\n       node bin/anvil.mjs COMMAND < fixture.json\nCommands: ' + Object.keys(commands).join(', '));
    return 0;
  }
  const host = await load();
  const invoke = (name, input) => host.text(host.w[name](host.json(input)));
  if (command === 'operator') {
    const kind = args[0] ?? 'vrs'; const desired = Number(args[1] ?? 3);
    if (!['vrs', 'stateful', 'deployment'].includes(kind) || !Number.isSafeInteger(desired) || desired < 0) throw new TypeError('Expected a controller name and nonnegative exact desired count');
    const seed = { mode: kind === 'stateful' ? 'statefulFaults' : kind, desired, desireds: [], ordinals: [], existing: 0, fair: true, crash: false, drop: false, monkey: false, vct: kind === 'stateful' };
    const state = JSON.parse(invoke('scenarioFixtureRender', seed)).apiServer;
    const report = JSON.parse(invoke('runtimeRender', {
      mode: 'fixpoint', state, models: kind === 'deployment' ? ['deployment', 'vrs'] : [kind],
      policy: { spec: true, status: true, valid: true, transition: true, defaultStatus: { replicas: 0 } },
      namespace: 'ns', fuel: 1000, rounds: Math.max(10, desired * 2 + 4),
    }));
    const pods = report.state.resources.filter(x => x.obj.kind === 'Pod').length;
    const pvcs = report.state.resources.filter(x => x.obj.kind === 'PersistentVolumeClaim').length;
    const converged = report.result.ok?.converged === true && pods === desired && report.checks.every(Boolean);
    console.log(JSON.stringify({ controller: kind, desired, pods, pvcs, ...report.result.ok, requests: report.rpc, oracleAgreed: report.checks.every(Boolean), success: converged }, null, 2));
    return converged ? 0 : 1;
  }
  const name = commands[command]; if (!name) throw new TypeError(`Unknown command: ${command}`);
  const chunks = []; for await (const chunk of process.stdin) chunks.push(chunk);
  const parsed = host.parse(Buffer.concat(chunks).toString('utf8'));
  if (!parsed.ok) { console.error(JSON.stringify(parsed.error)); return 1; }
  const result = host.text(host.w[name](parsed.value));
  console.log(result); return result.startsWith('error: ') ? 1 : 0;
}
try { process.exitCode = await main(); }
catch (error) { console.error(error.message); process.exitCode = 1; }
