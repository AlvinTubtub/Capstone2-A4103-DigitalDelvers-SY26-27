# Chapter IV Targeted Test Evidence — 2026-09-30

This directory contains commit-ready evidence from a targeted automated validation run of the PSE Pulse repository.

Recommended repository destination:

`docs/test-evidence/2026-09-30-targeted-validation/`

Contents:

- `TEST_EXECUTION_REPORT.md` — human-readable formal report and limitations.
- `targeted_test_summary.csv` — machine-readable summary of collected/executed/pass/fail counts.
- `environment.txt` — repository commit and execution environment.
- `rerun_targeted_tests.sh` — reproducible commands for the same targeted groups.
- `logs/` — raw pytest output for each executed group.

The evidence records **314/314 passing portable core tests** and **322/323 passing targeted tests overall**. The sole targeted failure depends on a gitignored formal-run archive absent from the supplied ZIP; see the formal report for details.

This directory should not be described as a complete 473-test-suite pass, and it does not include UAT or final frontend npm build/type-check evidence.
