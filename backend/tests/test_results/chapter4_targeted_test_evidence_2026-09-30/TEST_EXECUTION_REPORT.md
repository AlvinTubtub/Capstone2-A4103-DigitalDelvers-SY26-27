# PSE Pulse Targeted Technical Test Execution Report

**Purpose:** Commit-ready evidence for Chapter IV technical validation before final UAT completion.

## Repository under test

- **Commit:** `ed290972e50064f922e9c5817d8d2bb949339141`
- **Commit subject:** `Document Cron-job.org EOD scheduling`
- **Commit timestamp:** `2026-09-29T22:29:19+08:00`
- **Source:** User-supplied fresh repository ZIP
- **Execution environment:** OpenAI sandbox; environment details are retained in `environment.txt`

## Scope

Pytest discovered **473 tests** in the repository. Rather than claim execution of the entire suite, this evidence package records a Chapter-IV-focused targeted run covering the data foundation, formal methodology, all three principal model implementations, evaluation/statistics, frontend-data contract, operational inference, production workflows, artifact handling, and corporate-action screening.

### Results

| Group | Evidence area | Executed | Passed | Failed | Status |
|---|---|---:|---:|---:|---|
| G01 | Data foundation, formal scope, data quality, chronology and split | 48 | 48 | 0 | PASS |
| G02 | LIR, ARIMA, LSTM, model selection, evaluation and statistics | 96 | 96 | 0 | PASS |
| G03 | Frontend exporter, frontend validation and reporting semantics | 33 | 33 | 0 | PASS |
| G04 | Production inference, forecast ledger, drift monitoring, manifest and workflows | 43 | 43 | 0 | PASS |
| G05 | Calendar, ingestion, artifacts, exports, diagnostics and clean imports | 94 | 94 | 0 | PASS |
| G06 | Corporate-action screening | 9 | 8 | 1 | PARTIAL — environment dependency |
| **Portable core total (G01–G05)** |  | **314** | **314** | **0** | **PASS** |
| **All targeted groups** |  | **323** | **322** | **1** | **PARTIAL** |

## Corporate-action test exception

The single G06 failure was:

`test_deterministic_evidence_and_no_local_paths`

The failure occurs because the test attempts to reconstruct evidence from the formal-run archive at approximately:

`backend/artifacts/evaluations/formal-runs/FORECASTPH_FORMAL_20260911_01/`

That runtime archive is intentionally gitignored and was not present in the supplied repository ZIP. The integrity precondition therefore failed before the deterministic evidence reconstruction could proceed. The other **8 corporate-action tests passed**.

macOS `.DS_Store` metadata found in the extracted ZIP was removed from the temporary working copy before the corporate-action test was rerun; the removed paths are recorded in `logs/06_ds_store_removed.txt`.

This exception should be described as a **repository/environment reproducibility dependency**, not as evidence that the corporate-action screening result itself failed.

## What this report supports

These results provide executed technical evidence for Chapter IV discussion of:

- formal dataset and chronology controls;
- data-quality validation;
- LIR, ARIMA and LSTM implementation rules;
- model selection and evaluation functions;
- statistical procedures;
- frontend publication and reporting semantics;
- operational inference and prospective forecast-ledger behavior;
- drift monitoring and production-manifest rules;
- workflow definitions, PSE calendar and ingestion behavior; and
- corporate-action screening, subject to the documented formal-archive dependency.

## What this report does not support by itself

This package is **not** evidence that all 473 collected pytest tests passed. It also does not replace:

- final User Acceptance Testing with the eight stakeholder participants;
- final browser-based responsive and performance testing;
- final frontend `npx tsc --noEmit` result; or
- final frontend `npm run build` result.

Those results should be documented separately when executed.

## Suggested Chapter IV wording

> A targeted automated technical-validation run was executed against repository commit `ed290972e50064f922e9c5817d8d2bb949339141`. The selected high-value test groups covered the formal data foundation, forecasting models, evaluation and statistical procedures, frontend-data contract, production inference, operational workflows, artifact handling, and corporate-action screening. Of 323 targeted tests executed, 322 passed. The 314 portable core tests all passed. One corporate-action reproducibility test could not complete because it requires the gitignored frozen formal-run archive, which was not included in the supplied repository copy; the remaining eight corporate-action tests passed. This targeted run is reported separately from the full repository suite and from stakeholder UAT.

Use this wording only together with the documented commit and evidence package, and replace it if the research team later runs a newer local/CI validation against a different commit.
