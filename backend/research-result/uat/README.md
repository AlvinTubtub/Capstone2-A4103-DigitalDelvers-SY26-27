# PSE Pulse — User Acceptance Testing (UAT) Evidence

## Purpose and scope

This directory contains the finalized PSE Pulse UAT analysis. UAT describes participants' reported experience with the website: usability, perceived feature helpfulness, and desktop/laptop and tablet/mobile use. It does not independently establish forecasting accuracy, browser-level technical compatibility, automated functional correctness, measured loading performance, or accessibility compliance. Those questions require separate evidence.

## Participants and questionnaire

The response workbook supplied by the researchers contains eight consenting, unique respondents. The final questionnaire has 47 five-point rating items in four categories: 21 navigation/usability, nine feature helpfulness, eight desktop/laptop experience, and nine tablet/mobile experience. It also asks about investing experience, browsers, devices, theme preference, and open-ended feedback. The aggregate [participant profile](uat_participant_profile.csv) reports seven Beginners and one Intermediate; seven used a mobile phone and one a tablet for the second-device evaluation. All eight reported Dark Mode in both device contexts.

## Likert scoring and descriptive statistics

Each item uses the five ordered labels specified in the [question mapping](uat_question_mapping.json) and [analysis script](uat_analysis.py). The scales differ by item: ease, clarity, relevance, helpfulness, and agreement. A *favorable* rating is score 4 or 5 on its own scale: Somewhat/Very Easy, Somewhat/Very Clear, Somewhat/Very Relevant, Very/Extremely Helpful, or Agree/Strongly Agree. The remaining categories are retained in the item-level tables; “Moderately Helpful” is the middle helpfulness category, not an agreement response.

The analysis reports category frequencies and percentages, valid and missing counts, mean, median, and sample standard deviation. Frequencies and percentages are the primary descriptive evidence. Means summarize ordered Likert responses and do not turn them into measured performance or task success. No inferential claim or overall system correctness rate follows from these ratings.

## Final UAT summary

The figures below match [uat_chapter4_summary.csv](uat_chapter4_summary.csv).

| Category | Items | Valid ratings | Favorable ratings | Percentage |
| --- | ---: | ---: | ---: | ---: |
| Navigation/Usability | 21 | 168 | 168 | 100% |
| Feature Helpfulness | 9 | 72 | 72 | 100% |
| Desktop/Laptop | 8 | 64 | 64 | 100% |
| Tablet/Mobile | 9 | 72 | 72 | 100% |
| **Total** | **47** | **376** | **376** | **100%** |

These are 376 *item responses from eight people*, not 376 participants. Every rating was in a favorable category, but participants did not select the maximum score on every item. The percentage is not an overall system acceptance or technical correctness rate.

## UAT evidence files

| File | Evidence or role |
| --- | --- |
| [Executed Jupyter notebook](PSE_Pulse_UAT_Analysis_2026-10-16.ipynb) | Displays the full aggregate tables, 11 embedded graphs, interpretations, and research limits. |
| [Analysis script](uat_analysis.py) | Validates the private response sheet and generates the mapping and nine aggregate CSVs. |
| [UAT unit tests](test_uat_analysis.py) | Checks scoring, schema rejection, and thematic counts with synthetic data, plus current RTM definitions and committed aggregate totals. |
| [Question mapping](uat_question_mapping.json) | Records exact questionnaire headers, item identifiers, and ordered scale labels. |
| [Chapter IV summary](uat_chapter4_summary.csv) | Gives item and rating totals for the four UAT categories. |
| [Participant profile](uat_participant_profile.csv) | Gives aggregate investing-experience, browser, device, and theme counts. |
| [Navigation/usability ratings](uat_navigation_usability_summary.csv) | Summarizes the 21 navigation and usability items. |
| [Feature helpfulness ratings](uat_feature_helpfulness_summary.csv) | Summarizes the nine Q28 feature items. |
| [Desktop/laptop ratings](uat_desktop_experience_summary.csv) | Summarizes the eight Q29 experience statements. |
| [Tablet/mobile ratings](uat_mobile_experience_summary.csv) | Summarizes the nine Q33 experience statements. |
| [Device comparison](uat_device_comparison.csv) | Compares related, differently worded desktop and mobile items descriptively. |
| [Qualitative themes](uat_qualitative_themes.csv) | Gives aggregate Q34–Q36 feedback-theme counts and coding rules. |
| [Requirements alignment](uat_requirement_alignment.csv) | Relates UAT items to the current Chapter III functional and nonfunctional requirements, with evidence limits. |

