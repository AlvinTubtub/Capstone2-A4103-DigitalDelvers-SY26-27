# PSE Pulse Browser-Level Validation

Run ID: BROWSER_VALIDATION_20261001_0926_PHT  
Repository SHA: 8acda4af140e02ae55dc40b29541c4089bded597  
Production URL: https://pse-pulse.vercel.app/  
Test start: 2026-10-01T01:27:27.171Z  
Test end: 2026-10-01T01:43:54.339Z  
Environment: Darwin 27.0, arm64, Node v24.16.0, Playwright 1.63.0.

## Purpose and scope

Chapter IV technical validation of the live production website. Routes: /, /companies, /companies/ALI, /companies/GLO, /watchlist, /compare, /learn-stocks, /about. This run did not modify the application or forecasting results.

## Method

- Responsive matrix: Chromium, eight routes × eight viewports (390×844, 412×915, 768×1024, 820×1180, 1366×768, 1440×900, 1920×1080, 2560×1440). Checks include landmarks, core content, navigation, page errors, critical same-origin requests, and horizontal overflow.
- Compatibility matrix: three planned engines × eight routes × mobile 390×844 and desktop 1440×900. Firefox launch failed locally, so those cases are BLOCKED rather than failed application tests.
- Primary performance: 10 independent fresh Chromium contexts per route at 1440×900; timer starts immediately before navigation and ends when the route-specific landmark and core content are ready. No synthetic throttling. A 30-second navigation timeout is a valid threshold failure with a censored lower-bound elapsed time; no slow trial was discarded.
- Lighthouse: three runs per route/form factor for /, /companies, /companies/ALI, /compare, desktop and mobile. Lighthouse simulation is supplementary and excluded from the five-second acceptance calculation.
- Site identity: initial and final public home HTML SHA-256 both 8ed46632857c392c6ed1e3835239b5898031bac951e059064f0e3b6460bf9e21; deployment Git SHA not independently resolved from the public response.

## Results

| Category | Result |
|---|---|
| Mobile responsive testing | FAIL: 15/16 passed |
| Tablet responsive testing | FAIL: 15/16 passed |
| Laptop/desktop browser testing | FAIL: 31/32 passed |
| Cross-browser compatibility | BLOCKED: 32/48 passed; 16 Firefox cases blocked |
| Page-load/performance measurement | PASS: 80/80 valid fresh-context trials |
| 90% within five-second performance threshold | PASS: 73/80 = 91.25% (required ≥90.00%) |

Primary observed load: median 429 ms; p90 565 ms; p95 ≥30003 ms; maximum observed lower bound ≥30009 ms. The p95/max include censored timeouts and are lower bounds, not completed usable loads.

### Per-route five-second rate

| Route | Within 5s / valid | Rate |
|---|---:|---:|
| / | 8/10 | 80.00% |
| /companies | 9/10 | 90.00% |
| /companies/ALI | 10/10 | 100.00% |
| /companies/GLO | 10/10 | 100.00% |
| /watchlist | 9/10 | 90.00% |
| /compare | 8/10 | 80.00% |
| /learn-stocks | 9/10 | 90.00% |
| /about | 10/10 | 100.00% |

### Lighthouse medians

| Route / form factor | Completed | Score | LCP (ms) | CLS |
|---|---:|---:|---:|---:|
| / — desktop | 3/3 | 74 | 5915 | 0.000 |
| / — mobile | 3/3 | 90 | 3645 | 0.000 |
| /companies — desktop | 3/3 | 70 | 1847 | 0.517 |
| /companies — mobile | 3/3 | 100 | 1845 | 0.019 |
| /companies/ALI — desktop | 3/3 | 86 | 2295 | 0.000 |
| /companies/ALI — mobile | 3/3 | 97 | 1994 | 0.000 |
| /compare — desktop | 3/3 | 90 | 1994 | 0.000 |
| /compare — mobile | 3/3 | 99 | 1993 | 0.000 |

## Failures and limitations

- 10 observed timeout cases are documented in DEFECTS_FOUND.md. These do not by themselves prove an application-code defect.
- Playwright Firefox 155.0 was downloaded but exited before opening its temporary profile on this macOS 27 host. Its 16 compatibility cases are BLOCKED. Chromium and WebKit cases completed.
- Actual Safari GUI smoke check was not executed; Playwright WebKit testing completed separately.
- Network-quality raw output is in logs/environment.log. Lighthouse mobile simulation may use throttling, unlike the primary threshold test.
- A harness preflight checked client-rendered charts too early; its raw output remains in logs/preflight_raw_results.json and failure observations remain in machine-readable records and logs. The final matrices use a corrected chart-readiness wait.

## Evidence inventory

- `responsive_test_results.csv`, `cross_browser_results.csv`, `performance_results.csv`, `performance_summary.json`, `lighthouse_summary.csv`
- `browser_validation_summary.csv`, `TABLE_XX_BROWSER_LEVEL_VALIDATION.md`, `DEFECTS_FOUND.md`, `test_environment.json`, `test_manifest.csv`
- `lighthouse/`, `logs/`, and `raw_results.json`
- Reproducible harness: `tools/browser_validation/` with exact dependency versions in `package-lock.json`.

## Interpretation boundary

These automated tests provide browser-level technical validation. They do not replace stakeholder usability testing, real-device UAT, or user-perception evaluation.

Playwright WebKit provides WebKit engine-level compatibility evidence and is not equivalent to certification against every Safari release or Apple device.

Screenshots were intentionally excluded from repository storage to reduce repository size. Machine-readable CSV/JSON results and execution logs are the authoritative evidence. Screenshot path fields are blank; validation measurements and pass/fail results are unchanged.
