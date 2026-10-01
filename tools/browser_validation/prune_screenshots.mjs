import { createHash } from 'node:crypto';
import { readFile, readdir, rm, stat, writeFile, access } from 'node:fs/promises';
import { dirname, extname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const roots = [
  join(repo, 'backend/research-result/system_testing/browser_validation'),
  join(repo, 'docs/research-history/browser-validation'),
];
const mode = process.argv[2] ?? '--dry-run';
if (!['--dry-run', '--apply', '--verify'].includes(mode)) throw new Error('Use --dry-run, --apply, or --verify');
const imageExtension = (path) => ['.png', '.jpg', '.jpeg', '.webp', '.gif'].includes(extname(path).toLowerCase());
const manifestName = (path) => /(?:^|\/)(?:final_test_manifest|test_manifest)\.csv$/.test(path);
const pathPattern = /[^\s"'<>(),;]*?\.(?:png|jpe?g|webp|gif)\b/gi;
const policyText = 'Screenshots were intentionally excluded from repository storage to reduce repository size. Machine-readable CSV/JSON results and execution logs are the authoritative evidence. Screenshot path fields are blank; validation measurements and pass/fail results are unchanged.';

async function walk(root) {
  const found = [];
  async function visit(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`Refusing symlink inside evidence root: ${path}`);
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile()) found.push(path);
    }
  }
  await visit(root);
  return found;
}

function parseCsv(text, path) {
  const rows = [];
  let row = [], cell = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (char === ',' && !quoted) { row.push(cell); cell = ''; }
    else if (char === '\n' && !quoted) {
      row.push(cell.replace(/\r$/, ''));
      rows.push(row); row = []; cell = '';
    } else cell += char;
  }
  if (quoted) throw new Error(`Unclosed CSV quote: ${path}`);
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  if (!rows.length) throw new Error(`Empty CSV: ${path}`);
  const width = rows[0].length;
  if (rows.some((item) => item.length !== width)) throw new Error(`Inconsistent CSV field count: ${path}`);
  return rows;
}

function serializeCsv(rows) {
  const quote = (value) => `"${String(value).replaceAll('"', '""')}"`;
  return [rows[0].join(','), ...rows.slice(1).map((row) => row.map(quote).join(','))].join('\n') + '\n';
}

const scrub = (value) => {
  if (typeof value !== 'string' || !pathPattern.test(value)) { pathPattern.lastIndex = 0; return value; }
  pathPattern.lastIndex = 0;
  if (/^[^\s"'<>(),;]+\.(?:png|jpe?g|webp|gif)$/i.test(value)) return '';
  return value.replace(pathPattern, '[screenshot intentionally excluded]');
};

function scrubJson(value) {
  if (Array.isArray(value)) return value.map(scrubJson);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, scrubJson(item)]));
  return scrub(value);
}

async function sha(path) { return createHash('sha256').update(await readFile(path)).digest('hex'); }
const exists = async (path) => { try { await access(path); return true; } catch { return false; } };
function safeManifestTarget(manifest, name) {
  if (!name || name.startsWith('/') || name.split(/[\\/]/).includes('..')) throw new Error(`Unsafe manifest entry ${name} in ${manifest}`);
  const path = resolve(dirname(manifest), name);
  if (!path.startsWith(dirname(manifest) + sep)) throw new Error(`Manifest escapes its directory: ${name}`);
  return path;
}

async function regenerate(manifest) {
  const rows = parseCsv(await readFile(manifest, 'utf8'), manifest);
  if (!['filename', 'path'].includes(rows[0][0]) || rows[0].slice(1).join(',') !== 'sha256,size_bytes,run_id,repository_sha,production_url') throw new Error(`Unexpected manifest schema: ${manifest}`);
  const output = [rows[0]];
  let removedImages = 0, removedOtherMissing = 0;
  for (const row of rows.slice(1)) {
    const target = safeManifestTarget(manifest, row[0]);
    if (imageExtension(target)) { removedImages++; continue; }
    if (!(await exists(target))) { removedOtherMissing++; continue; }
    const details = await stat(target);
    output.push([row[0], await sha(target), String(details.size), ...row.slice(3)]);
  }
  await writeFile(manifest, serializeCsv(output));
  return { path: relative(repo, manifest), entries: output.length - 1, removedImages, removedOtherMissing };
}

async function verifyManifest(manifest) {
  const rows = parseCsv(await readFile(manifest, 'utf8'), manifest);
  if (!['filename', 'path'].includes(rows[0][0]) || rows[0].slice(1).join(',') !== 'sha256,size_bytes,run_id,repository_sha,production_url') throw new Error(`Unexpected manifest schema: ${manifest}`);
  for (const row of rows.slice(1)) {
    const target = safeManifestTarget(manifest, row[0]);
    if (!(await exists(target))) throw new Error(`Missing manifest file: ${target}`);
    if (await sha(target) !== row[1]) throw new Error(`SHA-256 mismatch: ${target}`);
    if ((await stat(target)).size !== Number(row[2])) throw new Error(`Size mismatch: ${target}`);
  }
  return rows.length - 1;
}

