# Final PSE Pulse UAT evidence — 2026-10-16

This directory contains only aggregate outputs derived from the researcher-supplied final questionnaire PDF and complete Google Forms XLSX response sheet. The private workbook and PDF remain outside the repository. Do not commit either source workbook, raw emails, or row-level free text.

## Reproduce

From this directory, with Python 3 and `pandas`, `numpy`, `openpyxl`, `matplotlib`, `IPython`, `nbformat`, and `nbclient` installed:

```bash
python uat_analysis.py --workbook "/path/to/private/responses.xlsx"
export PSE_PULSE_UAT_WORKBOOK="/path/to/private/responses.xlsx"
jupyter nbconvert --to notebook --execute --inplace PSE_Pulse_UAT_Analysis_2026-10-16.ipynb
```

The first command regenerates the mapping, nine aggregate CSVs, and source-validation note. The notebook reruns the same calculations and displays the full tables and 11 pastel Matplotlib figures. Keep the workbook path outside the repository. The notebook does not print it.

## Read first

- `UAT_DATA_VALIDATION.md`: consent, duplicates, missingness, checksum, and form-version caveat.
- `UAT_RESULTS_AND_DISCUSSION.md`: Chapter IV evidence and interpretations.
- `UAT_CHAPTER5_EVIDENCE.md`: conclusions, recommendations, and limits.
- `UAT_ANALYSIS_VALIDATION.md`: execution and verification record.
- `UAT_MANUSCRIPT_REPLACEMENT_GUIDE.md`: review-ready replacement plan for manuscript Tables 72–77 and related Chapter IV/V prose.
- `uat_question_mapping.json`: exact workbook headers and scale mapping for all 47 rating items plus profile and qualitative fields.

The requirement alignment uses the **current Capstone 2 Chapter III Requirements Traceability Matrix, Table 9**, in `MO-IT200D2 _ A4103 Group 4 Capstone 2 Paper (3).docx`. The older integrated stakeholder RTM CSV is superseded where definitions differ: current FR-05 includes company/sector browsing and sector-peer context; current FR-10 concerns comparative model-performance evidence. The `pooled_item_response_favorable_pct` field counts repeated item responses and is not a participant-level acceptance rate. UAT classifications describe perception or an applicable rating component only; functional correctness, nonfunctional technical criteria, and forecast accuracy require their separate evidence.

The available pre-response research methodology documents an 80% stakeholder acceptance criterion, corresponding to at least seven favorable responses among eight participants. The final UAT ratings satisfy the numerical favorable-response component where applicable. However, formal overall UAT acceptance remains pending verification of the approved criterion's scope, unaided core-task completion, and unresolved Critical/High-severity defect status. Adviser approval timing and prespecified mapping of the revised questionnaire to the designated acceptance items were not independently established. The repository's October 1 notebook supplied only the visual presentation reference; no previous statistics were reused.
