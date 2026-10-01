import { createHash } from 'node:crypto';
import { readFile, writeFile, readdir, stat, copyFile, mkdir } from 'node:fs/promises';
import { basename, join, relative } from 'node:path';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
if (!root || !runId) throw new Error('EVIDENCE_DIR and RUN_ID are required');
const final = join(root, 'final_run');
const json = async (path) => JSON.parse(await readFile(path, 'utf8'));
const raw = await json(join(final, 'raw_results.json'));
const firefoxRaw = await json(join(final, 'firefox_cross_browser_results.raw.json'));
const identityBefore = await json(join(root,'retest','logs','live_site_pre_final.log'));
const identityAfter = await json(join(root,'retest','logs','live_site_post_final.log'));
const identityMatch = identityBefore.http_status===200 && identityAfter.http_status===200 && identityBefore.html_sha256===identityAfter.html_sha256;
const firefox = firefoxRaw.map(({ row }) => row);
if (raw.runId !== runId || firefox.length !== 16 || raw.responsive.length !== 64 || ![32,48].includes(raw.cross.length) || raw.perf.length !== 80) throw new Error('Incomplete final matrices');
if (firefox.some((row) => row.run_id !== runId)) throw new Error('Firefox run ID mismatch');
const cross = [...raw.cross.filter((row)=>row.browser_engine!=='firefox'), ...firefox];
const fields = ['run_id','timestamp','browser_engine','browser_version','route','viewport','http_status','primary_content_visible','horizontal_overflow','pageerror_count','console_error_count','critical_request_failure_count','status','notes'];
const escape = (value) => `"${String(value ?? '').replaceAll('"','""').replaceAll('\n',' ')}"`;
const csv = (columns, rows) => [columns.join(','), ...rows.map((row) => columns.map((column) => escape(row[column])).join(','))].join('\n')+'\n';
await mkdir(join(final,'logs'), { recursive:true });
if (raw.cross.length===32) await copyFile(join(final,'cross_browser_results.csv'),join(final,'logs','playwright_cross_browser_results.csv'));
await writeFile(join(final,'cross_browser_results.csv'),csv(fields,cross));
await writeFile(join(final,'raw_results.json'),JSON.stringify({...raw,cross,firefox_automation:'Installed Mozilla Firefox 157.0 via isolated LaunchServices and Selenium/WebDriver'},null,2)+'\n');

