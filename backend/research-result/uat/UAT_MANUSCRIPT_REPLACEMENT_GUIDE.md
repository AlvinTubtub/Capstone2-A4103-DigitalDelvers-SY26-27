# Final UAT manuscript replacement guide

**For researcher review before editing the DOCX.** The original `MO-IT200D2 _ A4103 Group 4 Capstone 2 Paper (3).docx` was not changed. Its six existing UAT table objects are numbered 72–77 in document order, although their visible draft captions use “Table XX.” Retain the manuscript's final numbering process; the headings below identify the existing objects rather than inventing new caption numbers.

## Authority and use

- Current requirement definitions: Capstone 2 Chapter III Requirements Traceability Matrix, manuscript Table 9. The older integrated stakeholder RTM CSV is superseded where it conflicts, especially FR-05 and FR-10.
- Final UAT instrument: 36 numbered questions; 21 Q7–Q27 ratings, nine Q28 feature ratings, eight Q29 desktop/laptop ratings, and nine Q33 tablet/mobile ratings.
- Final response evidence: eight consenting, unique submissions; no exclusions; 376/376 favorable rating responses. These are repeated item responses from eight people.
- A documented pre-response 80% criterion corresponds to at least 7/8 favorable participants for designated ratings. The final rating counts satisfy this numerical component where applicable. Do not assign overall formal PASS before confirming approved criterion scope, unaided core-task completion, and unresolved Critical/High-severity defect status.
- The final PDF was exported October 16; submissions span October 13–16. Matching headers and options do not prove each respondent's live form version. The workbook cannot independently prove the eight are the same people who joined requirements gathering.

## Existing manuscript content that must be replaced

| Existing object or section | Outdated content in the current manuscript | Correct final evidence and action |
| --- | --- | --- |
| Table 72, requirement-level UAT assessment | Uses October 1 ratings, including 7/8 historical understanding, 6/8 Historical Data Overview, and a principal-versus-Naive interpretation item. | Replace with current Table 9 requirement definitions and final Q7–Q33 item links below. Keep technical and forecasting verification separate. |
| Table 73, six core usability/interpretation measures | Says five of six meet 7/8; Best Principal Model versus Naive is 6/8. | Final form asks 21 navigation/usability ratings, all 8/8 favorable. It does not ask the obsolete principal-versus-Naive item. |
| Table 74, eight helpfulness features | Includes Responsible-Use Disclaimers and Beginner/Advanced Modes as matrix features; Next-Day Price Forecasts 7/8, mean 4.50; Ask AI 7/8, mean 4.125. | Final Q28 has nine different features. Next-Day Price Forecasts: 8/8, mean 4.625. Ask AI Assistant: 8/8, mean 4.750. Use the complete nine-row table below. |
| Table 75, desktop/overall experience | Reports learning-use and recommendation intent 7/8, speed and responsive readability 6/8. | Final Q29 has eight desktop/laptop statements, all 8/8 favorable. Learning-use mean 4.625; recommendation mean 4.875; perceived speed mean 4.750; desktop readability mean 4.625. Use the eight-row table below. |
| Table 76, most-useful themes | Old Ask AI count 4 and historical data/charts count 3. | Final Q34: Ask AI 3, historical data/charts 4, forecast information 4, Beginner/Advanced view 1. Repurpose Table 76 for the final nine mobile statements and place qualitative themes in Table 77. |
| Table 77, improvement themes | Combines onboarding/tooltips/terminology into four mentions and omits final optional-issue status. | Final Q36: terminology/tooltips 3; first-time guidance 2; visual design/chart legend 2; no additional change 3. Q35 is blank for 8/8 and does not prove no defects. Use final thematic table below. |
| Chapter IV UAT prose and literature synthesis | States 5/6 core threshold, 7/8 use/recommend, 6/8 speed/readability, old mean 4.625 for historical/chart clarity, old principal-versus-Naive shortfall, and “all eight demonstrated understanding” of non-advisory use. | Replace with final Q11 mean 4.875, Q12 mean 5.000, all 8/8 favorable Q29 intentions/speed/readability, and the limited Q3 acknowledgment/Q27 clarity interpretation. Do not assert demonstrated comprehension. |
| Chapter V summary, conclusions, and recommendations | Repeats 7/8 use/recommend, 5/6 measures, 6/8 principal-versus-Naive understanding, 6/8 speed/readability, and overall acceptance achieved. | Replace with final descriptive ratings and pending formal-acceptance qualification. Remove the obsolete question and its recommendation linkage. |

