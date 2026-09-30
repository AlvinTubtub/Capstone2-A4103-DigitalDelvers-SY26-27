# Chapter IV Follow-up Technical Validation

## Repository Under Test

- Repository: `https://github.com/AlvinTubtub/Capstone2-A4103-DigitalDelvers-SY26-27.git`
- Branch: `main`
- Initial commit SHA: `57fed9821850dc4aeff946433d32793b963b3ed0`
- Authoritative commit after `git pull --ff-only origin main`: `57fed9821850dc4aeff946433d32793b963b3ed0`
- Final commit SHA: `57fed9821850dc4aeff946433d32793b963b3ed0` (no code change)
- Validation date: 2026-09-30, Asia/Manila (UTC+08:00)
- Pull result: already up to date
- Pre-test tracked working-tree state: clean

The untracked evidence directory found during the first Phase 0 check was preserved without modification at the gitignored path `backend/artifacts/validation-preexisting/chapter4_followup_validation_2026-09-30_preexisting_20260930_1656`. A fresh evidence package was then created at the required path.

## Frontend Validation

| Command | Result | Elapsed | Evidence |
|---|---:|---:|---|
| `npm ci` | PASS | 5 seconds | `logs/01_frontend_npm_ci.log` |
| `npx tsc --noEmit` | PASS | 2 seconds | `logs/02_frontend_typescript.log` |
| `npm run build` | PASS | 15 seconds | `logs/03_frontend_build.log` |

`npm ci` reported its warnings and advisories without filtering. No application change was made in response to non-blocking advisories.

## Corporate-Action Screening

- Initial command: `python -m pytest -q tests/test_corporate_action_screening.py`
- Initial result: FAIL — 8 passed, 1 failed in 13.44 seconds; logger elapsed time 15 seconds
- Original failing test: `tests/test_corporate_action_screening.py::test_deterministic_evidence_and_no_local_paths`
- Exact failure: `_build_evidence(screening.FORMAL_ROOT)` constructed `FormalRunArchive("FORECASTPH_FORMAL_20260911_01", root=backend/artifacts/evaluations/formal-runs)`, and `verify_integrity()` returned false because the expected archive was absent from the fresh clone.
- Root cause: the deterministic regression test has a runtime dependency on an authentic finalized formal archive stored under intentionally gitignored `backend/artifacts/`. A clean checkout does not contain that archive.
- Authentic archive available: YES
- Verified source: `/Users/alvintubtub/Downloads/Capstone2-A4103-DigitalDelvers-SY26-27/backend/artifacts/evaluations/formal-runs/FORECASTPH_FORMAL_20260911_01`
- Source verification: state `FINALIZED`; `verify_integrity()` returned `True`
- Correction: copied only the verified archive with `rsync -a` into the validation clone's expected gitignored runtime path.
- Restored-copy verification: state `FINALIZED`; `verify_integrity()` returned `True`
- Final command: `python -m pytest -q tests/test_corporate_action_screening.py`
- Final result: PASS — 9 passed in 2.15 seconds; logger elapsed time 3 seconds
- Code/test correction: none
- Local commit: not applicable

The first source-verification command failed before inspecting candidates because the evidence helper did not initially add the backend root to Python's import path. That failed invocation is preserved in `logs/05_source_formal_archive_integrity.log`. The corrected evidence-helper invocation is separately preserved in `logs/05_source_formal_archive_integrity_retry.log`; no archive or research file was changed by the failed invocation.

## Full Backend Suite

- Executed: YES
- Command: `python -m pytest -q`
- Result: FAIL — 424 passed, 49 failed, 2 warnings in 77.38 seconds; logger elapsed time 78 seconds
- Failure scope: all 49 failures are in `tests/test_research_result_export.py`.
- Diagnosed cause: `FORECASTPH_SUPPLEMENTARY_20260921_03` is absent from `backend/artifacts/evaluations/supplementary-runs`, so `SupplementaryEvidenceArchive.verify_integrity()` fails on the missing `integrity_manifest.json`. The resulting fail-closed exception prevents the affected research-result export tests from reaching their individual assertions.
- Follow-up action: none. The requested external-search exception was limited to the historical formal-run archive, so no external supplementary archive was searched for or copied. No unrelated source/test workaround was made.

## Research Integrity Statement

No finalized formal research result was modified, overwritten, regenerated, retrained, or changed merely to make testing pass. `git diff -- backend/research-result` produced no output. The restored historical formal archive remains under gitignored `backend/artifacts/` and was not added to Git. The corporate-action assertion was not removed, skipped, xfailed, weakened, or bypassed. No new formal experiment was created with `FORECASTPH_FORMAL_20260911_01`.

## Evidence Files

### Records and helpers

- `CORRECTIVE_ACTION.md`
- `backend_environment.txt`
- `environment_before.txt`
- `FINAL_SUMMARY.txt`
- `final_repository_state.txt`
- `frontend_packages.txt`
- `run_logged.sh`
- `verify_formal_archives.py`
- `verify_supplementary_archives.py`

### Logs

