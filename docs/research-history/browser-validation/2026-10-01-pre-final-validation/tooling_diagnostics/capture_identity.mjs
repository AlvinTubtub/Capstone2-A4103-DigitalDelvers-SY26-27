import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
const label = process.argv[2];
if (!root || !label || !/^[a-z0-9_-]+$/.test(label)) throw new Error('Usage: EVIDENCE_DIR=... node capture_identity.mjs label');
const output = join(root, 'retest', 'logs', `live_site_${label}.log`);
await mkdir(dirname(output), { recursive: true });
const response = await fetch('https://pse-pulse.vercel.app/', { redirect: 'follow' });
const html = await response.text();
const identity = {
  timestamp: new Date().toISOString(),
  request_url: 'https://pse-pulse.vercel.app/',
  final_url: response.url,
  http_status: response.status,
  headers: Object.fromEntries(response.headers),
  html_sha256: createHash('sha256').update(html).digest('hex'),
  html_bytes: Buffer.byteLength(html),
  deployment_sha_note: 'Public response does not independently identify a Git deployment SHA',
};
await writeFile(output, JSON.stringify(identity, null, 2) + '\n');
console.log(`${label}: HTTP ${identity.http_status}; SHA-256 ${identity.html_sha256}`);
