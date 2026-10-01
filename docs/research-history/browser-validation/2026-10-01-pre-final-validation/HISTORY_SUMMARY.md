# Pre-final browser-validation history — 2026-10-01

Repository SHA: `8acda4af140e02ae55dc40b29541c4089bded597`. Production URL: `https://pse-pulse.vercel.app/`.

## Initial validation

| Category | Result |
|---|---:|
| Mobile responsive | 15/16 |
| Tablet responsive | 15/16 |
| Laptop/desktop responsive | 31/32 |
| Cross-browser | 32/48; all 16 Firefox cases BLOCKED by a local launcher failure |
| Within five seconds | 73/80 = 91.25%; threshold PASS |

The initial run recorded 10 navigation timeouts. The original manifest covers 145 evidence files and verifies against the preserved `initial_run/` copy.

## Corrective action

- The 10 original timeout observations received five fresh-context retries each; all 50 corrected attempts passed. This did not erase the initial failures.
- Reinstalling pinned Playwright Firefox did not resolve `Could not find profile folder`.
- The tester manually installed Mozilla Firefox. The actual Firefox 157.0 application was subsequently automated in an isolated Selenium/WebDriver session without altering the normal user profile.
- The valid targeted Firefox regression reached 16/16; preliminary harness-error runs and the one-time `/watchlist` timeout were retained separately.

## Pre-final regression

| Category | Result |
|---|---:|
| Mobile responsive | 15/16 |
| Tablet responsive | 16/16 |
| Laptop/desktop responsive | 32/32 |
| Cross-browser | 45/48 (Chromium 14/16, Firefox 15/16, WebKit 16/16) |
| Within five seconds | 76/80 = 95.00%; threshold PASS |
| Overall categories | 4/6 |

Eight new 30-second navigation timeouts appeared in that separate final attempt. Its 526-file final manifest verifies against `previous_active_package/`; the copied tree also matched the source byte-for-byte when archived.

These runs were pre-final technical validation and corrective-action evidence. They were retained for traceability but are **not** an authoritative 6/6 Chapter IV browser-validation result.
