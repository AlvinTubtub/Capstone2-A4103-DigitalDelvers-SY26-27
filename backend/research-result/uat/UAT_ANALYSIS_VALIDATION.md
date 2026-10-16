# Final UAT analysis validation — 2026-10-16

## Execution and inputs

- Git branch: `main`; starting and final HEAD: `ab561b04fde28f592710e22349f4bcebefeaf9a5` (`chore: remove UAT research results`). Its parent contained the October 1 notebook, inspected only for headings, pastel charts, table presentation, and spacing. The deleted directory was absent before work began.
- Source: researcher-supplied final 23-page questionnaire PDF and eight-row, 60-column XLSX, sheet `Form Responses 1`. The PDF was read only. Source workbook checksum, consent, duplicates, and missingness appear in `UAT_DATA_VALIDATION.md`.
- The current Capstone 2 Chapter III RTM (Table 9) is the requirement-definition authority. FR-05 includes browsing and sector-peer context; FR-10 means comparative model-performance evidence. The older integrated stakeholder RTM CSV differs and is not used for current definitions. The available Capstone 1 and Capstone 2 methodologies document an 80% / 7-of-8 criterion before the final submissions; formal adviser approval timing and its exact revised-item scope were not independently established.

## Commands and results

1. `/opt/anaconda3/bin/python uat_analysis.py --workbook "/path/to/private/response.xlsx"` — passed. Regenerated nine aggregate CSVs, the mapping JSON, and source-validation note. Only the requirement-alignment CSV changed; the eight statistical CSVs remained byte-identical to their verified baseline.
2. `/opt/anaconda3/bin/python -m unittest discover -s . -p 'test_*.py' -v` — five UAT logic tests passed: five-point scoring, schema-drift rejection, distinct-respondent thematic counting, current Chapter III FR-05/FR-10 definitions, and final 8-respondent/47-item/376-rating preservation with the obsolete question absent.
3. Jupyter `nbclient.NotebookClient(...).execute()` on `PSE_Pulse_UAT_Analysis_2026-10-16.ipynb` — passed under a clean Python 3 kernel after the RTM correction. All 24 code cells executed in order; 25 Markdown cells, 11 embedded PNG charts, no error outputs. The first sandboxed attempt in the original implementation could not open a local kernel socket; the authorized local-kernel rerun succeeded.
4. Notebook format, table arithmetic, mapping, and privacy assertions — passed. All 47 mapped rating items reconcile to 376 valid item responses. Every item's five category counts sum to its valid count, and favorable counts equal scores 4 plus 5. Eight valid responses per item; no missing rating values.
5. Regeneration preserved byte-identical values in all eight previously verified statistical CSVs. The ninth CSV, `uat_requirement_alignment.csv`, now uses the 16 exact requirement definitions in the current Chapter III Table 9; all 16 were compared against that table and matched.
6. `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_research_result_export.py -k 'authoritative_substantive_csv_hashes_are_frozen' -q` — one passed, 91 deselected. This checked the frozen formal research CSV hashes without invoking an exporter that writes formal results.
7. Jupyter HTML export rendered all 11 notebook charts. Notebook tables use wrapped HTML cells so the current FR-05 and FR-10 definitions appear in full. The corrected Chapter IV tables and `UAT_MANUSCRIPT_REPLACEMENT_GUIDE.md` were checked against the statistical CSVs. No calculation changed to obtain a different acceptance result.

## Privacy and visual review

No email-shaped identifiers, private source path, raw free text, or respondent-level output appears in published text or notebook text outputs. Chart PNG data were excluded from text-pattern scanning and visually inspected. All 11 charts are embedded; the navigation and device-comparison figures were inspected for readable labels, complete titles, legends, and data labels. The private workbook remains outside the repository. No row-level CSV was created.

## Remaining limits

The workbook lacks per-response form-version metadata; matching final headers, all matrix rows, and observed scale labels establish compatibility but do not independently prove each respondent's live form version. The documented 80% / 7-of-8 threshold is not a retrospective invention. Its formal application remains pending confirmation of approved scope, unaided core-task completion, and unresolved Critical/High-severity defect status. The local manuscript draft retains old UAT statements; Tables 72–77 and related Chapter IV/V text require researcher revision using the new replacement guide. The full backend suite, frontend build, and objective performance/viewport tests were not rerun because this change is confined to UAT evidence and documentation. No files outside this UAT directory were changed; no commit or push occurred. No UAT test failed; 91 unrelated research-export tests were deselected from the targeted frozen-hash run.