- `logs/00_repository_state_after_pull.log`
- `logs/01_frontend_npm_ci.log`
- `logs/02_frontend_typescript.log`
- `logs/03_frontend_build.log`
- `logs/03a_backend_venv_create.log`
- `logs/03b_backend_pip_upgrade.log`
- `logs/03c_backend_requirements_install.log`
- `logs/04_corporate_action_before_fix.log`
- `logs/04a_formal_archive_dependency_investigation.log`
- `logs/04b_formal_archive_search.log`
- `logs/05_source_formal_archive_integrity.log`
- `logs/05_source_formal_archive_integrity_retry.log`
- `logs/05a_archive_restore_copy.log`
- `logs/06_restored_formal_archive_integrity.log`
- `logs/07_corporate_action_after_archive_restore.log`
- `logs/08_backend_full_pytest.log`
- `logs/08a_backend_full_failure_diagnosis.log`
- `logs/09_full_suite_failure_analysis.log`
- `logs/09a_continuation_state.log`
- `logs/10_research_integrity_and_repository_status.log`
- `logs/10_supplementary_dependency_trace.log`
- `logs/11_local_supplementary_archive_check.log`
- `logs/11_local_supplementary_archive_check_retry.log`
- `logs/13_source_supplementary_archive_integrity.log`
- `logs/13a_supplementary_archive_search.log`
- `logs/13b_recovered_supplementary_archive_integrity.log`
- `logs/13c_supplementary_archive_restore_copy.log`
- `logs/14_restored_supplementary_archive_integrity.log`
- `logs/15_research_result_export_after_restore.log`
- `logs/16_backend_full_pytest_after_supplementary_restore.log`
- `logs/17_research_integrity_postcheck.log`
- `logs/18_final_continuation_evidence_verification.log`
- `logs/18_final_continuation_evidence_verification_retry.log`

### Screenshots

- `screenshots/01_frontend_npm_ci.png`
- `screenshots/02_frontend_typescript.png`
- `screenshots/03_frontend_build_1.png`
- `screenshots/03_frontend_build_2.png`
- `screenshots/04_corporate_action_before_fix.png`
- `screenshots/07_corporate_action_after_archive_restore.png`
- `screenshots/08_backend_full_pytest.txt`
- `screenshots/15_research_result_export_after_restore.png`
- `screenshots/16_backend_full_pytest_after_supplementary_restore.png`

## Full Backend Suite Supplementary-Archive Corrective Action

### Original Full-Suite Result

- Command: `python -m pytest -q`
- Result: 424 passed, 49 failed, 2 warnings in 77.38 seconds
- Commit: `57fed9821850dc4aeff946433d32793b963b3ed0`

### Failure Scope

All 49 failures came from `tests/test_research_result_export.py`. The preserved traceback contains 47 direct `ResearchResultExportError` instances and two assertion messages wrapping the same exception. Every one names the missing `backend/artifacts/evaluations/supplementary-runs/FORECASTPH_SUPPLEMENTARY_20260921_03/integrity_manifest.json` path. No unrelated failure group was found.

### Root Cause

`scripts.export_research_results.load_authoritative_evidence()` requires both the finalized formal archive and the finalized supplementary evidence package. The formal archive was already restored and verified. The supplementary package is intentionally outside Git, so it was absent from the clean validation clone. Its fail-closed verifier rejected the missing runtime package before 49 research-result export tests could reach their individual assertions.

### Historical Archive

- Package ID: `FORECASTPH_SUPPLEMENTARY_20260921_03`
- Historical formal source: `FORECASTPH_FORMAL_20260911_01`
- Found source path: `/Users/alvintubtub/Downloads/Capstone2-A4103-DigitalDelvers-SY26-27/backend/artifacts/evaluations/supplementary-runs/FORECASTPH_SUPPLEMENTARY_20260921_03`
- Source verification as found: FAIL only on `exact_file_set`, because Finder had added an unmanifested `.DS_Store`. State, schemas, package/source identity, every manifested file hash and size, and both aggregate hashes passed.
- Recovery: copied the source read-only to `/tmp/pse-pulse-supplementary-recovery-20260930`, excluding only `.DS_Store`; no manifested byte and no source file was changed.
- Manifest-clean recovery verification: PASS. State `FINALIZED`; exact file set, hashes, sizes, aggregate, all 11 semantic payloads, and formal state/integrity/aggregate/manifest linkage passed.
- Restored destination: `/Users/alvintubtub/Desktop/PSE_Pulse_Validation_2026-09-30_163754/backend/artifacts/evaluations/supplementary-runs/FORECASTPH_SUPPLEMENTARY_20260921_03`
- Destination verification: PASS with the same full repository verification result.

### Targeted Regression Result

- Command: `python -m pytest -q tests/test_research_result_export.py`
- Result: 92 passed
- Execution time: 28.34 seconds; logger elapsed time 29 seconds
- Commit: `57fed9821850dc4aeff946433d32793b963b3ed0`

### Final Full Backend Result

- Command: `python -m pytest -q`
- Result: 473 passed, 2 warnings
- Execution time: 55.96 seconds; logger elapsed time 56 seconds
- Commit: `57fed9821850dc4aeff946433d32793b963b3ed0`

### Corrective Action Classification

No application source-code correction was required. The failures were caused by a clean-checkout/runtime reproducibility dependency because the finalized supplementary archive is intentionally outside Git. Only the verified historical runtime artifact was restored under gitignored `backend/artifacts/`.

### Research Integrity

- No finalized formal result was altered.
- No finalized supplementary result was altered.
- No test assertion was skipped, xfailed, removed, mocked away, weakened, or bypassed.
- No historical artifact was regenerated under an old package or run ID.
- `git diff -- backend/research-result` produced no output after the passing full-suite run.
- No source file changed, no commit was created, and nothing was pushed.
