import { createHash } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const parse = (line) => [...line.matchAll(/"((?:""|[^"])*)"(?:,|$)/g)].map((match)=>match[1].replaceAll('""','"'));

async function verify(manifestName, prefix, pathColumn) {
  const lines=(await readFile(join(root,manifestName),'utf8')).trim().split('\n');
  const headers=lines[0].split(',');
  const nameIndex=headers.indexOf(pathColumn);
  const hashIndex=headers.indexOf('sha256');
  const sizeIndex=headers.indexOf('size_bytes');
  if (nameIndex<0||hashIndex<0||sizeIndex<0) throw new Error(`Malformed ${manifestName}`);
  let count=0;
  for (const line of lines.slice(1)) {
    const row=parse(line);
    if (row.length!==headers.length) throw new Error(`Bad manifest row in ${manifestName}`);
    const target=join(root,prefix,row[nameIndex]);
    const content=await readFile(target);
    if (createHash('sha256').update(content).digest('hex')!==row[hashIndex]) throw new Error(`SHA-256 mismatch: ${target}`);
    if ((await stat(target)).size!==Number(row[sizeIndex])) throw new Error(`Size mismatch: ${target}`);
    count++;
  }
  return count;
}

const initial=await verify('initial_run/test_manifest.csv','initial_run','filename');
const final=await verify('final_test_manifest.csv','','path');
console.log(`Manifest verification PASS: initial=${initial} files; final=${final} files`);
