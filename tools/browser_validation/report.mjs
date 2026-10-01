import { access, copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
if (!root || !runId) throw new Error('EVIDENCE_DIR and RUN_ID are required');
const load = async (name) => JSON.parse(await readFile(join(root, name), 'utf8'));
const environment = await load('test_environment.json');
const playwright = await load('raw_results.json');
const before = await load('logs/live_site_identity_start.log');
const after = await load('logs/live_site_identity_end.log');
if (environment.run_id !== runId || playwright.runId !== runId) throw new Error('Run ID mismatch');
if (playwright.responsive.length !== 64 || playwright.cross.length !== 32 || playwright.perf.length !== 80) throw new Error('Incomplete matrices');
const cross = playwright.cross;
const routes = ['/', '/companies', '/companies/ALI', '/companies/GLO', '/watchlist', '/compare', '/learn-stocks', '/about'];
const crossViewports = ['390x844', '1440x900'];
const expectedCross = new Set(['chromium', 'webkit'].flatMap((engine) => crossViewports.flatMap((viewport) => routes.map((route) => `${engine}|${route}|${viewport}`))));
const actualCross = cross.map((row) => `${row.browser_engine}|${row.route}|${row.viewport}`);
if (actualCross.length !== expectedCross.size || new Set(actualCross).size !== expectedCross.size || actualCross.some((key) => !expectedCross.has(key))) throw new Error('Duplicate, unexpected, or missing Chromium/WebKit cross-browser case');
const compatibility = [...playwright.responsive, ...cross];
const retryCases = compatibility.filter((row) => row.transport_retry_used === true);
const successfulRetries = retryCases.filter((row) => row.status === 'PASS');
const exhaustedRetries = retryCases.filter((row) => row.status !== 'PASS');
const escape = (value) => `"${String(value ?? '').replaceAll('"', '""').replaceAll('\n', ' ')}"`;
const csv = (fields, rows) => [fields.join(','), ...rows.map((row) => fields.map((field) => escape(row[field])).join(','))].join('\n') + '\n';
const crossFields = ['run_id','timestamp','browser','browser_engine','browser_version','route','viewport','navigation_start','response_received_ms','http_status','domcontentloaded_time_ms','document_ready_state','primary_landmark_visible_ms','usable_page_load_ms','window_load_time_ms','browser_navigation_error','primary_content_visible','horizontal_overflow','pageerror_count','console_error_count','critical_request_failure_count','status','notes','logical_case_id','transport_attempt_count','transport_retry_used','first_attempt_transport_status','final_document_http_status','usable_state_ms','assertion_status','final_status'];
await mkdir(join(root, 'logs'), { recursive: true });
try { await access(join(root, 'logs', 'playwright_cross_browser_results.csv')); }
catch { await copyFile(join(root, 'cross_browser_results.csv'), join(root, 'logs', 'playwright_cross_browser_results.csv')); }
await writeFile(join(root, 'cross_browser_results.csv'), csv(crossFields, cross));
const passed = (rows) => rows.filter((row) => row.status === 'PASS').length;
const groups = [
  ['Mobile responsive testing', playwright.responsive.filter((row) => row.viewport_category === 'mobile'), 16, 'responsive_test_results.csv'],
  ['Tablet responsive testing', playwright.responsive.filter((row) => row.viewport_category === 'tablet'), 16, 'responsive_test_results.csv'],
  ['Laptop/desktop browser testing', playwright.responsive.filter((row) => ['laptop','desktop'].includes(row.viewport_category)), 32, 'responsive_test_results.csv'],
  ['Cross-browser compatibility', cross, 32, 'cross_browser_results.csv'],
];
const valid = playwright.perf.filter((row) => row.status !== 'INVALID TEST');
const within = valid.filter((row) => row.within_5000ms === true).length;
const rate = valid.length ? 100 * within / valid.length : 0;
const times = valid.map((row) => Number(row.usable_page_load_ms)).filter(Number.isFinite).sort((a, b) => a - b);
const median = times.length ? (times[(times.length - 1) >> 1] + times[times.length >> 1]) / 2 : null;
const percentile = (p) => times.length ? times[Math.ceil(p * times.length) - 1] : null;
const perRoute = Object.fromEntries([...new Set(playwright.perf.map((row) => row.route))].map((route) => {
  const rows = valid.filter((row) => row.route === route);
  const wins = rows.filter((row) => row.within_5000ms === true).length;
  return [route, { valid_trials: rows.length, within_threshold_trials: wins, pass_rate_pct: rows.length ? 100 * wins / rows.length : null }];
}));
const performance = {
  run_id: runId, production_url: environment.production_url, planned_trials: 80, valid_trials: valid.length,
  threshold_ms: 5000, required_pass_rate_pct: 90, within_threshold_trials: within, overall_pass_rate_pct: rate,
  median_usable_load_ms: median, p90_usable_load_ms: percentile(.9), p95_usable_load_ms: percentile(.95),
  maximum_usable_load_ms: times.at(-1) ?? null,
  censored_timeout_trials: valid.filter((row) => String(row.notes).includes('censored lower bound')).length,
  per_route: perRoute,
};
await writeFile(join(root, 'performance_summary.json'), JSON.stringify(performance, null, 2) + '\n');
const summary = groups.map(([validation, rows, expected, evidence]) => ({
  validation, status: rows.length === expected && passed(rows) === expected ? 'PASS' : 'FAIL',
  measured_result: `${passed(rows)}/${expected} cases passed`, evidence,
}));
summary.push({ validation: 'Page-load/performance measurement', status: valid.length === 80 ? 'PASS' : 'FAIL', measured_result: `${valid.length}/80 valid trials`, evidence: 'performance_results.csv' });
summary.push({ validation: '90% within five-second performance threshold', status: valid.length === 80 && rate >= 90 ? 'PASS' : 'FAIL', measured_result: `${within}/${valid.length} (${rate.toFixed(2)}%) within 5.0 seconds`, evidence: 'performance_summary.json' });
const categories = summary.filter((row) => row.status === 'PASS').length;
const identityMatches = before.http_status === 200 && after.http_status === 200 && before.html_sha256 === after.html_sha256;
const eligible = categories === 6 && identityMatches;
await writeFile(join(root, 'browser_validation_summary.csv'), csv(['validation','status','measured_result','evidence'], summary));
const table = [
  '### Table XX. Browser-Level Validation', '', '| Validation | Status | Measured Result |', '|---|---|---|',
  ...summary.map((row) => `| ${row.validation} | ${row.status} | ${row.measured_result} |`), '',
  `Overall: ${categories}/6 categories (${(100 * categories / 6).toFixed(2)}% category pass rate) — ${eligible ? 'PASS' : 'FAIL'}.`, '',
  `Production URL: ${environment.production_url}. Repository SHA recorded by the harness: ${environment.repository_sha}. Run: ${runId}; started ${environment.test_start_timestamp}, ended ${after.timestamp}.`,
  'Eight routes were tested at mobile 390×844 and 412×915; tablet 768×1024 and 820×1180; laptop 1366×768 and 1440×900; desktop 1920×1080 and 2560×1440. Cross-browser viewports were 390×844 and 1440×900.',
  'The finalized cross-browser acceptance scope is Chromium and WebKit engine compatibility (16 cases each). WebKit is not labeled Safari. Firefox was used only in pre-final diagnostic evidence and is excluded because the project requirement specifies cross-browser compatibility without mandating Firefox; its earlier attempts and failures remain in research history.',
  `Responsive and compatibility cases permitted one clean-context retry only when the first attempt received no main document. First-attempt transport failures: ${retryCases.length}; successful retries: ${successfulRetries.length}; exhausted retries: ${exhaustedRetries.length}. Both attempts are retained in transport-attempt evidence. No performance trial was retried or replaced.`,
  `The unthrottled Chromium performance test measured 80 fresh-context usable-page loads at 1440×900. ${within}/${valid.length} (${rate.toFixed(2)}%) met the separate five-second threshold; the requirement was at least 90%.`,
  eligible ? 'The run met all six predefined technical categories and is eligible for the authoritative Chapter IV package after manifest verification.' : `The candidate met ${categories}/6 categories and MUST NOT be promoted as an authoritative 6/6 result.`,
  'Automated browser validation does not replace stakeholder UAT or subjective real-device usability evaluation.', '',
].join('\n');
await writeFile(join(root, 'TABLE_XX_BROWSER_LEVEL_VALIDATION.md'), table);
const byEngine = Object.fromEntries(['chromium','webkit'].map((engine) => [engine, `${passed(cross.filter((row) => row.browser_engine === engine))}/16`]));
const failures = [
  ...playwright.responsive.filter((row) => row.status !== 'PASS').map((row) => `Responsive ${row.route} ${row.viewport_width}×${row.viewport_height}: ${row.status}`),
  ...cross.filter((row) => row.status !== 'PASS').map((row) => `Cross-browser ${row.browser_engine} ${row.route} ${row.viewport}: ${row.status}`),
  ...playwright.perf.filter((row) => row.status !== 'PASS').map((row) => `Performance ${row.route} trial ${row.trial}: ${row.status}`),
];
const readme = [
  '# PSE Pulse Browser-Level Technical Validation', '',
  `Run ID: ${runId}  `, `Production URL: ${environment.production_url}  `, `Repository SHA: ${environment.repository_sha}  `,
  `Categories passed: ${categories}/6  `, `Category pass rate: ${(100 * categories / 6).toFixed(2)}%  `, `Overall browser-validation status: ${eligible ? 'PASS' : 'FAIL; do not promote'}.`, '',
  '## Responsive result', '', ...summary.slice(0, 3).map((row) => `- ${row.validation}: ${row.status}, ${row.measured_result}`), '',
  '## Cross-browser result', '', `- Chromium ${byEngine.chromium}; WebKit engine ${byEngine.webkit}; overall ${passed(cross)}/32.`,
  '- Firefox is excluded from finalized acceptance because the project requirement specifies cross-browser compatibility but does not mandate Firefox. Its pre-final diagnostic attempts and failures remain in research history. WebKit is not called Safari.', '',
  '## Bounded transport retries', '', `- First-attempt transport failures: ${retryCases.length}; successful transport retries: ${successfulRetries.length}; exhausted retries: ${exhaustedRetries.length}. Raw first and final attempts remain in transport-attempt evidence.`,
  '- Application, UI, JavaScript, and slow-performance results were never retried. The 80 performance trials were each measured once.', '',
  '## Performance result', '', `- Five-second performance result: ${within}/${valid.length} = ${rate.toFixed(2)}%. Requirement: at least 90%. Status: ${valid.length === 80 && rate >= 90 ? 'PASS' : 'FAIL'}.`,
  `- ${valid.length}/80 planned trials were valid; no replacement trials were used.`,
  `- Median ${median?.toFixed(2) ?? 'N/A'} ms; p90 ${percentile(.9)?.toFixed(2) ?? 'N/A'} ms; p95 ${percentile(.95)?.toFixed(2) ?? 'N/A'} ms; maximum ${times.at(-1)?.toFixed(2) ?? 'N/A'} ms. Timed-out elapsed values are lower bounds.`, '',
  '## Evidence boundary', '', `- Home-page HTML SHA-256 before/after: ${identityMatches ? 'MATCH' : 'MISMATCH'}; the public response does not independently establish a deployment Git SHA.`,
  '- Earlier pre-final runs and corrective-action records are retained under `docs/research-history/browser-validation/`.',
  '- Automated technical validation does not replace stakeholder UAT or subjective real-device usability evaluation.', '',
  '## Observed non-passes', '', ...(failures.length ? failures.map((line) => `- ${line}`) : ['- None.']), '',
].join('\n');
await writeFile(join(root, 'README.md'), readme);
console.log(JSON.stringify({ run_id: runId, categories_passed: categories, cross_browser: byEngine, valid_performance_trials: valid.length, within_five_seconds: within, identity_match: identityMatches, promotion_eligible: eligible }, null, 2));
