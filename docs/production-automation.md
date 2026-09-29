# PSE Pulse Production Automation

## 1. Purpose

This document describes operational PSE end-of-day (EOD) updates and production-model scheduling after the frozen formal research experiment. It does not redefine the formal research protocol. The two Cron-job.org times below are user-confirmed external configuration; the repository verifies the GitHub workflow and backend behavior, but cannot verify the current Cron-job.org dashboard settings.

## 2. Formal research and operational separation

The formal research run is `FORECASTPH_FORMAL_20260911_01`, with a `2026-09-11` cutoff. Later operational OHLCV observations and next-session forecasts do not change its frozen dataset, selected configurations, holdout predictions, RMSE/MAE/MASE/R², statistical tests, model winner counts, or research conclusions. The operational workflow does not rerun the formal experiment.

## 3. Automation architecture

```text
Official PSE EOD publication
        ↓
Cron-job.org scheduled trigger (external configuration)
        ↓
Authenticated GitHub dispatch request: update-pse-data
        ↓
PSE EOD Update and Persisted Model Forecast
(.github/workflows/update_pipeline.yml)
        ↓
Restore and validate compatible persisted production artifacts
        ↓
Ingest available official EOD reports; validate canonical raw OHLCV
        ↓
Only when backend/data/raw changed:
  resolve prior prospective outcomes → infer from persisted models
  → issue next-session forecasts and Naive → report drift
  → validate generated frontend JSON
        ↓
Commit and push changed raw, ledger, and frontend forecast files;
if no files changed, commit step is a no-op
```

The ingestion command starts on the calendar day after the latest configured raw observation and ends on the current Philippine date. It requests reports by date; an HTTP 404 is treated as unpublished, not as a successful market observation or a fatal error. Valid new quotations are merged into canonical raw CSVs without overwriting conflicting historical rows. The workflow uses `git diff --quiet -- data/raw` after successful ingestion to decide whether to run downstream forecast and ledger stages.

## 4. Cron-job.org scheduling strategy

| Schedule role | Days | Time | Purpose |
| --- | --- | --- | --- |
| Primary | Tuesday–Friday | 4:00 PM PHT | First normal post-session EOD attempt |
| Fallback | Monday–Friday | 5:30 PM PHT | Recovery attempt when official EOD quotes are published later |

Times use Philippine Time (`Asia/Manila`, UTC+8). Tuesday–Friday can intentionally receive both trigger attempts; that overlap is not a duplicate configuration error. Monday has only the 5:30 PM attempt. Both jobs target the same operational dispatch and workflow, not independent forecasting processes. The schedule is configured in Cron-job.org, not in repository YAML. A dashboard capture can later support Chapter IV implementation evidence; no private job configuration or screenshot is added here.

## 5. GitHub dispatch interface

Cron-job.org is configured to make an authenticated GitHub request that creates the `repository_dispatch` event type `update-pse-data`. [The EOD workflow](../.github/workflows/update_pipeline.yml) accepts that event and manual `workflow_dispatch`. It has **no internal GitHub Actions `schedule` trigger**. The authentication material and dispatch request details are not public documentation.

## 6. Primary and fallback execution semantics

| Situation | Verified workflow behavior |
| --- | --- |
| 4:00 PM finds a new valid official report | Ingestion merges new raw rows; raw validation passes; changed raw data enables outcome resolution, persisted inference, forecast issuance, drift reporting, frontend validation, and an operational commit if files changed. |
| 4:00 PM finds no published report | An unpublished/404 date is nonfatal. With no raw CSV change, outcome resolution, inference, forecast issuance, drift reporting, and frontend JSON regeneration are skipped. Raw validation and the final no-change commit check still run. |
| 5:30 PM finds a report published after 4:00 PM | The later run starts from the latest raw date, can ingest the newly available report, and follows the same changed-raw path. It is not a separate pipeline. |
| 5:30 PM follows a successful primary run | The later checkout includes the previously committed raw observation. With no additional raw change, downstream inference/ledger/frontend stages are skipped and the commit step has nothing to commit. |

