import { chromium, webkit } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { performance } from 'node:perf_hooks';
import { runBoundedTransportCase } from './transport_retry.mjs';

const root = process.env.EVIDENCE_DIR;
const runId = process.env.RUN_ID;
if (!root || !runId) throw new Error('EVIDENCE_DIR and RUN_ID are required');
const base = 'https://pse-pulse.vercel.app';
const routes = ['/', '/companies', '/companies/ALI', '/companies/GLO', '/watchlist', '/compare', '/learn-stocks', '/about'];
const viewports = [
  ['mobile', 390, 844], ['mobile', 412, 915],
  ['tablet', 768, 1024], ['tablet', 820, 1180],
  ['laptop', 1366, 768], ['laptop', 1440, 900],
  ['desktop', 1920, 1080], ['desktop', 2560, 1440],
];
const browsers = { chromium, webkit };
const csvEscape = (value) => `"${String(value ?? '').replaceAll('"', '""').replaceAll('\n', ' ')}"`;
const csv = (fields, rows) => [fields.join(','), ...rows.map((row) => fields.map((field) => csvEscape(row[field])).join(','))].join('\n') + '\n';
const slug = (route) => route === '/' ? 'home' : route.slice(1).replaceAll('/', '_');
const url = (route) => new URL(route, base).href;
const errors = [];
const transportAttempts = [];
const transportFields = ['logical_case_id','transport_attempt_count','transport_retry_used','first_attempt_transport_status','final_document_http_status','usable_state_ms','assertion_status','final_status'];
const responsiveFields = ['run_id','timestamp','browser','route','viewport_category','viewport_width','viewport_height','navigation_start','response_received_ms','http_status','domcontentloaded_time_ms','document_ready_state','primary_landmark_visible_ms','usable_page_load_ms','window_load_time_ms','browser_navigation_error','primary_content_visible','horizontal_overflow','pageerror_count','console_error_count','critical_request_failure_count','navigation_usable','core_content_rendered','screenshot','status','notes',...transportFields];
const crossFields = ['run_id','timestamp','browser','browser_engine','browser_version','route','viewport','navigation_start','response_received_ms','http_status','domcontentloaded_time_ms','document_ready_state','primary_landmark_visible_ms','usable_page_load_ms','window_load_time_ms','browser_navigation_error','primary_content_visible','horizontal_overflow','pageerror_count','console_error_count','critical_request_failure_count','status','notes',...transportFields];