## Proposed replacement for existing Table 72 — requirement assessment

Use the current Chapter III RTM labels. The classification refers only to UAT perception or a rating component. The complete alignment CSV provides the detailed verification limit for each row.

| ID | Current requirement | Final UAT items | UAT classification |
| --- | --- | --- | --- |
| FR-01 | Display ticker, complete company name, and official PSE sector. | Q9,Q10 | Partially supported by UAT |
| FR-02 | Display historical OHLCV and volume through readable interactive views. | Q11,Q28_01 | Partially supported by UAT |
| FR-03 | Display next-trading-session forecast and forecast metadata. | Q28_02 | Partially supported by UAT |
| FR-04 | Compare forecasts with corresponding actual closing prices. | Q12,Q28_03 | Partially supported by UAT |
| FR-05 | Support company and sector browsing and sector-peer context. | Q9,Q10 | Partially supported by UAT |
| FR-06 | Provide plain-language educational explanations and definitions. | Q18,Q25,Q28_06,Q28_08,Q36 | Partially supported by UAT |
| FR-07 | Display source, freshness, dates, and relevant model/artifact information. | Q8,Q23,Q29_05 | Partially supported by UAT |
| FR-08 | Display uncertainty, limitations, and responsible-use notices. | Q22,Q27 | Partially supported by UAT |
| FR-09 | Support appropriate searching, filtering, navigation, and historical-range controls. | Q9,Q10,Q29_06,Q33_07 | Partially supported by UAT |
| FR-10 | Present comparative model-performance evidence. | Q21,Q28_04 | Partially supported by UAT |
| NFR-01 | Provide clear, consistent, summary-first navigation. | Q7,Q9,Q10,Q17,Q19,Q20,Q24,Q29_01,Q33_01 | Partially supported by UAT |
| NFR-02 | Maintain readable charts, labels, spacing, contrast, and beginner-friendly language. | Q12,Q18,Q29_07,Q29_08,Q33_03,Q33_04 | UAT rating component met |
| NFR-03 | Load common pages and published outputs efficiently. | Q29_02,Q33_08 | Requires technical verification |
| NFR-04 | Support desktop, laptop, tablet, and mobile viewing. | Q33_01,Q33_02,Q33_03,Q33_04,Q33_05,Q33_06,Q33_07,Q33_09 | Partially supported by UAT |
| NFR-05 | Avoid unnecessary registration and personal-data collection. | — | Not directly evaluated by UAT |
| NFR-06 | Provide readable Dark Mode and Light Mode presentation. | Q6,Q32,Q29_08,Q28_09 | UAT rating component met |

**Suggested discussion.** The final UAT supplies favorable perceived-use evidence across the covered interface areas. FR-05 has direct browsing-ease evidence in Q9–Q10 but no isolated test of the approved three-company sector-peer behavior. FR-10 has Q21 explanation clarity and Q28_04 model-ranking helpfulness; correctness of comparative metrics and rankings requires approved backend-output checks. NFR-02 and NFR-06 have favorable rating components but still require their separate visual and technical checks. UAT ratings cannot prove forecast accuracy, data integrity, privacy behavior, timed loading, or complete functional correctness. Source: `uat_requirement_alignment.csv`, `uat_question_mapping.json`, and the current Chapter III RTM.

## Proposed replacement for existing Table 73 — navigation and usability