If a report was downloaded but yielded no new rows, the workflow likewise uses the actual raw-file change guard—not the mere presence of a PDF—to decide whether to forecast. The ingestion merger treats identical existing symbol/date values as no-ops and rejects conflicting historical values. These guards explain the normal repeated-trigger behavior; they do not guarantee that every external dispatch will run at its nominal time or that upstream PSE publication will succeed.

## 7. Persisted-model inference

The EOD job first locates a successful compatible production-artifact package, validates its manifest and completeness, restores it, and validates it again before ingestion. If no valid package exists, the job fails closed. Only a successful ingestion that changes canonical raw CSVs enables `scripts.forecast_all --all --verbose`; this command loads persisted models and exports operational frontend forecasts. It does not tune hyperparameters, select models, refit weights, or execute formal research analysis.

## 8. Prospective forecast ledger

When new raw data arrive, the workflow resolves matching prior pending forecasts using the newly observed target Close, then issues next-session principal-model and Naive forecasts. Forecast issuance precedes knowledge of that next target Close. The ledger appends outcome events without changing earlier issued predictions. Drift reporting uses resolved prospective records and does not initiate training or deployment. This operational evidence remains separate from the frozen formal experiment.

## 9. Production model training and refitting

[PSE Fresh Model Training](../.github/workflows/train_models.yml) uses **native GitHub Actions cron**, not Cron-job.org. Its verified schedule is `0 0 28 2,5,8,11 *`: 00:00 UTC, or 8:00 AM PHT on February 28, May 28, August 28, and November 28. It also supports manual `workflow_dispatch`. This separate workflow runs controlled fresh training, evaluation, and production refitting and uploads a validated artifact package. It does not retroactively change frozen formal research evidence.

## 10. Concurrency and repeated triggers

Both workflows declare `concurrency.group: pse-pipeline` with `cancel-in-progress: false`. They are not configured to run concurrently within that group, and a new trigger does not cancel an in-progress run. A busy group may delay an attempt; the configuration should not be read as a guarantee that every queued attempt executes at its nominal clock time. The EOD raw-change guard and conflict-safe merge handle the normal later fallback after an earlier successful EOD update.

## 11. Failure handling and manual recovery

GitHub Actions exposes job status and logs. Non-404 download failures, parsing/validation failures, conflicting historical OHLCV, missing compatible production artifacts, or frontend validation failure return a failing workflow rather than publishing a completed update. The 5:30 PM job offers a later attempt for delayed publication, and operators can invoke `workflow_dispatch` manually. No external alerting integration is asserted here. The final commit step runs only after prior workflow steps succeed and stages only canonical raw CSVs, prospective ledger events, and operational forecast JSON; it skips the commit when nothing changed.

## 12. Security

External dispatch authentication belongs in configured secret storage, not in this repository or public documentation. Do not publish GitHub credentials, authorization headers, private dispatch URLs, or Cron-job.org private configuration. Backend artifact restoration and provider access occur in the server-side workflow; frontend users cannot trigger model training through the website.

## 13. Schedule summary

| Process | Scheduler | Schedule (Asia/Manila) | Training? |
| --- | --- | --- | --- |
| EOD operational primary | Cron-job.org | Tuesday–Friday, 4:00 PM PHT | No |
| EOD operational fallback | Cron-job.org | Monday–Friday, 5:30 PM PHT | No |
| Production model training/refitting | GitHub Actions | Quarterly: February/May/August/November 28, 8:00 AM PHT | Yes |

## 14. Related repository files

- [Operational EOD workflow](../.github/workflows/update_pipeline.yml)
- [Quarterly training workflow](../.github/workflows/train_models.yml)
- [Backend guide](../backend/README.md)
- [Frontend forecast-data contract](frontend-forecast-contract.md)
- [EOD ingestion entry point](../backend/scripts/update_eod.py)
- [Persisted inference entry point](../backend/scripts/forecast_all.py)
- [Prospective ledger entry point](../backend/scripts/update_forecast_ledger.py)
