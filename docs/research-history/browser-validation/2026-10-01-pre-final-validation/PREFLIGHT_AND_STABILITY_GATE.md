# Follow-up preflight and stability gate

Repository SHA: `8acda4af140e02ae55dc40b29541c4089bded597`. Live URL: `https://pse-pulse.vercel.app/`. This is **pre-final diagnostic evidence**, not an authoritative Chapter IV run.

The existing browser-validation package was copied byte-for-byte to `previous_active_package/` before active evidence was changed. The copy matched the source tree, and its 145-file original and 526-file later manifests verified.

Targeted preflight passed in Playwright Chromium and WebKit on the homepage, desktop `/compare`, and mobile `/companies`. The installed Mozilla Firefox 157.0 passed the homepage, desktop `/compare`, and mobile `/companies/ALI` through isolated Selenium/WebDriver sessions; screenshots were captured at the time and later excluded from repository storage. The corrected Firefox navigation method waits for the content document before applying its BiDi viewport. One earlier Firefox preflight failed because it applied the viewport to a privileged blank document; that invalid harness result remains retained under `preflight/firefox_none_smoke/`.

The full timeout stability gate covered 12 distinct historical route/browser/viewport combinations with 10 fresh attempts each. Eight configurations passed 10/10. Four failed 9/10:

| Browser | Route | Viewport | Result |
|---|---|---|---:|
| Chromium | `/about` | 1440×900 | 9/10 |
| Chromium | `/companies` | 1440×900 | 9/10 |
| Chromium | `/learn-stocks` | 390×844 | 9/10 |
| Chromium | `/learn-stocks` | 1440×900 | 9/10 |

All other configurations, including actual Firefox `/compare` at 390×844, passed 10/10. Overall, 116/120 attempts passed; the gate requires **every** configuration to pass 10/10. See `preflight/stability_gate_l2AM7v/stability_gate_summary.json` and its per-attempt JSON/Firefox raw evidence.

The four failures happened before navigation response commit: `response_received`, HTTP status, DOMContentLoaded, and primary-landmark times were absent, and the browser recorded a critical request failure. Thus these specific failures cannot be reclassified as late noncritical resource waits or usable pages. The unchanged 30-second ceiling was reached. Five subsequent direct HTTP GET checks of `/about` returned 200 in approximately 0.17–0.31 seconds; that narrow check does not identify the browser-path failure's root cause or invalidate the browser observations.

After the gate, the active harness was simplified: superseded diagnostic scripts were retained under `tooling_diagnostics/`; the Playwright runner now records response-commit and landmark timing separately from DOMContentLoaded/load; Firefox keeps the isolated WebDriver method. A post-cleanup Firefox homepage smoke test passed with HTTP 200, an interactive document, a visible primary landmark, no recorded browser errors, and its temporary Marionette listener closed. No full final matrix was run with this revised harness because the required stability gate had already failed.

**Gate decision: FAIL.** Under the task's stop rule, no authoritative final candidate was started and no 6/6 result was promoted. The existing active browser-validation folder remains an explicitly labeled 4/6 pre-final package; it must not be described as the authoritative final result. Forecasting research and UAT outputs were not changed.