All 21 Q7–Q27 questions remain in questionnaire order. “Score 4” means Somewhat Easy/Clear/Relevant, according to the item's scale; “Score 5” means Very Easy/Clear/Relevant. Full wording and scale are in the mapping JSON.

| Item | Short description | Score 4 | Score 5 | Favorable | Mean | Median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q7 | Find Home information | 2 | 6 | 8/8 | 4.750 | 5 |
| Q8 | Home date and refresh clarity | 0 | 8 | 8/8 | 5.000 | 5 |
| Q9 | Find company or sector from Home | 2 | 6 | 8/8 | 4.750 | 5 |
| Q10 | Select company/open details | 2 | 6 | 8/8 | 4.750 | 5 |
| Q11 | Understand historical price and volume | 1 | 7 | 8/8 | 4.875 | 5 |
| Q12 | Distinguish actual and predicted chart values | 0 | 8 | 8/8 | 5.000 | 5 |
| Q13 | Switch Beginner/Advanced view | 3 | 5 | 8/8 | 4.625 | 5 |
| Q14 | Add company to Watchlist | 3 | 5 | 8/8 | 4.625 | 5 |
| Q15 | Find saved companies | 1 | 7 | 8/8 | 4.875 | 5 |
| Q16 | Understand Watchlist limit | 1 | 7 | 8/8 | 4.875 | 5 |
| Q17 | Find learning topic | 1 | 7 | 8/8 | 4.875 | 5 |
| Q18 | Understand learning content | 0 | 8 | 8/8 | 5.000 | 5 |
| Q19 | Follow learning path | 2 | 6 | 8/8 | 4.750 | 5 |
| Q20 | Find project purpose | 1 | 7 | 8/8 | 4.875 | 5 |
| Q21 | Understand methods/evaluation | 1 | 7 | 8/8 | 4.875 | 5 |
| Q22 | Understand forecast scope/limits | 2 | 6 | 8/8 | 4.750 | 5 |
| Q23 | Find source/update process | 2 | 6 | 8/8 | 4.750 | 5 |
| Q24 | Open Ask AI/start question | 1 | 7 | 8/8 | 4.875 | 5 |
| Q25 | Understand Ask AI answer | 1 | 7 | 8/8 | 4.875 | 5 |
| Q26 | Ask AI answer relevance | 0 | 8 | 8/8 | 5.000 | 5 |
| Q27 | Understand Ask AI educational limits | 2 | 6 | 8/8 | 4.750 | 5 |

**Suggested discussion.** All 168 navigation/usability item responses were favorable. Q8, Q12, Q18, and Q26 received eight top-category ratings each. Q13 and Q14 had the lowest means in this section, 4.625/5 each, with three score-4 and five score-5 ratings. These are opportunities for refinement within otherwise positive responses. Perceived chart clarity does not establish forecasting accuracy. Source: `uat_navigation_usability_summary.csv` and notebook Graph 4.

## Proposed replacement for existing Table 74 — feature helpfulness

The final Q28 matrix has **nine** features. Score 4 is Very Helpful; score 5 is Extremely Helpful.

| Item | Feature | Very Helpful | Extremely Helpful | Favorable | Mean | Median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q28_01 | Historical Data Overview | 2 | 6 | 8/8 | 4.750 | 5 |
| Q28_02 | Next-Day Price Forecasts | 3 | 5 | 8/8 | 4.625 | 5 |
| Q28_03 | Forecast Charts | 2 | 6 | 8/8 | 4.750 | 5 |
| Q28_04 | Model Ranking Summaries | 3 | 5 | 8/8 | 4.625 | 5 |
| Q28_05 | My Watchlist | 2 | 6 | 8/8 | 4.750 | 5 |
| Q28_06 | Learn Stocks | 2 | 6 | 8/8 | 4.750 | 5 |
| Q28_07 | About PSE Pulse | 3 | 5 | 8/8 | 4.625 | 5 |
| Q28_08 | Ask AI Assistant | 2 | 6 | 8/8 | 4.750 | 5 |
| Q28_09 | Light and Dark Modes | 1 | 7 | 8/8 | 4.875 | 5 |

