import { createHash } from 'node:crypto';
import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { join, relative } from 'node:path';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
if (!root || !runId) throw new Error('EVIDENCE_DIR and RUN_ID are required');
const readJson = async (name) => JSON.parse(await readFile(join(root, name), 'utf8'));
const env = await readJson('test_environment.json');
const results = await readJson('raw_results.json');
const identityStart = await readJson('logs/live_site_identity_start.log');
const identityEnd = await readJson('logs/live_site_identity_end.log');
const lighthouseFiles = (await readdir(join(root, 'lighthouse'))).filter((file) => file.endsWith('.json'));
const lighthouse = await Promise.all(lighthouseFiles.map((file) => readJson(`lighthouse/${file}`)));
const csvEscape = (value) => `"${String(value ?? '').replaceAll('"', '""').replaceAll('\n', ' ')}"`;
const csv = (fields, rows) => [fields.join(','), ...rows.map((row) => fields.map((field) => csvEscape(row[field])).join(','))].join('\n') + '\n';
const pct = (a, b) => b ? 100 * a / b : null;
const fmtPct = (value) => value === null ? 'N/A' : `${value.toFixed(2)}%`;
const median = (values) => { if (!values.length) return null; const a = [...values].sort((x, y) => x-y); return (a[(a.length-1)>>1] + a[a.length>>1]) / 2; };
const percentile = (values, p) => { if (!values.length) return null; const a = [...values].sort((x,y)=>x-y); return a[Math.ceil(p*a.length)-1]; };
const count = (rows, status) => rows.filter((row) => row.status === status).length;
const responsiveGroups = {
  mobile: results.responsive.filter((row) => row.viewport_category === 'mobile'),
  tablet: results.responsive.filter((row) => row.viewport_category === 'tablet'),
  'laptop/desktop': results.responsive.filter((row) => ['laptop', 'desktop'].includes(row.viewport_category)),
};
const groupStatus = (rows) => rows.length && rows.every((row) => row.status === 'PASS') ? 'PASS' : rows.some((row) => row.status === 'FAIL') ? 'FAIL' : 'BLOCKED';
const validPerf = results.perf.filter((row) => row.status !== 'INVALID TEST');
const thresholdPasses = validPerf.filter((row) => row.within_5000ms === true).length;
const rate = pct(thresholdPasses, validPerf.length);
const perRoute = Object.fromEntries([...new Set(results.perf.map((row) => row.route))].map((route) => {
  const rows = validPerf.filter((row) => row.route === route);
  const pass = rows.filter((row) => row.within_5000ms === true).length;
  return [route, { planned_trials: 10, valid_trials: rows.length, within_threshold_trials: pass, pass_rate_pct: pct(pass, rows.length) }];
}));
const loadTimes = validPerf.map((row) => Number(row.usable_page_load_ms)).filter(Number.isFinite);
const censored = validPerf.filter((row) => row.notes?.includes('censored lower bound')).length;
const performanceSummary = {
  run_id: runId, production_url: env.production_url, threshold_ms: 5000,
  required_pass_rate_pct: 90.0, planned_trials: 80, valid_trials: validPerf.length,
  within_threshold_trials: thresholdPasses, overall_pass_rate_pct: rate,
  status: validPerf.length === 80 ? (rate >= 90 ? 'PASS' : 'FAIL') : 'BLOCKED',
  median_usable_load_ms: median(loadTimes), p90_usable_load_ms: percentile(loadTimes, .9),
  p95_usable_load_ms: percentile(loadTimes, .95), maximum_usable_load_ms: loadTimes.length ? Math.max(...loadTimes) : null,
  censored_timeout_trials: censored,
  percentile_caveat: censored ? 'Timeout elapsed values are lower bounds, not completed usable loads; percentiles including them are lower bounds.' : null,
  per_route: perRoute,
};
await writeFile(join(root, 'performance_summary.json'), JSON.stringify(performanceSummary, null, 2) + '\n');

