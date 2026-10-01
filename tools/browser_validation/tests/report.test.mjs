import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const scripts = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const runId = 'SYNTHETIC_REPORT_TEST';
const routes = ['/', '/companies', '/companies/ALI', '/companies/GLO', '/watchlist', '/compare', '/learn-stocks', '/about'];
const viewports = [['mobile',390,844],['mobile',412,915],['tablet',768,1024],['tablet',820,1180],['laptop',1366,768],['laptop',1440,900],['desktop',1920,1080],['desktop',2560,1440]];

async function fixture(failing = false) {
  const root = await mkdtemp(join(tmpdir(), 'pse-pulse-report-test-'));
  await mkdir(join(root, 'logs'));
  const responsive = viewports.flatMap(([category,width,height]) => routes.map((route) => ({ run_id:runId,route,viewport_category:category,viewport_width:width,viewport_height:height,status:failing&&category==='mobile'&&width===390&&route==='/'?'FAIL':'PASS' })));
  const cross = ['chromium','webkit'].flatMap((browser_engine) => [[390,844],[1440,900]].flatMap(([width,height]) => routes.map((route) => ({ run_id:runId,browser_engine,route,viewport:`${width}x${height}`,status:'PASS' }))));
  const firefox = [[390,844],[1440,900]].flatMap(([width,height]) => routes.map((route) => ({ row:{ run_id:runId,browser_engine:'firefox',route,viewport:`${width}x${height}`,status:'PASS' } })));
  const perf = routes.flatMap((route) => Array.from({length:10},(_,index) => ({ run_id:runId,route,trial:index+1,status:'PASS',within_5000ms:true,usable_page_load_ms:'450',notes:'' })));
  const writeJson = (name,value) => writeFile(join(root,name),JSON.stringify(value,null,2)+'\n');
  await writeJson('test_environment.json',{run_id:runId,repository_sha:'test-sha',production_url:'https://pse-pulse.vercel.app/',test_start_timestamp:'2026-10-01T00:00:00Z'});
  await writeJson('raw_results.json',{runId,responsive,cross,perf});
  await writeJson('firefox_cross_browser_results.raw.json',firefox);
  await writeJson('logs/live_site_identity_start.log',{http_status:200,html_sha256:'same'});
  await writeJson('logs/live_site_identity_end.log',{http_status:200,html_sha256:'same',timestamp:'2026-10-01T00:10:00Z'});
  await writeFile(join(root,'cross_browser_results.csv'),'Playwright rows before merge\n');
  return root;
}

function execute(script,root) {
  return spawnSync(process.execPath,[join(scripts,script)],{env:{...process.env,EVIDENCE_DIR:root,RUN_ID:runId},encoding:'utf8'});
}

test('report calculates six categories and manifest verifies every file',async()=>{
  const root=await fixture();
  const report=execute('report.mjs',root);
  assert.equal(report.status,0,report.stderr);
  const result=JSON.parse(report.stdout);
  assert.equal(result.categories_passed,6);
  assert.equal(result.promotion_eligible,true);
  assert.deepEqual(result.cross_browser,{chromium:'16/16',webkit:'16/16'});
  assert.equal(result.within_five_seconds,80);
  assert.match(await readFile(join(root,'TABLE_XX_BROWSER_LEVEL_VALIDATION.md'),'utf8'),/32\/32 cases passed/);
  assert.equal(execute('manifest.mjs',root).status,0);
  assert.equal(execute('verify.mjs',root).status,0);
  await writeFile(join(root,'performance_summary.json'),'changed after manifest\n');
  assert.notEqual(execute('verify.mjs',root).status,0);
});

test('pre-final Firefox failures never enter finalized acceptance scoring',async()=>{
  const root=await fixture();
  const firefox=JSON.parse(await readFile(join(root,'firefox_cross_browser_results.raw.json'),'utf8'));
  firefox[0].row.status='FAIL';
  await writeFile(join(root,'firefox_cross_browser_results.raw.json'),JSON.stringify(firefox)+'\n');
  const report=execute('report.mjs',root);
  assert.equal(report.status,0,report.stderr);
  const result=JSON.parse(report.stdout);
  assert.equal(result.categories_passed,6);
  assert.deepEqual(result.cross_browser,{chromium:'16/16',webkit:'16/16'});
  assert.match(await readFile(join(root,'README.md'),'utf8'),/Firefox is excluded from finalized acceptance/);
});

test('one failed responsive case cannot become a 6/6 report',async()=>{
  const root=await fixture(true);
  const report=execute('report.mjs',root);
  assert.equal(report.status,0,report.stderr);
  assert.equal(JSON.parse(report.stdout).categories_passed,5);
  assert.equal(JSON.parse(report.stdout).promotion_eligible,false);
  assert.match(await readFile(join(root,'TABLE_XX_BROWSER_LEVEL_VALIDATION.md'),'utf8'),/MUST NOT be promoted/);
});

test('report discloses bounded transport retries without changing logical-case counts',async()=>{
  const root=await fixture();
  const source=JSON.parse(await readFile(join(root,'raw_results.json'),'utf8'));
  source.responsive[0].transport_retry_used=true;
  source.responsive[0].transport_attempt_count=2;
  source.responsive[0].first_attempt_transport_status='TRANSPORT_NO_DOCUMENT';
  await writeFile(join(root,'raw_results.json'),JSON.stringify(source)+'\n');
  const report=execute('report.mjs',root);
  assert.equal(report.status,0,report.stderr);
  assert.equal(JSON.parse(report.stdout).categories_passed,6);
  const table=await readFile(join(root,'TABLE_XX_BROWSER_LEVEL_VALIDATION.md'),'utf8');
  assert.match(table,/First-attempt transport failures: 1; successful retries: 1; exhausted retries: 0/);
  const readme=await readFile(join(root,'README.md'),'utf8');
  assert.match(readme,/no replacement trials were used/);
});
