### Table XX. Browser-Level Validation

| Validation | Status | Measured Result |
|---|---|---|
| Mobile responsive testing | PASS | 16/16 cases passed |
| Tablet responsive testing | PASS | 16/16 cases passed |
| Laptop/desktop browser testing | PASS | 32/32 cases passed |
| Cross-browser compatibility | FAIL | 46/48 cases passed |
| Page-load/performance measurement | PASS | 80/80 valid trials |
| 90% within five-second performance threshold | PASS | 76/80 (95.00%) within 5.0 seconds |

Production URL: https://pse-pulse.vercel.app/. Repository SHA recorded by the harness: 8acda4af140e02ae55dc40b29541c4089bded597. Run: BROWSER_VALIDATION_FINAL_20261001_1216_PHT; started 2026-10-01T04:16:41.777Z, ended 2026-10-01T04:28:20.999Z.
Eight routes were tested at mobile 390×844 and 412×915; tablet 768×1024 and 820×1180; laptop 1366×768 and 1440×900; desktop 1920×1080 and 2560×1440. Cross-browser viewports were 390×844 and 1440×900.
Chromium and the WebKit engine used Playwright. Mozilla Firefox was tested directly using an isolated Selenium/WebDriver session because the Playwright Firefox launcher encountered a macOS profile-launch issue. WebKit is not labeled Safari.
Responsive and compatibility cases permitted one clean-context retry only when the first attempt received no main document. First-attempt transport failures: 3; successful retries: 3; exhausted retries: 0. Both attempts are retained in transport-attempt evidence. No performance trial was retried or replaced.
The unthrottled Chromium performance test measured 80 fresh-context usable-page loads at 1440×900. 76/80 (95.00%) met the separate five-second threshold; the requirement was at least 90%.
The candidate met 5/6 categories and MUST NOT be promoted as an authoritative 6/6 result.
Automated browser validation does not replace stakeholder UAT or subjective real-device usability evaluation.