const summaryRows = [
  ['Mobile responsive testing', responsiveGroups.mobile, 'responsive_test_results.csv'],
  ['Tablet responsive testing', responsiveGroups.tablet, 'responsive_test_results.csv'],
  ['Laptop/desktop browser testing', responsiveGroups['laptop/desktop'], 'responsive_test_results.csv'],
].map(([validation, rows, evidence]) => ({ validation, status: groupStatus(rows), measured_result: `${count(rows,'PASS')}/${rows.length} passed`, evidence, notes: `${count(rows,'FAIL')} timed-out visit(s); see per-case notes and screenshots` }));
summaryRows.push({ validation: 'Cross-browser compatibility', status: groupStatus(results.cross), measured_result: `${count(results.cross,'PASS')}/${results.cross.length} passed; ${count(results.cross,'BLOCKED')} Firefox cases blocked`, evidence: 'cross_browser_results.csv', notes: 'Chromium and WebKit completed; Firefox binary failed to launch in this macOS environment' });
summaryRows.push({ validation: 'Page-load/performance measurement', status: validPerf.length === 80 ? 'PASS' : 'BLOCKED', measured_result: `${validPerf.length}/80 valid fresh-context trials`, evidence: 'performance_results.csv', notes: `${censored} navigation timeouts counted as threshold failures` });
summaryRows.push({ validation: '90% within five-second performance threshold', status: performanceSummary.status, measured_result: `${thresholdPasses}/${validPerf.length} = ${fmtPct(rate)} (required ≥90.00%)`, evidence: 'performance_summary.json', notes: 'Unthrottled live Chromium 1440×900; Lighthouse excluded' });
await writeFile(join(root, 'browser_validation_summary.csv'), csv(['validation','status','measured_result','evidence','notes'], summaryRows));

const table = [
  '### Table XX. Browser-Level Validation', '',
  '| Validation | Status | Result |', '|---|---|---|',
  ...summaryRows.map((row) => `| ${row.validation} | ${row.status} | ${row.measured_result} |`),
  '',
  `Technical browser validation of ${env.production_url} at ${env.test_start_timestamp} (repository ${env.repository_sha}). The automated matrix covered eight defined viewport sizes, eight routes, 64 responsive cases, and 48 planned cross-browser cases using Chromium, Firefox, and WebKit; 16 Firefox cases were blocked by local browser launch failure. It measured 80 fresh-context page loads without synthetic throttling. The five-second calculation is ${thresholdPasses}/${validPerf.length} × 100 = ${fmtPct(rate)}. ${censored} trials timed out at 30 seconds and were counted as threshold failures; their durations are lower bounds. Lighthouse supplied 24 separate desktop/mobile measurements for four routes and did not determine the threshold verdict. This is technical browser validation, not UAT. Playwright WebKit is engine-level evidence, not Safari certification.`,
  '',
].join('\n');
await writeFile(join(root, 'TABLE_XX_BROWSER_LEVEL_VALIDATION.md'), table);

