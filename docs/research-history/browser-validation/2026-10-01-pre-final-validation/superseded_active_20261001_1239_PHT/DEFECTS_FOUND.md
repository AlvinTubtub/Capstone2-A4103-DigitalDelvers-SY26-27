# Observed Failures Requiring Investigation

No source-application defect was confirmed. The following live navigation timeouts were observed and preserved; they could reflect site availability, the test network, or an intermittent browser/network interaction. Do not relabel them as layout defects without reproduction.

## OBS-01: responsive navigation failure

- Route: /learn-stocks
- Browser: Chromium
- Viewport: 390×844
- Reproduce: Open https://pse-pulse.vercel.app/learn-stocks in a fresh Chromium context at 390×844; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/learn-stocks", waiting until "domcontentloaded"[22m
 | https://pse-pulse.vercel.app/learn-stocks: net::ERR_TIMED_OUT
- Evidence: see the corresponding machine-readable result row and execution log; screenshot intentionally excluded
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-02: responsive navigation failure

- Route: /about
- Browser: Chromium
- Viewport: 820×1180
- Reproduce: Open https://pse-pulse.vercel.app/about in a fresh Chromium context at 820×1180; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/about", waiting until "domcontentloaded"[22m
 | https://pse-pulse.vercel.app/about: net::ERR_TIMED_OUT
- Evidence: see the corresponding machine-readable result row and execution log; screenshot intentionally excluded
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-03: responsive navigation failure

- Route: /about
- Browser: Chromium
- Viewport: 2560×1440
- Reproduce: Open https://pse-pulse.vercel.app/about in a fresh Chromium context at 2560×1440; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/about", waiting until "domcontentloaded"[22m
 | https://pse-pulse.vercel.app/about: net::ERR_TIMED_OUT
- Evidence: see the corresponding machine-readable result row and execution log; screenshot intentionally excluded
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-04: performance navigation failure

- Route: /
- Browser: Chromium
- Viewport: 1440×900
- Reproduce: Open https://pse-pulse.vercel.app/ in a fresh Chromium context at 1440×900; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/", waiting until "domcontentloaded"[22m
 | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure
- Evidence: performance_results.csv (route /, trial 1)
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-05: performance navigation failure

- Route: /
- Browser: Chromium
- Viewport: 1440×900
- Reproduce: Open https://pse-pulse.vercel.app/ in a fresh Chromium context at 1440×900; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/", waiting until "domcontentloaded"[22m
 | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure
- Evidence: performance_results.csv (route /, trial 4)
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-06: performance navigation failure

- Route: /companies
- Browser: Chromium
- Viewport: 1440×900
- Reproduce: Open https://pse-pulse.vercel.app/companies in a fresh Chromium context at 1440×900; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/companies", waiting until "domcontentloaded"[22m
 | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure
- Evidence: performance_results.csv (route /companies, trial 1)
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-07: performance navigation failure

- Route: /watchlist
- Browser: Chromium
- Viewport: 1440×900
- Reproduce: Open https://pse-pulse.vercel.app/watchlist in a fresh Chromium context at 1440×900; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/watchlist", waiting until "domcontentloaded"[22m
 | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure
- Evidence: performance_results.csv (route /watchlist, trial 4)
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-08: performance navigation failure

- Route: /compare
- Browser: Chromium
- Viewport: 1440×900
- Reproduce: Open https://pse-pulse.vercel.app/compare in a fresh Chromium context at 1440×900; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/compare", waiting until "domcontentloaded"[22m
 | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure
- Evidence: performance_results.csv (route /compare, trial 1)
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-09: performance navigation failure

- Route: /compare
- Browser: Chromium
- Viewport: 1440×900
- Reproduce: Open https://pse-pulse.vercel.app/compare in a fresh Chromium context at 1440×900; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/compare", waiting until "domcontentloaded"[22m
 | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure
- Evidence: performance_results.csv (route /compare, trial 6)
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.

## OBS-10: performance navigation failure

- Route: /learn-stocks
- Browser: Chromium
- Viewport: 1440×900
- Reproduce: Open https://pse-pulse.vercel.app/learn-stocks in a fresh Chromium context at 1440×900; wait for DOMContentLoaded and the route landmark.
- Expected: Page reaches a usable rendered state.
- Actual: page.goto: Timeout 30000ms exceeded.
Call log:
[2m  - navigating to "https://pse-pulse.vercel.app/learn-stocks", waiting until "domcontentloaded"[22m
 | Timed out before usable state; elapsed is a censored lower bound, counted as threshold failure
- Evidence: performance_results.csv (route /learn-stocks, trial 3)
- Severity recommendation: Investigate intermittent availability/network path; application severity unconfirmed.