**Suggested discussion.** All 72 Q28 responses were Very or Extremely Helpful. Light and Dark Modes had the highest mean (4.875/5; seven Extremely Helpful). Next-Day Price Forecasts, Model Ranking Summaries, and About PSE Pulse each had mean 4.625/5 and five Extremely Helpful responses. Ask AI Assistant had mean 4.750/5, with six Extremely Helpful and two Very Helpful. These descriptive ratings do not measure learning gains. Source: `uat_feature_helpfulness_summary.csv` and notebook Graphs 5–6.

## Proposed replacement for existing Table 75 — desktop/laptop experience

The final Q29 matrix has eight agreement statements. Score 4 is Agree; score 5 is Strongly Agree.

| Item | Statement summary | Agree | Strongly Agree | Favorable | Mean | Median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q29_01 | Clean organization | 1 | 7 | 8/8 | 4.875 | 5 |
| Q29_02 | Perceived page speed | 2 | 6 | 8/8 | 4.750 | 5 |
| Q29_03 | Learning use intent | 3 | 5 | 8/8 | 4.625 | 5 |
| Q29_04 | Recommendation intent | 1 | 7 | 8/8 | 4.875 | 5 |
| Q29_05 | Source and freshness visibility | 3 | 5 | 8/8 | 4.625 | 5 |
| Q29_06 | Stock/sector/date controls | 1 | 7 | 8/8 | 4.875 | 5 |
| Q29_07 | Desktop readability | 3 | 5 | 8/8 | 4.625 | 5 |
| Q29_08 | Visual comfort | 3 | 5 | 8/8 | 4.625 | 5 |

**Suggested discussion.** All 64 desktop/laptop item responses were favorable. Learning-use intent was 8/8 favorable with mean 4.625/5; recommendation intent was 8/8 with mean 4.875/5. Perceived page speed was 8/8 favorable with mean 4.750/5; desktop readability was 8/8 with mean 4.625/5. These are perceptions and intentions, not observed use or timed performance. The form does not distinguish desktop from laptop users. Source: `uat_desktop_experience_summary.csv` and notebook Graph 7.

## Proposed replacement for existing Table 76 — tablet/mobile experience

Seven respondents used a Mobile Phone and one used a Tablet; seven used Google Chrome and one used Safari on the second device. All preferred Dark mode. Score 4 is Agree; score 5 is Strongly Agree.

| Item | Statement summary | Agree | Strongly Agree | Favorable | Mean | Median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q33_01 | Mobile navigation | 1 | 7 | 8/8 | 4.875 | 5 |
| Q33_02 | Touch controls | 1 | 7 | 8/8 | 4.875 | 5 |
| Q33_03 | Text readability | 3 | 5 | 8/8 | 4.625 | 5 |
| Q33_04 | Chart readability | 3 | 5 | 8/8 | 4.625 | 5 |
| Q33_05 | Content access | 2 | 6 | 8/8 | 4.750 | 5 |
| Q33_06 | Horizontal scrolling | 5 | 3 | 8/8 | 4.375 | 4 |
| Q33_07 | Company/sector/date controls | 1 | 7 | 8/8 | 4.875 | 5 |
| Q33_08 | Perceived page speed | 1 | 7 | 8/8 | 4.875 | 5 |
| Q33_09 | Main task completion | 2 | 6 | 8/8 | 4.750 | 5 |

**Suggested discussion.** All 72 Q33 item responses were favorable. Horizontal scrolling had the lowest mean of any rating item (4.375/5; five Agree and three Strongly Agree). Text and chart readability were each 4.625/5. Tablet-specific inference is limited to one respondent. Perceived mobile task completion is not an observed unaided task-completion record. Source: `uat_participant_profile.csv`, `uat_mobile_experience_summary.csv`, and notebook Graphs 3 and 8–9.

## Proposed replacement for existing Table 77 — qualitative themes

