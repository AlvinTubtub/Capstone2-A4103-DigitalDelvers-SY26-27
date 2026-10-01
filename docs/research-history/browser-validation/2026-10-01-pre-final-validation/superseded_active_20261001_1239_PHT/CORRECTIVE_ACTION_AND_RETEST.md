# Corrective Action and Retest

1. Initial browser run: responsive 61/64, cross-browser 32/48 with Firefox blocked, performance 73/80 within five seconds; original artifacts preserved under `initial_run/`.
2. Initial Firefox BLOCKED condition: pinned Playwright Firefox could not start a temporary profile.
3. Playwright Firefox reinstall attempt: pinned browser reinstall completed without resolving launch.
4. Continued `Could not find profile folder` failure: both bundled and explicit installed-browser Playwright smoke tests recorded the same error.
5. Tester manually installed Mozilla Firefox 157.0 in `/Applications/Firefox.app`.
6. New Firefox smoke-test method: isolated LaunchServices process with fresh temporary profile, GeckoDriver connect-existing, and Selenium/WebDriver passed.
7. Firefox compatibility regression: valid targeted matrix passed 16/16 after one isolated `/watchlist` timeout; that case passed five fresh-session retries. Final clean Firefox matrix is separately recorded.
8. Original timeout controlled retests: 10 observations × five fresh-context attempts; 50/50 corrected attempts passed. The invalid harness preflight remains labeled and excluded.
9. Final responsive run: 63/64 passed.
10. Final cross-browser run: 45/48 passed (Chromium 14/16, Firefox 15/16, WebKit 16/16).
11. Final performance confirmation: 80/80 valid trials, 76/80 (95.00%) within five seconds.
12. Final category status: 4/6 PASS; overall FAIL.

Original failures were not reclassified as nonexistent; the final category verdict derives only from final clean run records. The application and formal research results were not changed.
