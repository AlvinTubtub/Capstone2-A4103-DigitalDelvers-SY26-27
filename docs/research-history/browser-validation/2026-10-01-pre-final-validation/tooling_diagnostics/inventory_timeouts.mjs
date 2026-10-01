import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
if (!root) throw new Error('EVIDENCE_DIR is required');
const initial = join(root, 'initial_run');
const output = join(root, 'retest');
const parseCsv = (input) => {
  const [header, ...lines] = input.trim().split('\n');
  const names = header.split(',');
  return lines.map((line) => {
    const values = [...line.matchAll(/"((?:""|[^"])*)"(?:,|$)/g)]
      .map((match) => match[1].replaceAll('""', '"'));
    if (values.length !== names.length) throw new Error(`Malformed CSV row: ${line}`);
    return Object.fromEntries(names.map((name, index) => [name, values[index]]));
  });
};
const csvEscape = (value) => `"${String(value ?? '').replaceAll('"', '""').replaceAll('\n', ' ')}"`;
const files = [
  ['responsive_test_results.csv', 'responsive'],
  ['cross_browser_results.csv', 'cross-browser'],
  ['performance_results.csv', 'performance'],
];
const environment = JSON.parse(await readFile(join(initial, 'test_environment.json'), 'utf8'));
const raw = JSON.parse(await readFile(join(initial, 'raw_results.json'), 'utf8'));
const records = [];
for (const [file, category] of files) {
  const rows = parseCsv(await readFile(join(initial, file), 'utf8'));
  for (const row of rows) {
    if (!/timeout|timed out|ERR_TIMED_OUT/i.test(row.notes ?? '')) continue;
    const viewport = category === 'cross-browser' ? row.viewport?.split('x') : null;
    records.push({
      timeout_id: `TOUT-${String(records.length + 1).padStart(3, '0')}`,
      source_file: `initial_run/${file}`,
      test_category: category,
      browser: row.browser_engine || row.browser,
      browser_version: row.browser_version || environment[`${row.browser}_version`] || '',
      route: row.route,
      viewport_width: row.viewport_width || viewport?.[0] || '',
      viewport_height: row.viewport_height || viewport?.[1] || '',
      original_timestamp: row.timestamp,
      original_timeout_ms: 30000,
      original_status: row.status,
      original_error: row.notes,
      original_screenshot: row.screenshot || '',
      retest_required: true,
    });
  }
}
const originalDefects = await readFile(join(initial, 'DEFECTS_FOUND.md'), 'utf8');
const defectCount = [...originalDefects.matchAll(/^## OBS-\d+:/gm)].length;
if (records.length !== defectCount) throw new Error(`CSV timeout count ${records.length} differs from original defect observations ${defectCount}`);
if (records.length !== raw.responsive.filter((row) => /timeout|timed out/i.test(row.notes)).length + raw.cross.filter((row) => /timeout|timed out/i.test(row.notes)).length + raw.perf.filter((row) => /timeout|timed out/i.test(row.notes)).length) throw new Error('CSV and raw JSON timeout counts differ');
await mkdir(output, { recursive: true });
const fields = ['timeout_id','source_file','test_category','browser','browser_version','route','viewport_width','viewport_height','original_timestamp','original_timeout_ms','original_status','original_error','original_screenshot','retest_required'];
await writeFile(join(output, 'original_timeout_inventory.csv'), [fields.join(','), ...records.map((record) => fields.map((field) => csvEscape(record[field])).join(','))].join('\n') + '\n');
for (const category of ['responsive','cross-browser','performance']) console.log(`${category} timeouts: ${records.filter((record)=>record.test_category===category).length}`);
console.log(`Total unique timeout observations: ${records.length}`);
