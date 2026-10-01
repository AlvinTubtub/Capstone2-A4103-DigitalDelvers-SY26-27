import { createHash } from 'node:crypto';
import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { basename, join, relative } from 'node:path';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
if (!root || !runId) throw new Error('EVIDENCE_DIR and RUN_ID are required');
const environment = JSON.parse(await readFile(join(root, 'test_environment.json'), 'utf8'));
if (environment.run_id !== runId) throw new Error('Run ID mismatch');
async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (await Promise.all(entries.map(async (entry) => entry.isDirectory() ? files(join(directory, entry.name)) : [join(directory, entry.name)]))).flat();
}
const all = (await files(root)).filter((path) => basename(path) !== '.DS_Store' && basename(path) !== 'final_test_manifest.csv').sort();
const fields = ['filename','sha256','size_bytes','run_id','repository_sha','production_url'];
const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
const rows = [];
for (const path of all) {
  const content = await readFile(path);
  rows.push({ filename: relative(root, path), sha256: createHash('sha256').update(content).digest('hex'), size_bytes: (await stat(path)).size, run_id: runId, repository_sha: environment.repository_sha, production_url: environment.production_url });
}
const csv = [fields.join(','), ...rows.map((row) => fields.map((field) => escape(row[field])).join(','))].join('\n') + '\n';
await writeFile(join(root, 'final_test_manifest.csv'), csv, { flag: 'wx' });
console.log(`EVIDENCE FILE COUNT: ${rows.length}`);
