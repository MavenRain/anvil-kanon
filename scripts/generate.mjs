import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('..', import.meta.url));
for (const name of ['model', 'list-ops', 'json', 'codecs', 'resources', 'io', 'packs', 'cluster-types', 'cluster-wire', 'oracle-io', 'assurance', 'fault-wire', 'proof', 'oracle-wire', 'kernel-fixtures', 'defaults']) {
  const r = spawnSync('python3', ['-P', `scripts/generate-${name}.py`], { cwd: root, stdio: 'inherit' });
  if (r.error) throw r.error;
  if (r.status !== 0) process.exit(r.status ?? 1);
}
console.log('Regenerated source, codecs, fixtures and adapters.');