Counts are distinct respondents per theme; responses can have multiple themes. No raw excerpts are published because of the small sample.

| Question | Coded theme | Respondents |
| --- | --- | ---: |
| Q34 | Ask AI learning support | 3/8 |
| Q34 | Forecast information | 4/8 |
| Q34 | Historical data or charts | 4/8 |
| Q34 | Beginner/Advanced view | 1/8 |
| Q35 | Optional issue item left blank | 8/8 |
| Q36 | Tooltips and terminology | 3/8 |
| Q36 | First-time guidance | 2/8 |
| Q36 | Visual design and chart legend | 2/8 |
| Q36 | No additional change suggested | 3/8 |

**Suggested discussion.** Q34 most-useful responses mentioned forecast information and historical data/charts four times each, Ask AI three times, and the Beginner/Advanced view once. Q36 suggestions included tooltips/terminology (3), first-time guidance (2), and visual design/chart legend (2); three responses suggested no further change. Q35 was optional and blank in all eight submissions; this cannot establish defect absence. Themes overlap and should not be summed into a respondent total. Source: `uat_qualitative_themes.csv` and notebook Graphs 10–11.

## Chapter IV prose replacement and methodological boundary

Suggested insertion after the tables: “The final questionnaire produced 376 favorable item ratings out of 376 valid ratings across 47 items, from eight consenting respondents. This reflects repeated ratings by a small purposively selected stakeholder sample. The available pre-response methodology documented an 80% criterion, equivalent to at least seven of eight favorable participants for designated items. The observed final ratings meet that numerical rating component where applicable. Overall formal UAT acceptance is not assigned until the approved criterion's scope, unaided task completion, and unresolved Critical/High-severity defect status are verified. The workbook has no per-response questionnaire-version field; its final-questionnaire-compatible headers and options do not independently prove each participant's live form version.”

Do not call acknowledgment of educational/non-advisory purpose a demonstrated comprehension test. Do not revive the removed Best Principal Model versus Naive item. Do not equate perceived loading speed with timed performance or UAT chart clarity with forecast accuracy.

## Chapter V statements requiring revision

- **Summary of findings:** Replace the manuscript's 7/8 use/recommend and 5/6 core-measure statements with final Q29_03 and Q29_04 (8/8 favorable each), the 47-item / 376-response description, and the explicit repeated-response denominator.
- **Conclusions:** Replace “overall stakeholder-acceptance threshold was achieved,” “generally accepted educational platform,” or equivalent formal PASS language with favorable perceived usability and helpfulness within eight intended stakeholders, pending the other formal acceptance evidence.
- **Recommendations:** Remove the claimed 6/8 Best Principal Model versus Naive shortfall and its causal link to tooltips. Recommend tooltips, terminology support, first-time guidance, and mobile scrolling improvements from actual Q36/Q33 results. Comparative model-performance correctness remains a separate output-verification obligation under current FR-10.
- **Limitations:** Add the unverified same-participant linkage, self-report scope, one-tablet observation, unavailable unaided task records, unavailable Critical/High defect-closure status, revised-item-to-threshold mapping, and questionnaire-version provenance. Do not claim independent external validation or forecasting accuracy from UAT.

## Review checklist before DOCX integration

1. Confirm the visible caption numbering the researcher wants for the six existing tables. This guide identifies objects 72–77 by document order only.
2. Verify whether task-completion and defect-closure evidence exists outside the response workbook before making any formal PASS claim.
3. Replace all October 1 UAT prose in Chapter IV, literature integration, Chapter V summary/conclusions/recommendations, and RTM discussion. Search for “five of six,” “7 of 8,” “6 of 8,” “Best Principal Model versus Naive,” “eight features,” “disclaimer feature,” and obsolete helpfulness means; preserve legitimate non-UAT uses of those strings.
4. Reconcile the current Chapter III Table 9 requirement definitions throughout the manuscript. FR-10 means comparative model-performance evidence in this baseline, not upload.
5. Keep the private response workbook and identifiers outside any published manuscript appendix.
