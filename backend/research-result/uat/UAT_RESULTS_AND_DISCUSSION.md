# Chapter IV — Final UAT results and discussion evidence

## Method and source

Eight submitted Google Forms records were analyzed against the final 36-question questionnaire. All eight contained the required consent and educational-purpose acknowledgment; no duplicate email keys or duplicate full records were found. The same response sheet covers 21 navigation/usability items, nine feature-helpfulness items, eight desktop/laptop statements, and nine tablet/mobile statements. The analysis uses score 1–5 in the exact order of each questionnaire scale. The top two categories define a favorable response. Frequencies and percentages are primary; means and medians summarize ordinal responses. No inferential test or overall composite score is applied. The source workbook is private and the SHA-256 is in `UAT_DATA_VALIDATION.md`.

## Respondent profile

Seven of eight respondents (87.5%) selected Beginner and one (12.5%) selected Intermediate. Seven used Google Chrome on desktop/laptop and one used Mozilla Firefox. Seven used a mobile phone for the second part and one used a tablet; seven used Google Chrome on that device and one used Safari. All eight preferred dark mode on both device categories. The questionnaire does not distinguish desktop from laptop usage. These frequencies describe the eight respondents only.

## Navigation and usability, Q7–Q27

| Website area | Items | Favorable item responses | Item mean range (1–5) |
| --- | ---: | ---: | ---: |
| Home | 3 | 24/24 | 4.750–5.000 |
| Companies and Company Details | 4 | 32/32 | 4.625–5.000 |
| My Watchlist | 3 | 24/24 | 4.625–4.875 |
| Learn Stocks | 3 | 24/24 | 4.750–5.000 |
| About PSE Pulse | 4 | 32/32 | 4.750–4.875 |
| Ask AI | 4 | 32/32 | 4.750–5.000 |

Every one of the 168 navigation item responses was favorable. Q8 (Home freshness display), Q12 (actual versus predicted chart distinction), Q18 (learning-content clarity), and Q26 (Ask AI relevance) each received eight top-category ratings. Q13 (Beginner/Advanced toggle) and Q14 (adding to watchlist) were the lowest within this section: each had three score-4 and five score-5 responses (mean 4.625/5). These are positive ratings with less top-category agreement; they suggest opportunities to simplify the interactions. They do not establish chart data accuracy or complete functional correctness.

## Feature helpfulness, Q28

| Item | Feature | Very Helpful | Extremely Helpful | Mean (1–5) |
| --- | --- | ---: | ---: | ---: |
| Q28_01 | Historical Data Overview | 2 | 6 | 4.750 |
| Q28_02 | Next-Day Price Forecasts | 3 | 5 | 4.625 |
| Q28_03 | Forecast Charts | 2 | 6 | 4.750 |
| Q28_04 | Model Ranking Summaries | 3 | 5 | 4.625 |
| Q28_05 | My Watchlist | 2 | 6 | 4.750 |
| Q28_06 | Learn Stocks | 2 | 6 | 4.750 |
| Q28_07 | About PSE Pulse | 3 | 5 | 4.625 |
| Q28_08 | Ask AI Assistant | 2 | 6 | 4.750 |
| Q28_09 | Light and Dark Modes | 1 | 7 | 4.875 |

All 72 feature ratings were Very Helpful or Extremely Helpful. Light and Dark Modes had the highest mean (4.875/5, seven Extremely Helpful). Next-Day Price Forecasts, Model Ranking Summaries, and About PSE Pulse were tied at 4.625/5, each with five Extremely Helpful and three Very Helpful. Those relative differences are small and descriptive. Helpfulness does not establish learning gains or model accuracy.

## Desktop/laptop experience, Q29

| Item | Desktop/laptop statement | Agree | Strongly Agree | Mean (1–5) |
| --- | --- | ---: | ---: | ---: |
| Q29_01 | Clean organization | 1 | 7 | 4.875 |
| Q29_02 | Perceived page speed | 2 | 6 | 4.750 |
| Q29_03 | Learning use intent | 3 | 5 | 4.625 |
| Q29_04 | Recommendation intent | 1 | 7 | 4.875 |
| Q29_05 | Source and freshness visibility | 3 | 5 | 4.625 |
| Q29_06 | Stock/sector/date controls | 1 | 7 | 4.875 |
| Q29_07 | Desktop readability | 3 | 5 | 4.625 |
| Q29_08 | Visual comfort | 3 | 5 | 4.625 |

All 64 desktop/laptop item responses were favorable. Clean organization, recommendation intent, and stock/sector/date controls each received seven Strongly Agree responses. Learning-use intent, source/freshness visibility, readability, and visual comfort each received five Strongly Agree and three Agree responses (mean 4.625/5). The 8/8 favorable learning-use and recommendation responses are intention ratings, not observed future use or population-level acceptance. Perceived speed (six Strongly Agree, two Agree) is distinct from timed performance testing.