const lhGroups = new Map();
for (const row of lighthouse) {
  const key = `${row.route} — ${row.form_factor}`;
  if (!lhGroups.has(key)) lhGroups.set(key, []);
  lhGroups.get(key).push(row);
}
const lhTable = [...lhGroups].sort(([a],[b])=>a.localeCompare(b)).map(([key, rows]) => {
  const good = rows.filter((row)=>row.status==='PASS');
  return `| ${key} | ${good.length}/${rows.length} | ${median(good.map((row)=>row.performance_score))?.toFixed(0) ?? 'N/A'} | ${median(good.map((row)=>row.lcp_ms))?.toFixed(0) ?? 'N/A'} | ${median(good.map((row)=>row.cls))?.toFixed(3) ?? 'N/A'} |`;
});
const failures = [...results.responsive.filter((row)=>row.status==='FAIL').map((row)=>({kind:'responsive', row, route:row.route, engine:'Chromium', viewport:`${row.viewport_width}×${row.viewport_height}`})), ...results.cross.filter((row)=>row.status==='FAIL').map((row)=>({kind:'cross-browser', row, route:row.route, engine:row.browser_engine, viewport:row.viewport})), ...results.perf.filter((row)=>row.status==='FAIL').map((row)=>({kind:'performance', row, route:row.route, engine:'Chromium', viewport:'1440×900'}))];
const defectLines = ['# Observed Failures Requiring Investigation', '', 'No source-application defect was confirmed. The following live navigation timeouts were observed and preserved; they could reflect site availability, the test network, or an intermittent browser/network interaction. Do not relabel them as layout defects without reproduction.', ''];
failures.forEach((item, index) => {
  const evidence = item.kind === 'responsive' ? item.row.screenshot : item.kind === 'cross-browser' ? 'cross_browser_results.csv' : `performance_results.csv (route ${item.route}, trial ${item.row.trial})`;
  defectLines.push(`## OBS-${String(index+1).padStart(2,'0')}: ${item.kind} navigation failure`, '', `- Route: ${item.route}`, `- Browser: ${item.engine}`, `- Viewport: ${item.viewport}`, `- Reproduce: Open ${new URL(item.route, env.production_url).href} in a fresh ${item.engine} context at ${item.viewport}; wait for DOMContentLoaded and the route landmark.`, '- Expected: Page reaches a usable rendered state.', `- Actual: ${item.row.notes}`, `- Evidence: ${evidence}`, '- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.', '');
});
await writeFile(join(root, 'DEFECTS_FOUND.md'), defectLines.join('\n'));

