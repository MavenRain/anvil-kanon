import { cpSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const inventory = JSON.parse(readFileSync(resolve(root, 'port-inventory.json'), 'utf8'));
const source = process.env.ANVIL_OCAML_ROOT ?? resolve(root, '../anvil-ocaml');
const target = resolve(root, 'build/oracle-source');
function run(command, args, capture = false) {
  const result = spawnSync(command, args, { encoding: 'utf8', stdio: capture ? 'pipe' : 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} exited ${result.status}: ${result.stderr ?? ''}`);
  return result.stdout?.trim();
}
mkdirSync(resolve(root, 'build'), { recursive: true });
if (!existsSync(target)) run('git', ['clone', '--local', '--no-hardlinks', source, target]);
const revision = run('git', ['-C', target, 'rev-parse', 'HEAD'], true);
if (revision !== inventory.revision) throw new Error(`Oracle revision ${revision} differs from pinned ${inventory.revision}`);
const trackedChanges = run('git', ['-C', target, 'status', '--porcelain', '--untracked-files=no'], true);
if (trackedChanges) throw new Error('The oracle has modified tracked source files');
mkdirSync(resolve(target, 'port_oracle'), { recursive: true });
for (const file of ['dune', 'port_oracle.ml', 'io_json.ml', 'api_oracle.ml', 'graph_oracle.ml', 'cluster_oracle.ml', 'assurance_oracle.ml', 'scenario_oracle.ml', 'checker_oracle.ml', 'fault_oracle.ml', 'proof_oracle.ml', 'runtime_oracle.ml', 'kernel_oracle.ml', 'defaults_oracle.ml', 'action_oracle.ml']) cpSync(resolve(root, 'oracle', file), resolve(target, 'port_oracle', file));
run('opam', ['exec', `--switch=${process.env.ANVIL_OPAM_SWITCH ?? 'anvil-ocaml'}`, '--',
  'dune', 'build', '--root', target, 'port_oracle/port_oracle.exe']);
console.log(`Built differential oracle at ${revision}`);