## Qualitative feedback

The [analysis script](uat_analysis.py) groups Q34 and Q36 answers through documented case-insensitive keyword and regular-expression rules. A response may match more than one theme; the [theme CSV](uat_qualitative_themes.csv) reports distinct respondents per theme, so theme counts should not be summed as independent participants. This is a descriptive coding aid, not a fully validated qualitative thematic analysis. No participant quotations or raw answers are published here. All eight optional Q35 issue fields were blank; blanks do not prove that software defects were absent.

## Requirements alignment

The [alignment CSV](uat_requirement_alignment.csv) connects participant perceptions to the current Capstone 2 Chapter III Requirements Traceability Matrix. Its classifications include partial UAT support, a met UAT *rating component*, technical verification required, and requirements not directly evaluated by UAT. A favorable linked rating does not mark the complete requirement as passed. For example, perceived ease of browsing cannot verify all sector-peer behavior, and helpfulness of model rankings cannot verify comparative metric correctness.

Numerical forecast correctness, complete feature functionality, five-second loading performance, WCAG compliance, system security, and correctness of all operational data need their own technical or formal research evidence.

## Reproducibility and privacy

The original Google Forms XLSX workbook contains private participant information and is not committed to this public repository. The committed package contains analysis code, an executed notebook, the question mapping, aggregate CSVs, and synthetic-data-focused tests. Full source-data reproduction requires authorized access to the original workbook; it is not publicly available. The script checks consent, duplicate keys, questionnaire structure, and rating labels before producing aggregate outputs.

With Python 3 and `pandas`, `numpy`, `openpyxl`, `matplotlib`, `IPython`, `nbformat`, and `nbclient` installed, run the supported CLI from this directory. Use a separate output directory when independently checking the committed results:

```bash
python uat_analysis.py --workbook /path/to/private/responses.xlsx --output /tmp/pse-pulse-uat-check
```

The existing notebook can be read with its saved outputs. To execute it, set `PSE_PULSE_UAT_WORKBOOK` to the authorized private XLSX path and run its cells in Jupyter from this directory; execution regenerates aggregate files in the notebook's working directory. Do not publish the workbook, respondent identities, emails, or individual responses.

## Interpretation limitations

Eight mostly beginner respondents support descriptive findings for this intended stakeholder group, not population-level inference or universal satisfaction. Ratings describe self-reported experience, not observed unaided task success. Device findings reflect seven phone users and one tablet user; all eight reported Dark Mode, so this UAT does not independently establish Light Mode acceptance. UAT does not replace browser, functional, performance, accessibility, or forecast-accuracy testing.

The response workbook has no per-response form-version field. Its headings, matrix items, and rating options are compatible with the final questionnaire, but that compatibility cannot independently establish which live form version each participant saw. The results demonstrate favorable participant-reported ratings within the evaluated sample; they do not, by themselves, establish satisfaction of every system requirement or an independently verified overall UAT acceptance decision.

## Research evidence boundary

The formal forecasting [results manifest](../results_manifest.csv) does not include this UAT package. The notebook and CSVs here are separate participant-reported research evidence, not forecasting model outputs. They do not modify LIR, ARIMA, LSTM, the Naive benchmark, formal RMSE/MAE/MASE/R² results, principal model selection, frozen model evaluation, or current operational forecasts.
