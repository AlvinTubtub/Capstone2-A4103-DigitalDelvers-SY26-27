# Research Question-to-Evidence Map

This is the reviewer-facing companion to the [structured RQ1–RQ12 evidence map](research-question-evidence-map.csv). The CSV is authoritative for exact repository paths, methods, Chapter IV working outputs, statuses, and remaining gaps. No current repository manuscript establishes verified final wording for all twelve questions, so the short labels below follow the documented RQ scopes; synchronize exact wording with the approved manuscript before submission.

Formal quantitative evidence is frozen under run `FORECASTPH_FORMAL_20260911_01` at the 2026-09-11 cutoff. This map creates no new result or research conclusion. Operational production data after that cutoff is separate from the frozen formal study.

| RQ | Short question | Primary evidence | Status | Key guardrail / gap |
| --- | --- | --- | --- | --- |
| RQ1 | Budding-trader and stakeholder needs | No finalized stakeholder evidence in the repository | PENDING | Obtain anonymized responses, an approved requirements baseline, and traceability; features alone do not prove needs. |
| RQ2 | Official PSE OHLCV collection and scope | [Data provenance](../backend/research-result/data_provenance.csv), [formal scope](../backend/research-result/formal_scope.csv) | COMPLETE | The source reference is provider-level; current operational observations do not change the frozen study. |
| RQ3 | Formal dataset quality | [Quality results](../backend/research-result/data_quality.csv), [screening rules](../backend/research-result/data_quality_rules.csv) | COMPLETE | APX's material-discontinuity REVIEW is neither a dataset FAIL nor a confirmed corporate action. |
| RQ4 | Chronological LIR, ARIMA, and LSTM development | [Formal scope](../backend/research-result/formal_scope.csv), [selected configurations](../backend/research-result/selected_configurations.csv) | COMPLETE | Formal development differs from daily inference without retraining. |
| RQ5 | Selected configurations | [Selected configurations](../backend/research-result/selected_configurations.csv) | COMPLETE | Do not substitute current production fitted state for formal selections. |
| RQ6 | Common-holdout accuracy | [Holdout metrics](../backend/research-result/holdout_metrics.csv) | COMPLETE | R² is supplementary, not percentage accuracy; all methods use aligned target dates. |
| RQ7 | Principal models versus Naive | [Benchmark DM evidence](../backend/research-result/benchmark_vs_naive_dm.csv) | COMPLETE | Lower RMSE is descriptive; statistical significance requires finalized DM evidence. |
| RQ8 | Statistical method comparison | [Within-company DM](../backend/research-result/within_company_dm.csv), [across-company tests](../backend/research-result/across_company_tests.csv) | COMPLETE | Six pairs use two loss families and separate Holm corrections. Friedman did not reject (p = 0.6278003229833597 at α = 0.05), so Wilcoxon post-hoc was not performed. |
| RQ9 | Principal-model winners | [Per-company winners](../backend/research-result/principal_winners.csv), [win summary](../backend/research-result/principal_win_summary.csv) | COMPLETE | LIR 4, ARIMA 7, LSTM 4; none reached the descriptive 8-of-15 strict majority. This is not a significance test. |
| RQ10 | Selected sector peers | [Sector-peer summary](../backend/research-result/sector_peer_summary.csv) | COMPLETE | Findings apply to three selected companies per sector, not the entire PSE sector population. |
| RQ11 | PSE Pulse forecast integration | [Frontend data contract](frontend-forecast-contract.md), [frontend guide](../frontend/README.md) | COMPLETE | The system implements integration, but that does not establish usability or UAT acceptance. |
| RQ12 | Requirements and user-centered system evaluation | No finalized system-evaluation evidence in the repository | PENDING | Collect requirements traceability, system test results, usability/UAT results, and defect retests. Automated tests do not replace UAT. |

Status summary: **10 COMPLETE, 0 PARTIAL, 2 PENDING**. RQ1 and RQ12 need empirical stakeholder or system-evaluation evidence; no participant responses or acceptance results are inferred from the existing implementation. Planned `docs/system-evaluation/` outputs are gaps, not cited as files that already exist.
