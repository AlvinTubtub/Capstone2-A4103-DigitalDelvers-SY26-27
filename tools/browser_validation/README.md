# PSE Pulse browser-validation harness

This pinned, read-only harness tests `https://pse-pulse.vercel.app/`. It does not train models or change forecasting research data. The pre-final validation attempts and superseded diagnostic scripts are preserved under `docs/research-history/browser-validation/`.

## Prerequisites

Use the repository version of Node and install the lockfile dependencies from this directory. The finalized matrix uses Playwright Chromium and WebKit engine compatibility. WebKit is not Safari. Firefox was part of pre-final diagnostic testing only; the project requirement does not mandate Firefox, and its earlier attempts and failures remain preserved in research history.

```bash
cd tools/browser_validation
npm ci
npx playwright install chromium webkit
```

The retained `firefox_matrix.mjs` is diagnostic tooling, not a step in the finalized acceptance run.

## Preflight, transport diagnosis, and targeted gate

Run small targeted `navigation_probe.mjs` cases and `firefox_matrix.mjs preflight` before a full run. `navigation_probe.mjs` writes JSON to `OUTPUT_FILE`; `SCREENSHOT_DIR` optionally captures the first Playwright screenshot. The gate script reads the preserved historical timeout inventory and pre-final result, deduplicates route/browser/viewport combinations, and performs ten fresh attempts each.

```bash
cd ../..
export HISTORY_EVIDENCE_DIR="$PWD/docs/research-history/browser-validation/2026-10-01-pre-final-validation/previous_active_package"
export PREFLIGHT_ROOT="$PWD/docs/research-history/browser-validation/2026-10-01-pre-final-validation/preflight"
node tools/browser_validation/stability_gate.mjs
```

The original gate output belongs in research history. Its 2026-10-01 run failed 8/12 configurations despite 116/120 individual attempts passing; do not erase or reinterpret those rows. The subsequent transport diagnosis isolated no-main-document Chromium timeouts and required a separate ten-logical-case targeted gate for each of the four problematic configurations. See `transport_diagnosis/TRANSPORT_TIMEOUT_DIAGNOSIS.md` and `FINAL_RUN_GO_NO_GO.md` before a final run.

## One fresh final candidate, only after a documented GO decision

Use a new empty candidate directory and an Asia/Manila run ID. `run.mjs` is the single shared Playwright runner for the responsive (64), Chromium/WebKit compatibility (32), and performance (80) matrices. It enforces a 30-second navigation maximum; performance retains a 5,000 ms usable-state threshold. Route content, navigation, overflow, JavaScript errors, and critical same-origin resources are checked. Navigation commits and route landmarks are measured separately from later load events.

```bash
export RUN_ID="BROWSER_VALIDATION_FINAL_$(TZ=Asia/Manila date +%Y%m%d_%H%M)_PHT"
export EVIDENCE_DIR="$(mktemp -d /tmp/pse-pulse-authoritative-browser-validation.XXXXXX)"
node tools/browser_validation/prepare.mjs start
node tools/browser_validation/run.mjs
node tools/browser_validation/lighthouse.mjs
node tools/browser_validation/prepare.mjs end
node tools/browser_validation/report.mjs
node tools/browser_validation/manifest.mjs
node tools/browser_validation/verify.mjs
```

`report.mjs` calculates results from the fresh raw rows and marks a candidate promotion-eligible only when all six categories pass and the homepage fingerprint matches. Responsive and compatibility cases allow at most one fresh-context retry after a strictly classified no-main-document transport failure; the first and final attempts remain visible. Application/UI failures and slow results do not qualify. The 80 performance trials are never retried or replaced. The required categories are mobile 16/16, tablet 16/16, laptop/desktop 32/32, Chromium/WebKit cross-browser 32/32, valid performance measurement 80/80, and at least 72/80 (90%) usable page loads within five seconds. A failed candidate stays in research history; never edit failed rows or rerun repeatedly to select a favorable result. Promotion to the active Chapter IV folder is a separate, reviewed, evidence-preserving action.

`manifest.mjs` refuses to overwrite an existing manifest. Run it after every evidence file is final; `verify.mjs` checks each listed file's SHA-256 and size. Keep `node_modules` and temporary Firefox profiles out of the evidence package.

For repository storage, screenshots are intentionally excluded to reduce size. Machine-readable CSV/JSON results and execution logs are authoritative. After a candidate is promoted, `prune_screenshots.mjs --dry-run` inventories images under the active and research-history browser-validation roots; `--apply` removes only image files, clears their CSV/JSON/Markdown references, and regenerates affected manifests; `--verify` checks the remaining manifest hashes and references. Do not use it to alter validation outcomes.
