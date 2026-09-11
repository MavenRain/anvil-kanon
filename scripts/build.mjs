import { mkdirSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const kanon = process.env.KANON_ROOT ?? resolve(root, '../kanon');
const compiler = process.env.KANON_BIN ?? resolve(kanon, '_build/default/bin/kanon.exe');
const manifest = JSON.parse(readFileSync(resolve(root, 'modules.json'), 'utf8'));
const modelExports = JSON.parse(readFileSync(resolve(root, 'model-exports.json'), 'utf8'));
const codecExports = JSON.parse(readFileSync(resolve(root, 'codec-exports.json'), 'utf8'));
const packExports = JSON.parse(readFileSync(resolve(root, 'pack-exports.json'), 'utf8'));
mkdirSync(resolve(root, 'build'), { recursive: true });
const args = ['build', ...manifest.sources.map(p => resolve(root, p)),
  '-o', resolve(root, 'build/anvil.wasm'),
  ...[...manifest.exports, ...modelExports, ...codecExports, ...packExports].flatMap(name => ['--export', name])];
const result = spawnSync(compiler, args, { stdio: 'inherit' });
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
