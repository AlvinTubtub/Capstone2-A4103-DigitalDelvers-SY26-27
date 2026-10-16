# Final PSE Pulse UAT evidence — 2026-10-16

This directory contains the executed analysis notebook, reproducible analysis code, a question mapping, and aggregate results derived from the researcher-supplied final questionnaire PDF and complete Google Forms XLSX response sheet. The private workbook and PDF remain outside the repository. Do not commit either source workbook, raw emails, or row-level free text.

## Reproduce

From this directory, with Python 3 and `pandas`, `numpy`, `openpyxl`, `matplotlib`, `IPython`, `nbformat`, and `nbclient` installed:

```bash
python uat_analysis.py --workbook "/path/to/private/responses.xlsx"
export PSE_PULSE_UAT_WORKBOOK="/path/to/private/responses.xlsx"
jupyter nbconvert --to notebook --execute --inplace PSE_Pulse_UAT_Analysis_2026-10-16.ipynb
```

The first command validates consent, duplicate keys, questionnaire structure, and rating labels, then regenerates the question mapping JSON and nine aggregate CSVs. The notebook reruns the same calculations and displays the full tables and 11 pastel Matplotlib figures. Keep the workbook path outside the repository. The notebook does not print it. Run the five UAT unit tests with `python -m unittest discover -s . -p 'test_*.py' -v`.

## Retained files

- `PSE_Pulse_UAT_Analysis_2026-10-16.ipynb`: executed tables, 11 graphs, Chapter IV/V interpretations, and methodology limits.
- `uat_analysis.py` and `test_uat_analysis.py`: reproducible aggregation and validation tests.
- `uat_question_mapping.json`: exact workbook headers and scale mapping for all 47 rating items plus profile and qualitative fields.
- `uat_participant_profile.csv`: aggregate experience, device, browser, and theme counts.
- `uat_navigation_usability_summary.csv`: 21 navigation/usability items.
- `uat_feature_helpfulness_summary.csv`: nine feature-helpfulness items.
- `uat_desktop_experience_summary.csv`: eight desktop/laptop items.
- `uat_mobile_experience_summary.csv`: nine tablet/mobile items.
- `uat_device_comparison.csv`: descriptive comparisons of related device items.
- `uat_qualitative_themes.csv`: aggregate Q34–Q36 theme counts.
- `uat_requirement_alignment.csv`: UAT perception evidence mapped to the current Chapter III RTM.
- `uat_chapter4_summary.csv`: section-level rating totals for Chapter IV.

The requirement alignment uses the **current Capstone 2 Chapter III Requirements Traceability Matrix, Table 9**, in `MO-IT200D2 _ A4103 Group 4 Capstone 2 Paper (3).docx`. The older integrated stakeholder RTM CSV is superseded where definitions differ: current FR-05 includes company/sector browsing and sector-peer context; current FR-10 concerns comparative model-performance evidence. The `pooled_item_response_favorable_pct` field counts repeated item responses and is not a participant-level acceptance rate. UAT classifications describe perception or an applicable rating component only; functional correctness, nonfunctional technical criteria, and forecast accuracy require their separate evidence.

The available pre-response research methodology documents an 80% stakeholder acceptance criterion, corresponding to at least seven favorable responses among eight participants. The final UAT ratings satisfy the numerical favorable-response component where applicable. However, formal overall UAT acceptance remains pending verification of the approved criterion's scope, unaided core-task completion, and unresolved Critical/High-severity defect status. Adviser approval timing and prespecified mapping of the revised questionnaire to the designated acceptance items were not independently established. The repository's October 1 notebook supplied only the visual presentation reference; no previous statistics were reused.

The response workbook includes submissions dated October 13–16, while the final questionnaire PDF was exported October 16. Matching headers, matrix items, and rating options support compatibility, but the workbook has no per-response form-version field and cannot prove which live version each participant saw. The eight-person, mostly beginner sample supports descriptive stakeholder findings only; observed unaided task success, defect closure, forecasting accuracy, and population-wide acceptance require separate evidence.
