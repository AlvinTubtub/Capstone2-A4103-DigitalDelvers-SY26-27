# PSE Pulse Browser-Level Technical Validation

Run ID: BROWSER_VALIDATION_FINAL_20261001_1239_PHT  
Production URL: https://pse-pulse.vercel.app/  
Repository SHA: 8acda4af140e02ae55dc40b29541c4089bded597  
Categories passed: 6/6  
Category pass rate: 100.00%  
Overall browser-validation status: PASS.

## Responsive result

- Mobile responsive testing: PASS, 16/16 cases passed
- Tablet responsive testing: PASS, 16/16 cases passed
- Laptop/desktop browser testing: PASS, 32/32 cases passed

## Cross-browser result

- Chromium 16/16; WebKit engine 16/16; overall 32/32.
- Firefox is excluded from finalized acceptance because the project requirement specifies cross-browser compatibility but does not mandate Firefox. Its pre-final diagnostic attempts and failures remain in research history. WebKit is not called Safari.

## Bounded transport retries

- First-attempt transport failures: 1; successful transport retries: 1; exhausted retries: 0. Raw first and final attempts remain in transport-attempt evidence.
- Application, UI, JavaScript, and slow-performance results were never retried. The 80 performance trials were each measured once.

## Performance result

- Five-second performance result: 78/80 = 97.50%. Requirement: at least 90%. Status: PASS.
- 80/80 planned trials were valid; no replacement trials were used.
- Median 393.85 ms; p90 514.13 ms; p95 532.77 ms; maximum 30003.82 ms. Timed-out elapsed values are lower bounds.

## Evidence boundary

- Home-page HTML SHA-256 before/after: MATCH; the public response does not independently establish a deployment Git SHA.
- Earlier pre-final runs and corrective-action records are retained under `docs/research-history/browser-validation/`.
- Automated technical validation does not replace stakeholder UAT or subjective real-device usability evaluation.

## Observed non-passes

- Performance /watchlist trial 3: FAIL
- Performance /watchlist trial 9: FAIL

Screenshots were intentionally excluded from repository storage to reduce repository size. Machine-readable CSV/JSON results and execution logs are the authoritative evidence. Screenshot path fields are blank; validation measurements and pass/fail results are unchanged.