## Tablet/mobile experience, Q30–Q33

| Item | Tablet/mobile statement | Agree | Strongly Agree | Mean (1–5) |
| --- | --- | ---: | ---: | ---: |
| Q33_01 | Mobile navigation | 1 | 7 | 4.875 |
| Q33_02 | Touch controls | 1 | 7 | 4.875 |
| Q33_03 | Text readability | 3 | 5 | 4.625 |
| Q33_04 | Chart readability | 3 | 5 | 4.625 |
| Q33_05 | Content access | 2 | 6 | 4.750 |
| Q33_06 | Horizontal scrolling | 5 | 3 | 4.375 |
| Q33_07 | Company/sector/date controls | 1 | 7 | 4.875 |
| Q33_08 | Perceived page speed | 1 | 7 | 4.875 |
| Q33_09 | Main task completion | 2 | 6 | 4.750 |

All 72 tablet/mobile agreement responses were favorable. Horizontal scrolling was the lowest item across the 47 ratings: five Agree, three Strongly Agree, mean 4.375/5. Text and chart readability each had three Agree and five Strongly Agree responses (mean 4.625/5). Seven of eight device tests were on mobile phones, so tablet-specific inference is limited to one report. The form did not record viewport dimensions or objective scrolling measurements.

## Related desktop and mobile perceptions

The same eight people rated both contexts, preserving the respondent pairing in the source workbook. The questions are related but not identical. Perceived loading mean was 4.750/5 for desktop/laptop and 4.875/5 for mobile. Controls mean was 4.875/5 in both. Desktop general readability and mobile text readability were each 4.625/5; desktop visual comfort and mobile chart readability were each 4.625/5. These differences are descriptive and cannot be interpreted as a controlled device effect.

## Qualitative feedback, Q34–Q36

The coding counts distinct respondents per theme and allows a response to have multiple themes. In Q34, four responses mentioned forecast information, four historical data or charts, three Ask AI, and one the Beginner/Advanced view. In Q36, three mentioned tooltips or terminology, two first-time guidance, and two visual design or a chart legend; three did not suggest an additional change. All eight left optional Q35 blank. A blank answer does not establish that no confusing labels, broken charts, or navigation issues existed. To protect the small sample, no raw excerpts or row-level IDs are published. Coding rules and aggregate counts are in `uat_qualitative_themes.csv`.

## Requirement alignment and consolidated finding

The requirement map uses the current Capstone 2 Chapter III Requirements Traceability Matrix (Table 9). FR-05 covers company and sector browsing plus sector-peer context; Q9 and Q10 support perceived browsing ease, while the approved three-peer behavior needs functional verification. FR-10 is comparative model-performance evidence; Q21 and Q28_04 support perceived explanation clarity and ranking helpfulness, while displayed metrics and rankings need output verification. The CSV defines all 16 current FR/NFR identifiers and distinguishes UAT perception, an applicable UAT rating component, functional verification, nonfunctional technical verification, and separate forecasting evidence. No UAT-only label certifies a complete requirement. The pooled percentage counts repeated item responses, not independent participants or formal acceptance. Forecast accuracy remains supported only by frozen formal evaluation evidence.

Across 47 items there were 376 favorable item responses from eight people: 168/168 navigation, 72/72 feature, 64/64 desktop, and 72/72 mobile. These repeated responses are not 376 independent participants. This evidence supports favorable perceived experience in this sample, with relative improvement opportunities in small-screen scrolling, terminology, and first-time guidance.

## Limitations and manuscript integration

The respondent group is small, largely beginner, self-reported, and researcher-supplied. Their profile fits the planned budding-trader eligibility, but the workbook cannot verify that these are the same eight people from requirements gathering. Recruitment, live questionnaire exposure, observed unaided task completion, defect closure, and generalizability cannot be independently verified from this sheet. The PDF was exported on October 16 while submissions began October 13; matching field structure supports compatibility but does not prove per-response form version.

The available pre-response research methodology documents an 80% stakeholder acceptance criterion, corresponding to at least seven favorable responses among eight participants. The final UAT ratings satisfy the numerical favorable-response component where applicable. However, formal overall UAT acceptance remains pending verification of the approved criterion's scope, unaided core-task completion, and unresolved Critical/High-severity defect status. Adviser approval timing and prespecified mapping of the revised questionnaire to the designated acceptance items were not independently established. The local manuscript draft contains October 1 UAT statistics and an obsolete principal-model-versus-Naive question; Tables 72–77 and related prose require replacement using `UAT_MANUSCRIPT_REPLACEMENT_GUIDE.md`. The manuscript itself was not edited.
