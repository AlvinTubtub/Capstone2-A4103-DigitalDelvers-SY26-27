# PSE Pulse Browser-Level Validation — Final Run

Run ID: FINAL_20261001  
Repository SHA: 8acda4af140e02ae55dc40b29541c4089bded597  
Production URL: https://pse-pulse.vercel.app/  
The initial run and its original manifest remain preserved under `initial_run/`. This report describes the separately executed final clean run.

## Method

- Chromium responsive: eight routes × eight viewports, 64 fresh-context cases; visible landmarks, route content, navigation, overflow, page errors, and critical same-origin requests checked.
- Cross-browser: eight routes × mobile 390×844 and desktop 1440×900 in Chromium, actual Mozilla Firefox 157.0, and WebKit. Chromium/WebKit used Playwright; Firefox used an isolated temporary-profile WebDriver session with BiDi viewport control.
- Performance: Chromium 1440×900, ten fresh contexts per route; 5,000 ms threshold, 30-second navigation timeout, no synthetic throttling. Timed-out trials remain in the denominator as threshold failures.
- Lighthouse 24-run supplementary measurements remain in `initial_run/`; they were not rerun or used for the five-second verdict.
- Live home-page HTML identity before/after final run: MATCH (8ed46632857c392c6ed1e3835239b5898031bac951e059064f0e3b6460bf9e21 / 8ed46632857c392c6ed1e3835239b5898031bac951e059064f0e3b6460bf9e21); this fingerprint does not independently establish the deployed Git SHA.

## Final category results

| Category | Status | Measured result |
|---|---|---|
| Mobile responsive testing | FAIL | 15/16 final cases passed |
| Tablet responsive testing | PASS | 16/16 final cases passed |
| Laptop/desktop browser testing | PASS | 32/32 final cases passed |
| Cross-browser compatibility | FAIL | 45/48 final cases passed |
| Page-load/performance measurement | PASS | 80/80 valid trials completed |
| 90% within five-second performance threshold | PASS | 76/80 (95.00%) completed within 5.0 seconds |

Cross-browser engine counts: Chromium 14/16; Firefox 15/16; WebKit 16/16.
Performance: median 408.00 ms, p90 565.69 ms, p95 1146.14 ms, maximum 30002.65 ms. 4 timed-out trial(s) are censored lower bounds.
Overall category status: 4/6 PASS; 66.67% category pass rate.

## Final-run failures

- Responsive /companies at 412×915 (chromium): navigation timed out at the unchanged 30-second limit; see raw result for detail
- Cross-browser /learn-stocks at 390x844 (chromium): navigation timed out at the unchanged 30-second limit; see raw result for detail
- Cross-browser /about at 1440x900 (chromium): navigation timed out at the unchanged 30-second limit; see raw result for detail
- Cross-browser /compare at 390x844 (firefox): navigation timed out at the unchanged 30-second limit; see raw result for detail
- Performance / trial 2 (chromium): navigation timed out at the unchanged 30-second limit; see raw result for detail
- Performance /companies/ALI trial 2 (chromium): navigation timed out at the unchanged 30-second limit; see raw result for detail
- Performance /companies/ALI trial 8 (chromium): navigation timed out at the unchanged 30-second limit; see raw result for detail
- Performance /compare trial 1 (chromium): navigation timed out at the unchanged 30-second limit; see raw result for detail

## Evidence and interpretation

- Original failures and initial manifest: `initial_run/`.
- Browser recovery and controlled timeout retests: `retest/`.
- New responsive, cross-browser, and performance matrices: `final_run/`.
- Final evidence integrity: `final_test_manifest.csv`.
- The actual Mozilla Firefox method bypassed, but did not fix, the Playwright profile-launch failure.
- WebKit engine testing is not certification of every Safari release or device. Browser tests do not replace stakeholder UAT.

Screenshots were intentionally excluded from repository storage to reduce repository size. Machine-readable CSV/JSON results and execution logs are the authoritative evidence. Screenshot path fields are blank; validation measurements and pass/fail results are unchanged.