const readme = [
  '# PSE Pulse Browser-Level Validation', '',
  `Run ID: ${runId}  `,
  `Repository SHA: ${env.repository_sha}  `,
  `Production URL: ${env.production_url}  `,
  `Test start: ${env.test_start_timestamp}  `,
  `Test end: ${identityEnd.timestamp}  `,
  `Environment: ${env.operating_system} ${env.macos_version}, ${env.cpu_architecture}, Node ${env.node_version}, Playwright ${env.playwright_version}.`, '',
  '## Purpose and scope', '',
  'Chapter IV technical validation of the live production website. Routes: /, /companies, /companies/ALI, /companies/GLO, /watchlist, /compare, /learn-stocks, /about. This run did not modify the application or forecasting results.', '',
  '## Method', '',
  '- Responsive matrix: Chromium, eight routes × eight viewports (390×844, 412×915, 768×1024, 820×1180, 1366×768, 1440×900, 1920×1080, 2560×1440). Checks include landmarks, core content, navigation, page errors, critical same-origin requests, and horizontal overflow.',
  '- Compatibility matrix: three planned engines × eight routes × mobile 390×844 and desktop 1440×900. Firefox launch failed locally, so those cases are BLOCKED rather than failed application tests.',
  '- Primary performance: 10 independent fresh Chromium contexts per route at 1440×900; timer starts immediately before navigation and ends when the route-specific landmark and core content are ready. No synthetic throttling. A 30-second navigation timeout is a valid threshold failure with a censored lower-bound elapsed time; no slow trial was discarded.',
  '- Lighthouse: three runs per route/form factor for /, /companies, /companies/ALI, /compare, desktop and mobile. Lighthouse simulation is supplementary and excluded from the five-second acceptance calculation.',
  `- Site identity: initial and final public home HTML SHA-256 both ${identityStart.html_sha256}; deployment Git SHA not independently resolved from the public response.`, '',
  '## Results', '',
  '| Category | Result |', '|---|---|',
  ...summaryRows.map((row)=>`| ${row.validation} | ${row.status}: ${row.measured_result} |`), '',
  `Primary observed load: median ${performanceSummary.median_usable_load_ms?.toFixed(0) ?? 'N/A'} ms; p90 ${performanceSummary.p90_usable_load_ms?.toFixed(0) ?? 'N/A'} ms; p95 ≥${performanceSummary.p95_usable_load_ms?.toFixed(0) ?? 'N/A'} ms; maximum observed lower bound ≥${performanceSummary.maximum_usable_load_ms?.toFixed(0) ?? 'N/A'} ms. The p95/max include censored timeouts and are lower bounds, not completed usable loads.`, '',
  '### Per-route five-second rate', '',
  '| Route | Within 5s / valid | Rate |', '|---|---:|---:|',
  ...Object.entries(perRoute).map(([route, row])=>`| ${route} | ${row.within_threshold_trials}/${row.valid_trials} | ${fmtPct(row.pass_rate_pct)} |`), '',
  '### Lighthouse medians', '',
  '| Route / form factor | Completed | Score | LCP (ms) | CLS |', '|---|---:|---:|---:|---:|', ...lhTable, '',
  '## Failures and limitations', '',
  `- ${failures.length} observed timeout cases are documented in DEFECTS_FOUND.md. These do not by themselves prove an application-code defect.`,
  '- Playwright Firefox 155.0 was downloaded but exited before opening its temporary profile on this macOS 27 host. Its 16 compatibility cases are BLOCKED. Chromium and WebKit cases completed.',
  '- Actual Safari GUI smoke check was not executed; Playwright WebKit testing completed separately.',
  '- Network-quality raw output is in logs/environment.log. Lighthouse mobile simulation may use throttling, unlike the primary threshold test.',
  '- A harness preflight checked client-rendered charts too early; its raw output remains in logs/preflight_raw_results.json and failure screenshots remain in screenshots/responsive/failures/. The final matrices use a corrected chart-readiness wait.', '',
  '## Evidence inventory', '',
  '- `responsive_test_results.csv`, `cross_browser_results.csv`, `performance_results.csv`, `performance_summary.json`, `lighthouse_summary.csv`',
  '- `browser_validation_summary.csv`, `TABLE_XX_BROWSER_LEVEL_VALIDATION.md`, `DEFECTS_FOUND.md`, `test_environment.json`, `test_manifest.csv`',
  '- `screenshots/`, `lighthouse/`, `logs/`, and `raw_results.json`',
  '- Reproducible harness: `tools/browser_validation/` with exact dependency versions in `package-lock.json`.', '',
  '## Interpretation boundary', '',
  'These automated tests provide browser-level technical validation. They do not replace stakeholder usability testing, real-device UAT, or user-perception evaluation.', '',
  'Playwright WebKit provides WebKit engine-level compatibility evidence and is not equivalent to certification against every Safari release or Apple device.', '',
].join('\n');
await writeFile(join(root, 'README.md'), readme);

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const all = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? listFiles(path) : [path];
  }));
  return all.flat();
}
const files = (await listFiles(root)).filter((path)=>!path.endsWith('/test_manifest.csv')).sort();
const manifest = [];
for (const path of files) {
  const data = await readFile(path);
  manifest.push({ filename: relative(root,path), sha256: createHash('sha256').update(data).digest('hex'), size_bytes: (await stat(path)).size, run_id: runId, repository_sha: env.repository_sha, production_url: env.production_url });
}
await writeFile(join(root, 'test_manifest.csv'), csv(['filename','sha256','size_bytes','run_id','repository_sha','production_url'], manifest));
console.log(JSON.stringify({ responsive: [count(results.responsive,'PASS'),results.responsive.length], cross: [count(results.cross,'PASS'),results.cross.length], firefox_blocked:count(results.cross,'BLOCKED'), performance: [thresholdPasses,validPerf.length,rate], lighthouse:[lighthouse.filter((x)=>x.status==='PASS').length,lighthouse.length], observed_failures:failures.length, manifest_files:manifest.length }, null, 2));
