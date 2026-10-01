# PSE Pulse Browser-Level Technical Validation Candidate

Run ID: BROWSER_VALIDATION_FINAL_20261001_1216_PHT  
Production URL: https://pse-pulse.vercel.app/  
Repository SHA: 8acda4af140e02ae55dc40b29541c4089bded597  
Categories passed: 5/6  
Category pass rate: 83.33%  
Overall browser-validation status: FAIL candidate; do not promote.

## Responsive result

- Mobile responsive testing: PASS, 16/16 cases passed
- Tablet responsive testing: PASS, 16/16 cases passed
- Laptop/desktop browser testing: PASS, 32/32 cases passed

## Cross-browser result

- Chromium 16/16; Mozilla Firefox 14/16; WebKit 16/16; overall 46/48.
- Firefox used the installed browser through an isolated Selenium/WebDriver session, not the failing Playwright Firefox launcher.

## Bounded transport retries

- First-attempt transport failures: 3; successful transport retries: 3; exhausted retries: 0. Raw first and final attempts remain in transport-attempt evidence.
- Application, UI, JavaScript, and slow-performance results were never retried. The 80 performance trials were each measured once.

## Performance result

- Five-second performance result: 76/80 = 95.00%. Requirement: at least 90%. Status: PASS.
- 80/80 planned trials were valid; no replacement trials were used.
- Median 407.49 ms; p90 533.45 ms; p95 988.69 ms; maximum 30005.80 ms. Timed-out elapsed values are lower bounds.

## Evidence boundary

- Home-page HTML SHA-256 before/after: MATCH; the public response does not independently establish a deployment Git SHA.
- Earlier pre-final runs and corrective-action records are retained under `docs/research-history/browser-validation/`.
- Automated technical validation does not replace stakeholder UAT or subjective real-device usability evaluation.

## Observed non-passes

- Cross-browser firefox /watchlist 390x844: FAIL
- Cross-browser firefox /companies/ALI 1440x900: FAIL
- Performance / trial 10: FAIL
- Performance /companies trial 8: FAIL
- Performance /compare trial 9: FAIL
- Performance /about trial 9: FAIL

Screenshots were intentionally excluded from repository storage to reduce repository size. Machine-readable CSV/JSON results and execution logs are the authoritative evidence. Screenshot path fields are blank; validation measurements and pass/fail results are unchanged.
