import { createHash } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const lines = (await readFile(join(root, 'final_test_manifest.csv'), 'utf8')).trim().split('\n');
const fields = lines.shift().split(',');
if (fields.join(',') !== 'filename,sha256,size_bytes,run_id,repository_sha,production_url') throw new Error('Unexpected manifest schema');
const parse = (line) => [...line.matchAll(/"((?:""|[^"])*)"(?:,|$)/g)].map((match) => match[1].replaceAll('""', '"'));
let count = 0;
for (const line of lines) {
  const row = parse(line);
  if (row.length !== fields.length || row[0].startsWith('/') || row[0].split('/').includes('..')) throw new Error('Invalid manifest path');
  const path = join(root, row[0]);
  const content = await readFile(path);
  if (createHash('sha256').update(content).digest('hex') !== row[1]) throw new Error(`SHA-256 mismatch: ${row[0]}`);
  if ((await stat(path)).size !== Number(row[2])) throw new Error(`File-size mismatch: ${row[0]}`);
  count++;
}
console.log(`EVIDENCE FILE COUNT: ${count}`);
console.log('HASH VERIFICATION: PASS');