const passed = (rows) => rows.filter((row)=>row.status==='PASS').length;
const groups = [
  {name:'Mobile responsive testing',rows:raw.responsive.filter((row)=>row.viewport_category==='mobile'),expected:16,evidence:'final_run/responsive_test_results.csv'},
  {name:'Tablet responsive testing',rows:raw.responsive.filter((row)=>row.viewport_category==='tablet'),expected:16,evidence:'final_run/responsive_test_results.csv'},
  {name:'Laptop/desktop browser testing',rows:raw.responsive.filter((row)=>['laptop','desktop'].includes(row.viewport_category)),expected:32,evidence:'final_run/responsive_test_results.csv'},
  {name:'Cross-browser compatibility',rows:cross,expected:48,evidence:'final_run/cross_browser_results.csv'},
];
const valid = raw.perf.filter((row)=>row.status !== 'INVALID TEST');
const within = valid.filter((row)=>row.within_5000ms === true).length;
const rate = valid.length ? 100*within/valid.length : 0;
const times = valid.map((row)=>Number(row.usable_page_load_ms)).filter(Number.isFinite).sort((a,b)=>a-b);
const median = times.length ? (times[(times.length-1)>>1]+times[times.length>>1])/2 : null;
const percentile = (p) => times.length ? times[Math.ceil(p*times.length)-1] : null;
const censored = valid.filter((row)=>String(row.notes).includes('censored lower bound')).length;
const perRoute = Object.fromEntries([...new Set(raw.perf.map((row)=>row.route))].map((route)=>{
  const rows=valid.filter((row)=>row.route===route);
  const successes=rows.filter((row)=>row.within_5000ms === true).length;
  return [route,{planned_trials:10,valid_trials:rows.length,within_threshold_trials:successes,pass_rate_pct:rows.length?100*successes/rows.length:null}];
}));
const performanceSummary = {
  run_id:runId,production_url:'https://pse-pulse.vercel.app/',threshold_ms:5000,required_pass_rate_pct:90,
  planned_trials:80,valid_trials:valid.length,within_threshold_trials:within,overall_pass_rate_pct:rate,
  measurement_status:valid.length===80?'PASS':'FAIL',threshold_status:valid.length===80&&rate>=90?'PASS':'FAIL',
  median_usable_load_ms:median,p90_usable_load_ms:percentile(.9),p95_usable_load_ms:percentile(.95),maximum_usable_load_ms:times.at(-1)??null,
  censored_timeout_trials:censored,percentile_caveat:censored?'Timeout elapsed values are lower bounds, not completed usable loads.':null,per_route:perRoute,
};
await writeFile(join(final,'performance_summary.json'),JSON.stringify(performanceSummary,null,2)+'\n');
const summary = groups.map((group)=>({validation:group.name,status:group.rows.length===group.expected&&passed(group.rows)===group.expected?'PASS':'FAIL',measured_result:`${passed(group.rows)}/${group.expected} final cases passed`,evidence:group.evidence,notes:''}));
summary.push({validation:'Page-load/performance measurement',status:performanceSummary.measurement_status,measured_result:`${valid.length}/80 valid trials completed`,evidence:'final_run/performance_results.csv',notes:`${censored} censored timeout(s)`});
summary.push({validation:'90% within five-second performance threshold',status:performanceSummary.threshold_status,measured_result:`${within}/${valid.length} (${rate.toFixed(2)}%) completed within 5.0 seconds`,evidence:'final_run/performance_summary.json',notes:'Required >=90.00%; unthrottled Chromium 1440x900'});
await writeFile(join(root,'browser_validation_summary.csv'),csv(['validation','status','measured_result','evidence','notes'],summary));
const firefoxByEngine = Object.fromEntries(['chromium','firefox','webkit'].map((engine)=>[engine,{passed:passed(cross.filter((row)=>row.browser_engine===engine)),total:cross.filter((row)=>row.browser_engine===engine).length}]));
const categoriesPassed = summary.filter((row)=>row.status==='PASS').length;
const failureReason = (notes) => /timeout|timed out/i.test(String(notes)) ? 'navigation timed out at the unchanged 30-second limit; see raw result for detail' : String(notes).split('\n')[0];
const finalFailures = [
  ...raw.responsive.filter((row)=>row.status!=='PASS').map((row)=>`Responsive ${row.route} at ${row.viewport_width}×${row.viewport_height} (${row.browser}): ${failureReason(row.notes)}`),
  ...cross.filter((row)=>row.status!=='PASS').map((row)=>`Cross-browser ${row.route} at ${row.viewport} (${row.browser_engine}): ${failureReason(row.notes)}`),
  ...raw.perf.filter((row)=>row.status!=='PASS').map((row)=>`Performance ${row.route} trial ${row.trial} (${row.browser}): ${failureReason(row.notes)}`),
];
const table = [
  '### Table XX. Browser-Level Validation','',
  '| Validation | Status | Measured Result |','|---|---|---|',
  ...summary.map((row)=>`| ${row.validation} | ${row.status} | ${row.measured_result} |`),'',
  'Firefox compatibility was validated using the locally installed Mozilla Firefox application through an isolated WebDriver session because the pinned Playwright Firefox launcher encountered a macOS profile-launch issue. Chromium and WebKit were exercised through Playwright.','',
  `Final clean run: ${categoriesPassed}/6 categories passed (${(100*categoriesPassed/6).toFixed(2)}%). Performance threshold uses ${within}/${valid.length} valid fresh-context page loads and is separate from category pass rate.`,
  'The original timeout failures and Firefox launch blockage remain in `initial_run/`; controlled retries and recovery evidence are in `retest/`. Browser-level validation is not user acceptance testing.','',
].join('\n');
await writeFile(join(root,'TABLE_XX_BROWSER_LEVEL_VALIDATION.md'),table);
const report = [
  '# PSE Pulse Browser-Level Validation — Final Run','',
  `Run ID: ${runId}  `,`Repository SHA: 8acda4af140e02ae55dc40b29541c4089bded597  `,
  'Production URL: https://pse-pulse.vercel.app/  ',
  'The initial run and its original manifest remain preserved under `initial_run/`. This report describes the separately executed final clean run.','',
  '## Method','',
  '- Chromium responsive: eight routes × eight viewports, 64 fresh-context cases; visible landmarks, route content, navigation, overflow, page errors, and critical same-origin requests checked.',
  '- Cross-browser: eight routes × mobile 390×844 and desktop 1440×900 in Chromium, actual Mozilla Firefox 157.0, and WebKit. Chromium/WebKit used Playwright; Firefox used an isolated temporary-profile WebDriver session with BiDi viewport control.',
  '- Performance: Chromium 1440×900, ten fresh contexts per route; 5,000 ms threshold, 30-second navigation timeout, no synthetic throttling. Timed-out trials remain in the denominator as threshold failures.',
  '- Lighthouse 24-run supplementary measurements remain in `initial_run/`; they were not rerun or used for the five-second verdict.',
  `- Live home-page HTML identity before/after final run: ${identityMatch?'MATCH':'MISMATCH'} (${identityBefore.html_sha256} / ${identityAfter.html_sha256}); this fingerprint does not independently establish the deployed Git SHA.`,'',
  '## Final category results','',
  '| Category | Status | Measured result |','|---|---|---|',...summary.map((row)=>`| ${row.validation} | ${row.status} | ${row.measured_result} |`),'',
  `Cross-browser engine counts: Chromium ${firefoxByEngine.chromium.passed}/${firefoxByEngine.chromium.total}; Firefox ${firefoxByEngine.firefox.passed}/${firefoxByEngine.firefox.total}; WebKit ${firefoxByEngine.webkit.passed}/${firefoxByEngine.webkit.total}.`,
  `Performance: median ${median?.toFixed(2)??'N/A'} ms, p90 ${percentile(.9)?.toFixed(2)??'N/A'} ms, p95 ${percentile(.95)?.toFixed(2)??'N/A'} ms, maximum ${times.at(-1)?.toFixed(2)??'N/A'} ms. ${censored} timed-out trial(s) are censored lower bounds.`,
  `Overall category status: ${categoriesPassed}/6 PASS; ${(100*categoriesPassed/6).toFixed(2)}% category pass rate.`, '',
  '## Final-run failures','',
  ...(finalFailures.length?finalFailures.map((item)=>`- ${item}`):['- None.']), '',
  '## Evidence and interpretation','',
  '- Original failures and initial manifest: `initial_run/`.',
  '- Browser recovery and controlled timeout retests: `retest/`.',
  '- New responsive, cross-browser, and performance matrices: `final_run/`.',
  '- Final evidence integrity: `final_test_manifest.csv`.',
  '- The actual Mozilla Firefox method bypassed, but did not fix, the Playwright profile-launch failure.',
  '- WebKit engine testing is not certification of every Safari release or device. Browser tests do not replace stakeholder UAT.', '',
].join('\n');
await writeFile(join(root,'README.md'),report);
const action = [
  '# Corrective Action and Retest','',
  '1. Initial browser run: responsive 61/64, cross-browser 32/48 with Firefox blocked, performance 73/80 within five seconds; original artifacts preserved under `initial_run/`.',
  '2. Initial Firefox BLOCKED condition: pinned Playwright Firefox could not start a temporary profile.',
  '3. Playwright Firefox reinstall attempt: pinned browser reinstall completed without resolving launch.',
  '4. Continued `Could not find profile folder` failure: both bundled and explicit installed-browser Playwright smoke tests recorded the same error.',
  '5. Tester manually installed Mozilla Firefox 157.0 in `/Applications/Firefox.app`.',
  '6. New Firefox smoke-test method: isolated LaunchServices process with fresh temporary profile, GeckoDriver connect-existing, and Selenium/WebDriver passed.',
  '7. Firefox compatibility regression: valid targeted matrix passed 16/16 after one isolated `/watchlist` timeout; that case passed five fresh-session retries. Final clean Firefox matrix is separately recorded.',
  '8. Original timeout controlled retests: 10 observations × five fresh-context attempts; 50/50 corrected attempts passed. The invalid harness preflight remains labeled and excluded.',
  `9. Final responsive run: ${passed(raw.responsive)}/64 passed.`,
  `10. Final cross-browser run: ${passed(cross)}/48 passed (Chromium ${firefoxByEngine.chromium.passed}/16, Firefox ${firefoxByEngine.firefox.passed}/16, WebKit ${firefoxByEngine.webkit.passed}/16).`,
  `11. Final performance confirmation: ${valid.length}/80 valid trials, ${within}/${valid.length} (${rate.toFixed(2)}%) within five seconds.`,
  `12. Final category status: ${categoriesPassed}/6 PASS; overall ${categoriesPassed===6?'PASS':'FAIL'}.`,'',
  'Original failures were not reclassified as nonexistent; the final category verdict derives only from final clean run records. The application and formal research results were not changed.','',
].join('\n');
await writeFile(join(root,'CORRECTIVE_ACTION_AND_RETEST.md'),action);

async function files(directory) {
  const entries=await readdir(directory,{withFileTypes:true});
  return (await Promise.all(entries.map(async (entry)=>entry.isDirectory()?files(join(directory,entry.name)):[join(directory,entry.name)]))).flat();
}
const all=(await files(root)).filter((path)=>path!==join(root,'final_test_manifest.csv') && basename(path)!=='.DS_Store').sort();
const manifest=[];
for (const path of all) {
  const data=await readFile(path);
  manifest.push({path:relative(root,path),sha256:createHash('sha256').update(data).digest('hex'),size_bytes:(await stat(path)).size,run_id:runId,repository_sha:'8acda4af140e02ae55dc40b29541c4089bded597',production_url:'https://pse-pulse.vercel.app/'});
}
await writeFile(join(root,'final_test_manifest.csv'),csv(['path','sha256','size_bytes','run_id','repository_sha','production_url'],manifest));
console.log(JSON.stringify({responsive:[passed(raw.responsive),64],cross:[passed(cross),48],engines:firefoxByEngine,performance:[within,valid.length,rate],categories:[categoriesPassed,6],manifest_files:manifest.length},null,2));
