# Browser-validation harness

This isolated Node package validates the live PSE Pulse site. It does not change the application or forecasting data.

From the repository root, install the exact dependencies and browsers:

```bash
cd tools/browser_validation
npm ci
npx playwright install chromium firefox webkit
```

Create a unique Asia/Manila run ID and an empty evidence directory, then run the stages in order. Use an absolute path for `EVIDENCE_DIR`. If an earlier package exists, choose a new subdirectory rather than overwriting it.

```bash
export RUN_ID="BROWSER_VALIDATION_$(TZ=Asia/Manila date +%Y%m%d_%H%M)_PHT"
export EVIDENCE_DIR="$(git rev-parse --show-toplevel)/backend/research-result/system_testing/browser_validation/$RUN_ID"
node prepare.mjs start
node run.mjs
node lighthouse.mjs
node prepare.mjs end
node report.mjs
```

`run.mjs` performs 64 responsive cases, 48 planned cross-browser cases, and 80 unthrottled fresh-context page-load trials. `lighthouse.mjs` adds 24 supplementary measurements. A browser-engine launch failure is recorded as `BLOCKED`, not as an application failure. A navigation timeout during page-load timing counts against the five-second threshold and its elapsed duration is a censored lower bound.

The report stage hashes every evidence file except `test_manifest.csv` itself; a manifest cannot contain its own stable hash. Keep the package lockfile with this harness and do not commit `node_modules` or Playwright browser caches.

Screenshots were intentionally excluded from repository storage to reduce repository size. Machine-readable CSV/JSON results and execution logs are the authoritative evidence. Screenshot path fields are blank; validation measurements and pass/fail results are unchanged.
