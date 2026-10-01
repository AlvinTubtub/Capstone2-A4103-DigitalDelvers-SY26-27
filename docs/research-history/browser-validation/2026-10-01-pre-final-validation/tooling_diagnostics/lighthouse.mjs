import lighthouse from 'lighthouse';
import { launch } from 'chrome-launcher';
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
if (!root || !runId) throw new Error('EVIDENCE_DIR and RUN_ID are required');
const routes = ['/', '/companies', '/companies/ALI', '/compare'];
const fields = ['run_id','timestamp','route','form_factor','trial','performance_score','fcp_ms','lcp_ms','speed_index_ms','tbt_ms','cls','status','notes'];
const csvEscape = (value) => `"${String(value ?? '').replaceAll('"', '""').replaceAll('\n', ' ')}"`;
const rows = [];
await mkdir(join(root, 'lighthouse'), { recursive: true });
const chrome = await launch({ chromePath: chromium.executablePath(), chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu'] });
try {
  for (const route of routes) {
    for (const formFactor of ['desktop', 'mobile']) {
      for (let trial = 1; trial <= 3; trial++) {
        console.log(`[lighthouse] ${route} ${formFactor} ${trial}/3`);
        const row = { run_id: runId, timestamp: new Date().toISOString(), route, form_factor: formFactor, trial, status: 'BLOCKED' };
        try {
          const options = { port: chrome.port, output: 'json', onlyCategories: ['performance'], formFactor, logLevel: 'error' };
          if (formFactor === 'desktop') options.screenEmulation = { mobile: false, width: 1350, height: 940, deviceScaleFactor: 1, disabled: false };
          const result = await lighthouse(new URL(route, 'https://pse-pulse.vercel.app').href, options);
          const audits = result.lhr.audits;
          Object.assign(row, {
            performance_score: result.lhr.categories.performance.score * 100,
            fcp_ms: audits['first-contentful-paint'].numericValue,
            lcp_ms: audits['largest-contentful-paint'].numericValue,
            speed_index_ms: audits['speed-index'].numericValue,
            tbt_ms: audits['total-blocking-time'].numericValue,
            cls: audits['cumulative-layout-shift'].numericValue,
            status: result.lhr.runtimeError ? 'BLOCKED' : 'PASS',
            notes: result.lhr.runtimeError?.message ?? '',
          });
        } catch (error) { row.notes = error.stack ?? error.message; }
        rows.push(row);
        const slug = route === '/' ? 'home' : route.slice(1).replaceAll('/', '_');
        await writeFile(join(root, 'lighthouse', `${slug}_${formFactor}_${trial}.json`), JSON.stringify(row, null, 2) + '\n');
      }
    }
  }
} finally { await chrome.kill(); }
await writeFile(join(root, 'lighthouse_summary.csv'), [fields.join(','), ...rows.map((row) => fields.map((field) => csvEscape(row[field])).join(','))].join('\n') + '\n');
console.log(`[lighthouse complete] ${rows.filter((row) => row.status === 'PASS').length}/${rows.length}`);
