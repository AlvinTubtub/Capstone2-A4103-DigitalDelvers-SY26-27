import { spawnSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const started = new Date().toISOString();
const run = spawnSync('npx', ['playwright', 'install', 'firefox'], {
  encoding: 'utf8', timeout: 180000, maxBuffer: 10 * 1024 * 1024,
});
const output = [
  `Started: ${started}`,
  '$ npx playwright install firefox',
  `Exit status: ${run.status ?? 'none'}`,
  `Signal: ${run.signal ?? 'none'}`,
  `Error: ${run.error?.message ?? 'none'}`,
  `STDOUT:\n${run.stdout ?? ''}`,
  `STDERR:\n${run.stderr ?? ''}`,
  `Completed: ${new Date().toISOString()}`,
].join('\n');
await mkdir(join(root, 'retest', 'logs'), { recursive: true });
await writeFile(join(root, 'retest', 'logs', 'firefox_install.log'), output + '\n');
console.log(output.slice(0, 1200));
if (run.status !== 0) process.exitCode = 1;