const all = (await Promise.all(roots.map(walk))).flat();
const images = all.filter(imageExtension);
const manifests = all.filter(manifestName).sort((a, b) => b.split(sep).length - a.split(sep).length || Number(a.includes('final_test_manifest')) - Number(b.includes('final_test_manifest')));
console.log(`Evidence images: ${images.length}; manifests: ${manifests.length}`);
if (mode === '--dry-run') {
  let csv = 0, json = 0, missingNonImages = 0;
  for (const path of all) {
    if (extname(path).toLowerCase() === '.csv') { parseCsv(await readFile(path, 'utf8'), path); csv++; }
    if (extname(path).toLowerCase() === '.json') { JSON.parse(await readFile(path, 'utf8')); json++; }
  }
  for (const manifest of manifests) {
    const rows = parseCsv(await readFile(manifest, 'utf8'), manifest);
    for (const row of rows.slice(1)) {
      const target = safeManifestTarget(manifest, row[0]);
      if (!imageExtension(target) && !(await exists(target))) missingNonImages++;
    }
  }
  console.log(`Parsed ${csv} CSV and ${json} JSON files; pre-existing missing non-image manifest entries: ${missingNonImages}. Dry run only; no files changed.`);
  process.exit(0);
}
if (mode === '--apply') {
  let editedCsv = 0, editedJson = 0, editedMarkdown = 0;
  for (const path of all) {
    if (manifestName(path) || imageExtension(path)) continue;
    const ext = extname(path).toLowerCase();
    if (ext === '.csv') {
      const original = await readFile(path, 'utf8');
      if (!/\.(?:png|jpe?g|webp|gif)\b/i.test(original)) continue;
      const rows = parseCsv(original, path);
      const changed = rows.map((row, index) => index === 0 ? row : row.map(scrub));
      await writeFile(path, serializeCsv(changed)); editedCsv++;
    } else if (ext === '.json') {
      const original = await readFile(path, 'utf8');
      if (!/\.(?:png|jpe?g|webp|gif)\b/i.test(original)) continue;
      await writeFile(path, JSON.stringify(scrubJson(JSON.parse(original)), null, 2) + '\n'); editedJson++;
    } else if (ext === '.md') {
      const original = await readFile(path, 'utf8');
      let updated = original.replace(pathPattern, '[screenshot intentionally excluded]')
        .replaceAll('screenshots/responsive/failures/', 'machine-readable failure records and logs')
        .replaceAll('`screenshots/`, ', '')
        .replaceAll('failure screenshots remain in machine-readable failure records and logs', 'failure observations remain in machine-readable records and logs')
        .replaceAll(', and screenshots are enumerated in `original_timeout_inventory.csv`', ', and outcomes are enumerated in `original_timeout_inventory.csv`')
        .replaceAll('with dated raw records and screenshots', 'with dated raw records; screenshots were later excluded from repository storage')
        .replaceAll('; screenshots were captured.', '; screenshots were captured at the time and later excluded from repository storage.')
        .replaceAll('- Evidence: [screenshot intentionally excluded]', '- Evidence: see the corresponding machine-readable result row and execution log; screenshot intentionally excluded');
      if (path.endsWith('README.md') && !updated.includes(policyText)) updated = updated.trimEnd() + '\n\n' + policyText + '\n';
      if (updated !== original) { await writeFile(path, updated); editedMarkdown++; }
    }
  }
  for (const path of images) await rm(path);
  const regenerated = [];
  for (const manifest of manifests) regenerated.push(await regenerate(manifest));
  console.log(JSON.stringify({ removed_images: images.length, edited_csv: editedCsv, edited_json: editedJson, edited_markdown: editedMarkdown, regenerated }, null, 2));
}
const remaining = (await Promise.all(roots.map(walk))).flat();
if (remaining.some(imageExtension)) throw new Error('Image files remain in evidence roots');
for (const path of remaining.filter((item) => ['.csv', '.json', '.md'].includes(extname(item).toLowerCase()) && !manifestName(item))) {
  if (/\.(?:png|jpe?g|webp|gif)\b/i.test(await readFile(path, 'utf8'))) throw new Error(`Broken screenshot reference remains: ${path}`);
}
let entries = 0;
for (const manifest of manifests) entries += await verifyManifest(manifest);
console.log(`Verified ${entries} SHA-256 manifest entries across ${manifests.length} manifests; no image files or image references remain.`);