function wireErrors(page) {
  const observed = { pageerrors: [], consoleErrors: [], criticalFailures: [] };
  page.on('pageerror', (error) => observed.pageerrors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') observed.consoleErrors.push(message.text()); });
  page.on('requestfailed', (request) => {
    if (isCritical(request)) observed.criticalFailures.push(`${request.url()}: ${request.failure()?.errorText}`);
  });
  page.on('response', (response) => {
    if (response.status() >= 400 && isCritical(response.request())) observed.criticalFailures.push(`${response.status()} ${response.url()}`);
  });
  return observed;
}

function isCritical(request) {
  try {
    return new URL(request.url()).origin === base && ['document', 'script', 'stylesheet', 'fetch', 'xhr'].includes(request.resourceType());
  } catch { return false; }
}

async function routeChecks(page, route, width, deadline) {
  const remaining = () => Math.max(1, deadline - performance.now());
  const heading = page.locator('main h1').first();
  await heading.waitFor({ state: 'visible', timeout: remaining() });
  if (route === '/compare' || route.startsWith('/companies/')) {
    await page.locator('main .recharts-surface').first().waitFor({ state: 'visible', timeout: remaining() });
  }
  const primary = await page.locator('main').isVisible();
  const layout = await page.evaluate(() => {
    const heading = document.querySelector('main h1');
    const h = heading?.getBoundingClientRect();
    const navbar = document.querySelector('body > * nav');
    const nav = navbar?.getBoundingClientRect();
    const fixedCover = [...document.querySelectorAll('*')].filter((el) => {
      const css = getComputedStyle(el);
      if (css.position !== 'fixed' || css.visibility === 'hidden') return false;
      const r = el.getBoundingClientRect();
      return h && r.width > innerWidth * .7 && r.height > innerHeight * .25 && r.top < h.bottom && r.bottom > h.top;
    }).length;
    return {
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      viewportWidth: innerWidth,
      headingClipped: !h || h.width < 1 || h.height < 1 || h.left < -2 || h.right > innerWidth + 2,
      navOverflow: !!nav && (nav.left < -2 || nav.right > innerWidth + 2),
      fixedCover,
    };
  });
  let core = true;
  if (route === '/compare') core = await page.getByRole('heading', { name: 'Model Leaderboard' }).isVisible() && await page.locator('main .recharts-surface').count() > 0;
  else if (route.startsWith('/companies/')) core = await page.getByRole('heading', { name: route.split('/').at(-1), exact: true }).isVisible() && await page.locator('main .recharts-surface, main svg[role="img"]').count() > 0 && await page.getByText(/Next.Day Prediction|Forecast/i).count() > 0;
  else if (route === '/watchlist') core = await page.getByRole('heading', { name: 'My Watchlist' }).isVisible();
  else if (route === '/companies') core = await page.getByRole('heading', { name: 'Company List' }).isVisible();
  else if (route === '/learn-stocks') core = await page.getByRole('heading', { name: /4-Step Learning Path/ }).isVisible();
  else if (route === '/about') core = await page.getByRole('heading', { name: 'About PSE Pulse' }).isVisible();
  else core = await page.locator('main h1').isVisible();
  let navUsable;
  if (width < 768) {
    const mobile = page.getByRole('navigation', { name: 'Mobile Navigation' });
    navUsable = await mobile.isVisible() && await mobile.getByRole('link', { name: /Companies/ }).isVisible() && await mobile.getByRole('link', { name: /About/ }).isVisible();
  } else {
    navUsable = await page.getByRole('navigation').first().getByRole('link', { name: 'Companies' }).isVisible();
  }
  return { primary, core, navUsable, layout };
}

async function inspectAttempt(browser, engine, route, category, width, height, screenshotKind, attemptNumber, caseNumber) {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const observed = wireErrors(page);
  const timestamp = new Date().toISOString();
  const started = performance.now();
  const navigation = { navigation_start: timestamp, response_received_ms: null, domcontentloaded_time_ms: null, window_load_time_ms: null, document_ready_state: '', primary_landmark_visible_ms: null, usable_page_load_ms: null, browser_navigation_error: '' };
  page.on('domcontentloaded', () => { navigation.domcontentloaded_time_ms ??= performance.now() - started; });
  page.on('load', () => { navigation.window_load_time_ms ??= performance.now() - started; });
  let mainResponseStatus = null;
  page.on('response', (event) => { if (event.url() === url(route) && event.request().isNavigationRequest()) { navigation.response_received_ms ??= performance.now() - started; mainResponseStatus ??= event.status(); } });
  const notes = [];
  let response, checks, status = 'FAIL', screenshot = '';
  try {
    response = await page.goto(url(route), { waitUntil: 'commit', timeout: 30000 });
    checks = await routeChecks(page, route, width, started + 30000);
    navigation.primary_landmark_visible_ms = performance.now() - started;
    navigation.usable_page_load_ms = navigation.primary_landmark_visible_ms;
    navigation.document_ready_state = await page.evaluate(() => document.readyState);
    if (navigation.usable_page_load_ms > 30000) notes.push('usable landmark exceeded 30-second navigation ceiling');
    await page.waitForTimeout(250);
    if (!response || response.status() >= 400) notes.push(`HTTP ${response?.status() ?? 'none'}`);
    if (!checks.primary) notes.push('primary landmark hidden');
    if (!checks.core) notes.push('route-specific core content missing');
    if (!checks.navUsable) notes.push('navigation unusable');
    if (checks.layout.documentWidth > width + 2 || checks.layout.bodyWidth > width + 2) notes.push(`horizontal overflow doc=${checks.layout.documentWidth}, body=${checks.layout.bodyWidth}`);
    if (checks.layout.headingClipped) notes.push('primary heading clipped');
    if (checks.layout.navOverflow) notes.push('header/navigation overflow');
    if (checks.layout.fixedCover) notes.push('major fixed element obscures heading');
    if (observed.pageerrors.length) notes.push(`${observed.pageerrors.length} pageerror(s)`);
    if (observed.consoleErrors.length) notes.push(`${observed.consoleErrors.length} console error(s)`);
    if (observed.criticalFailures.length) notes.push(`${observed.criticalFailures.length} critical request failure(s)`);
    status = notes.length ? 'FAIL' : 'PASS';
  } catch (error) { navigation.browser_navigation_error = error.message; notes.push(error.message); }
  const canonical = screenshotKind === 'responsive' && [390, 768, 1440, 1920].includes(width) && ['/', '/companies', '/companies/ALI', '/compare', '/learn-stocks', '/about'].includes(route);
  const crossCanonical = screenshotKind === 'cross_browser' && ((width === 1440 && route === '/compare') || (width === 390 && route === '/companies/ALI'));
  if ((canonical && status === 'PASS') || crossCanonical || status !== 'PASS') {
    const sub = status === 'PASS' ? screenshotKind : `${screenshotKind}/failures`;
    const name = `${engine}_${category}_${width}x${height}_${slug(route)}${caseNumber === null ? '' : `_case${caseNumber}`}${status === 'PASS' ? '' : `_attempt${attemptNumber}_FAIL`}.png`;
    const path = join(root, 'screenshots', sub, name);
    await mkdir(join(root, 'screenshots', sub), { recursive: true });
    await page.screenshot({ path, fullPage: true }).catch((error) => notes.push(`screenshot failed: ${error.message}`));
    screenshot = relative(root, path);
    if (status !== 'PASS') {
      await writeFile(path.replace(/\.png$/, '.html'), await page.content().catch(() => ''), 'utf8');
      errors.push({ engine, route, viewport: `${width}x${height}`, notes, screenshot });
    }
  }
  const httpStatus = response?.status() ?? mainResponseStatus;
  const mainDocumentResponseReceived = httpStatus !== null;
  let appDomAvailable = !!checks?.primary;
  if (!checks && !mainDocumentResponseReceived) {
    const content = await Promise.race([page.content().catch(() => null), new Promise((resolve) => setTimeout(() => resolve(null), 1000))]);
    appDomAvailable = content === null ? null : /<main(?:\s|>)/i.test(content);
  }
  const assertionsExecuted = !!checks;
  const common = {
    run_id: runId, timestamp, route, http_status: httpStatus ?? '', ...navigation,
    primary_content_visible: !!checks?.primary,
    horizontal_overflow: !!checks && (checks.layout.documentWidth > width + 2 || checks.layout.bodyWidth > width + 2),
    pageerror_count: observed.pageerrors.length, console_error_count: observed.consoleErrors.length,
    critical_request_failure_count: observed.criticalFailures.length, status,
    notes: [...notes, ...observed.pageerrors, ...observed.consoleErrors, ...observed.criticalFailures].join(' | '),
  };
  await context.close();
  let transportStatus = 'DOCUMENT_DELIVERED';
  if (!mainDocumentResponseReceived && appDomAvailable === false && !assertionsExecuted && navigation.browser_navigation_error) transportStatus = 'TRANSPORT_NO_DOCUMENT';
  else if (httpStatus !== null && httpStatus >= 400) transportStatus = 'HTTP_APPLICATION_FAILURE';
  else if (navigation.browser_navigation_error && appDomAvailable) transportStatus = 'NAVIGATION_API_ONLY';
  else if (navigation.browser_navigation_error) transportStatus = 'APPLICATION_RUNTIME_FAILURE';
  else if (status !== 'PASS') transportStatus = 'UI_ASSERTION_FAILURE';
  return { common, checks, screenshot, status, transport_status: transportStatus, main_document_response_received: mainDocumentResponseReceived, app_dom_available: appDomAvailable, assertions_executed: assertionsExecuted, http_status: httpStatus, browser_navigation_error: navigation.browser_navigation_error };
}

async function inspectCase(browser, engine, route, category, width, height, screenshotKind, caseNumber = null) {
  const logicalCaseId = `${screenshotKind}_${engine}_${width}x${height}_${slug(route)}${caseNumber === null ? '' : `_case${caseNumber}`}`;
  const result = await runBoundedTransportCase((attemptNumber) => inspectAttempt(browser, engine, route, category, width, height, screenshotKind, attemptNumber, caseNumber));
  transportAttempts.push({ logical_case_id: logicalCaseId, browser: engine, route, viewport: `${width}x${height}`, attempts: result.attempts.map((attempt, index) => ({ attempt: index + 1, ...attempt })) });
  await writeFile(join(root, 'transport_attempts.json'), JSON.stringify(transportAttempts, null, 2) + '\n');
  const final = result.final;
  return {
    common: { ...final.common, logical_case_id: logicalCaseId, browser: engine, viewport: `${width}x${height}`, transport_attempt_count: result.transport_attempt_count, transport_retry_used: result.transport_retry_used, first_attempt_transport_status: result.first_attempt_transport_status, final_document_http_status: final.http_status ?? '', usable_state_ms: final.common.usable_page_load_ms ?? '', assertion_status: final.assertions_executed ? final.status : 'NOT_RUN', final_status: final.status },
    checks: final.checks, screenshot: final.screenshot,
  };
}

async function run() {
  await mkdir(root, { recursive: true });
  const responsive = [], cross = [], perf = [];
  const launched = {};
  for (const [name, type] of Object.entries(browsers)) {
    try { launched[name] = await type.launch({ headless: true }); }
    catch (error) { launched[name] = null; errors.push({ engine: name, route: 'all', viewport: 'all', notes: [error.message], screenshot: '' }); }
  }
  if (!launched.chromium) throw new Error('Chromium is required for the responsive and primary performance matrices');
  try {
    if (process.env.BROWSER_VALIDATION_MODE === 'targeted') {
      const selected = [
        ['/about', 'desktop', 1440, 900],
        ['/companies', 'desktop', 1440, 900],
        ['/learn-stocks', 'mobile', 390, 844],
        ['/learn-stocks', 'desktop', 1440, 900],
      ];
      for (const [route, category, width, height] of selected) {
        for (let caseNumber = 1; caseNumber <= 10; caseNumber++) {
          console.log(`[targeted] ${route} ${width}x${height} logical case ${caseNumber}/10`);
          const { common, checks, screenshot } = await inspectCase(launched.chromium, 'chromium', route, category, width, height, 'responsive', caseNumber);
          responsive.push({ ...common, browser: 'chromium', viewport_category: category, viewport_width: width, viewport_height: height, navigation_usable: !!checks?.navUsable, core_content_rendered: !!checks?.core, screenshot });
        }
      }
      await writeFile(join(root, 'targeted_transport_retry_validation.csv'), csv(responsiveFields, responsive));
      await writeFile(join(root, 'targeted_transport_retry_validation.raw.json'), JSON.stringify({ runId, responsive, transportAttempts, errors }, null, 2) + '\n');
      return;
    }
    for (const [category, width, height] of viewports) {
      for (const route of routes) {
        console.log(`[responsive] ${category} ${width}x${height} ${route}`);
        const { common, checks, screenshot } = await inspectCase(launched.chromium, 'chromium', route, category, width, height, 'responsive');
        responsive.push({ ...common, browser: 'chromium', viewport_category: category, viewport_width: width, viewport_height: height, navigation_usable: !!checks?.navUsable, core_content_rendered: !!checks?.core, screenshot });
      }
    }
    for (const [engine, browser] of Object.entries(launched)) {
      for (const [category, width, height] of [['mobile', 390, 844], ['desktop', 1440, 900]]) {
        for (const route of routes) {
          console.log(`[cross-browser] ${engine} ${category} ${route}`);
          if (!browser) {
            cross.push({ run_id: runId, timestamp: new Date().toISOString(), browser_engine: engine, browser_version: '', route, viewport: `${width}x${height}`, http_status: '', primary_content_visible: false, horizontal_overflow: '', pageerror_count: '', console_error_count: '', critical_request_failure_count: '', status: 'BLOCKED', notes: 'Browser engine failed to launch; see raw_results.json' });
            continue;
          }
          const { common } = await inspectCase(browser, engine, route, category, width, height, 'cross_browser');
          cross.push({ ...common, browser_engine: engine, browser_version: browser.version(), viewport: `${width}x${height}` });
        }
      }
    }
    for (const route of routes) {
      for (let trial = 1; trial <= 10; trial++) {
        console.log(`[performance] ${route} trial ${trial}/10`);
        const context = await launched.chromium.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
        const page = await context.newPage();
        const observed = wireErrors(page);
        const timestamp = new Date().toISOString();
        const start = performance.now();
        const navigation = { navigation_start: timestamp, response_received_ms: null, domcontentloaded_time_ms: null, window_load_time_ms: null, document_ready_state: '', primary_landmark_visible_ms: null, browser_navigation_error: '' };
        page.on('domcontentloaded', () => { navigation.domcontentloaded_time_ms ??= performance.now() - start; });
        page.on('load', () => { navigation.window_load_time_ms ??= performance.now() - start; });
        page.on('response', (event) => { if (event.url() === url(route)) navigation.response_received_ms ??= performance.now() - start; });
        let response, usable = null, status = 'INVALID TEST', notes = '';
        try {
          response = await page.goto(url(route), { waitUntil: 'commit', timeout: 30000 });
          await routeChecks(page, route, 1440, start + 30000);
          navigation.primary_landmark_visible_ms = performance.now() - start;
          navigation.document_ready_state = await page.evaluate(() => document.readyState);
          usable = performance.now() - start;
          status = response?.status() === 200 && observed.pageerrors.length === 0 && observed.criticalFailures.length === 0 ? (usable <= 5000 ? 'PASS' : 'FAIL') : 'FAIL';
          notes = [...observed.pageerrors, ...observed.consoleErrors, ...observed.criticalFailures].join(' | ');
        } catch (error) {
          navigation.browser_navigation_error = error.message;
          notes = error.message;
          if (/Timeout|ERR_TIMED_OUT/.test(error.message)) {
            usable = performance.now() - start;
            notes += ' | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure';
            status = 'FAIL';
          } else status = response ? 'FAIL' : 'INVALID TEST';
        }
        const nav = await page.evaluate(() => {
          const n = performance.getEntriesByType('navigation')[0];
          return n ? { dcl: n.domContentLoadedEventEnd, load: n.loadEventEnd || null } : {};
        }).catch(() => ({}));
        perf.push({ run_id: runId, timestamp, browser: 'chromium', browser_version: launched.chromium.version(), route, trial, viewport_width: 1440, viewport_height: 900, http_status: response?.status() ?? '', ...navigation, domcontentloaded_ms: nav.dcl ?? '', load_event_ms: nav.load ?? '', usable_page_load_ms: usable === null ? '' : usable.toFixed(2), within_5000ms: usable !== null && usable <= 5000, pageerror_count: observed.pageerrors.length, console_error_count: observed.consoleErrors.length, critical_request_failure_count: observed.criticalFailures.length, status, notes });
        await context.close();
      }
    }
  } finally { for (const browser of Object.values(launched)) if (browser) await browser.close(); }
  await writeFile(join(root, 'responsive_test_results.csv'), csv(responsiveFields, responsive));
  await writeFile(join(root, 'cross_browser_results.csv'), csv(crossFields, cross));
  await writeFile(join(root, 'performance_results.csv'), csv(['run_id','timestamp','browser','browser_version','route','trial','viewport_width','viewport_height','navigation_start','response_received_ms','http_status','domcontentloaded_time_ms','document_ready_state','primary_landmark_visible_ms','usable_page_load_ms','window_load_time_ms','browser_navigation_error','domcontentloaded_ms','load_event_ms','within_5000ms','pageerror_count','console_error_count','critical_request_failure_count','status','notes'], perf));
  await writeFile(join(root, 'raw_results.json'), JSON.stringify({ runId, responsive, cross, perf, errors, firefox_matrix_separate: true }, null, 2));
  console.log(`[complete] responsive=${responsive.length}, cross=${cross.length}, performance=${perf.length}`);
}

await run();
