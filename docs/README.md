# PSE Pulse Documentation

This index points team members, advisers, reviewers, and maintainers to the current documentation without moving provenance-sensitive files.

## Start here

- [Project overview](../README.md)
- [Backend technical guide](../backend/README.md)
- [Frontend and routes guide](../frontend/README.md)

## Current technical documentation

- [Frontend forecast-data contract](frontend-forecast-contract.md)
- [PSE Pulse branding migration](branding-migration.md)

## Final research evidence

The [frozen research-result evidence index](../backend/research-result/README.md) explains the authoritative formal result tables under `backend/research-result/`. Those CSV files are deterministic, read-only submission evidence.

## Data provenance and corrections

Data-source, recovery, verification, and correction records remain in [`backend/data/corrections/`](../backend/data/corrections/):

- [Historical raw-data provenance recovery](../backend/data/corrections/historical_raw_provenance_recovery.md)
- [Missing-session correction application](../backend/data/corrections/pse_dqr_missing_sessions_application.md)
- [Missing-session source verification](../backend/data/corrections/pse_dqr_missing_sessions_verification.md)

These records document provenance-sensitive work and must not be relocated or rewritten for presentation purposes.

## Historical research material

See the [research-history archive guide](research-history/README.md). Archived material can describe older datasets, statistics, URLs, or methodology drafts and is not the current authoritative research-result package.
