import { createHash } from 'node:crypto';
import { copyFile, mkdir, readFile, stat } from 'node:fs/promises';
import { dirname, join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const archive = join(root, 'initial_run');
try {
  await stat(archive);
  throw new Error(`Refusing to overwrite existing initial archive: ${archive}`);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

const manifest = await readFile(join(root, 'test_manifest.csv'), 'utf8');
const rows = manifest.trim().split('\n').slice(1);
const entries = rows.map((line) => {
  const columns = [...line.matchAll(/"((?:""|[^"])*)"(?:,|$)/g)]
    .map((match) => match[1].replaceAll('""', '"'));
  if (columns.length !== 6) throw new Error(`Malformed original manifest row: ${line}`);
  return { name: columns[0], sha256: columns[1] };
});
for (const entry of entries) {
  const source = join(root, entry.name);
  const actual = createHash('sha256').update(await readFile(source)).digest('hex');
  if (actual !== entry.sha256) throw new Error(`Original evidence hash mismatch: ${entry.name}`);
}
await mkdir(archive, { recursive: true });
for (const entry of entries) {
  const destination = join(archive, entry.name);
  await mkdir(dirname(destination), { recursive: true });
  await copyFile(join(root, entry.name), destination);
  const copied = createHash('sha256').update(await readFile(destination)).digest('hex');
  if (copied !== entry.sha256) throw new Error(`Copied evidence hash mismatch: ${entry.name}`);
}
await copyFile(join(root, 'test_manifest.csv'), join(archive, 'test_manifest.csv'));
console.log(`Initial run preserved byte-for-byte: ${entries.length} manifested files + original manifest`);
