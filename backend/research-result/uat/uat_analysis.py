"""Reproduce aggregate PSE Pulse UAT evidence from the private final response sheet.

Run: python uat_analysis.py --workbook /path/to/private/responses.xlsx
The source workbook must stay outside the repository. No row-level data are exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
LOG = logging.getLogger("uat")
SCALES = {
    "ease": ["Very Difficult", "Somewhat Difficult", "Neither Easy nor Difficult", "Somewhat Easy", "Very Easy"],
    "clarity": ["Very Unclear", "Somewhat Unclear", "Neither Clear nor Unclear", "Somewhat Clear", "Very Clear"],
    "relevance": ["Very Irrelevant", "Somewhat Irrelevant", "Neither Relevant nor Irrelevant", "Somewhat Relevant", "Very Relevant"],
    "helpfulness": ["Not Helpful", "Slightly Helpful", "Moderately Helpful", "Very Helpful", "Extremely Helpful"],
    "agreement": ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"],
}
AREAS = (["Home"] * 3 + ["Companies and Company Details"] * 4 +
         ["My Watchlist"] * 3 + ["Learn Stocks"] * 3 +
         ["About PSE Pulse"] * 4 + ["Ask AI"] * 4)
FEATURES = ["Historical Data Overview", "Next-Day Price Forecasts", "Forecast Charts",
            "Model Ranking Summaries", "My Watchlist", "Learn Stocks", "About PSE Pulse",
            "Ask AI Assistant", "Light and Dark Modes"]
DESKTOP = ["Clean organization", "Perceived page speed", "Learning use intent",
           "Recommendation intent", "Source and freshness visibility", "Stock/sector/date controls",
           "Desktop readability", "Visual comfort"]
MOBILE = ["Mobile navigation", "Touch controls", "Text readability", "Chart readability",
          "Content access", "Horizontal scrolling", "Company/sector/date controls",
          "Perceived page speed", "Main task completion"]
NAV_HEADER_PHRASES = [
    "main information on the Home page", "latest forecast date and data refresh",
    "company or sector to explore", "Companies page or search controls",
    "historical price and trading-volume", "difference between actual historical prices and predicted values",
    "Beginner and Advanced views", "add a company to My Watchlist",
    "companies saved in My Watchlist", "how many companies could be saved",
    "learning topic on the Learn Stocks", "learning content explain stock-market",
    "follow the learning path", "purpose of PSE Pulse", "forecasting methods and how they are evaluated",
    "scope and limitations of the forecasts", "data source and update process",
    "open Ask AI and start a question", "answer provided by Ask AI",
    "answer to the question you asked", "educational purpose and limits",
]
DESKTOP_HEADER_PHRASES = ["avoids information overload", "loads quickly and transitions smoothly",
    "starting point to learn", "recommend this educational dashboard", "source of the stock data",
    "stock, sector, and date controls", "without cut-off content", "colors/theme, text, labels, and charts"]
MOBILE_HEADER_PHRASES = ["navigation menu was easy", "easy to tap accurately", "readable without zooming",
    "Chart details were readable", "without content being cut off", "horizontal scrolling needed was manageable",
    "controls were easy to use on this device", "Pages loaded at an acceptable speed", "same main tasks on this device"]
PROFILE = {"Q4": "Investing experience", "Q5": "Desktop/laptop browser",
           "Q6": "Desktop/laptop theme", "Q30": "Tablet/mobile device",
           "Q31": "Tablet/mobile browser", "Q32": "Tablet/mobile theme"}
QUAL = {"Q34": "Most useful feature", "Q35": "Reported issues", "Q36": "Improvement suggestions"}
CONSENT = "I voluntarily agree to participate in this evaluation and understand my identity will remain confidential."


def make_mapping(columns: list[str]) -> dict:
    """Bind questionnaire IDs to exact Forms headers and reject schema drift."""
    if len(columns) != 60 or len(set(columns)) != 60:
        raise ValueError(f"Expected 60 distinct columns; found {len(columns)}")
    expected = ["Timestamp", "Email Address", "Consent to participate"]
    if columns[:3] != expected:
        raise ValueError("Source identification/consent headers changed")
    if "principal" in " ".join(columns).lower() and "naive" in " ".join(columns).lower():
        raise ValueError("Obsolete principal-versus-Naive item found")
    entries = []
    for q, idx in [("Q4", 4), ("Q5", 5), ("Q6", 6),
                   ("Q30", 45), ("Q31", 46), ("Q32", 47),
                   ("Q34", 57), ("Q35", 58), ("Q36", 59)]:
        entries.append(dict(id=q, section="profile" if q in PROFILE else "qualitative",
                            label=(PROFILE | QUAL)[q], source_column=columns[idx], scale=None))
    for offset, q in enumerate(range(7, 28)):
        header = columns[7 + offset]
        if NAV_HEADER_PHRASES[offset].casefold() not in header.casefold():
            raise ValueError(f"Final questionnaire wording mismatch at Q{q}")
        scale = ("relevance" if q == 26 else "clarity" if q in {8, 12, 16, 18, 21, 22, 25, 27} else "ease")
        entries.append(dict(id=f"Q{q}", section="navigation", area=AREAS[offset],
                            label=header, source_column=header, scale=scale))
    for j, label in enumerate(FEATURES):
        header = columns[28 + j]
        if not header.startswith("Based on your needs as a stock market learner, how helpful was each feature? [") or label not in header:
            raise ValueError(f"Q28 matrix mismatch: {label}")
        entries.append(dict(id=f"Q28_{j+1:02d}", section="feature", label=label,
                            source_column=header, scale="helpfulness"))
    for base, section, labels, phrases in [(37, "desktop", DESKTOP, DESKTOP_HEADER_PHRASES),
                                          (48, "mobile", MOBILE, MOBILE_HEADER_PHRASES)]:
        for j, label in enumerate(labels):
            header = columns[base + j]
            if not header.startswith("Please indicate your level of agreement on a scale of 1"):
                raise ValueError(f"Agreement matrix mismatch: {section} {j+1}")
            if phrases[j].casefold() not in header.casefold():
                raise ValueError(f"Final questionnaire wording mismatch at {section} item {j+1}")
            entries.append(dict(id=f"{'Q29' if section == 'desktop' else 'Q33'}_{j+1:02d}",
                                section=section, label=label, question_text=header.split(" [", 1)[-1].rstrip("]"),
                                source_column=header, scale="agreement"))
    for entry in entries:
        if entry["source_column"] not in columns:
            raise ValueError(f"Unmapped item: {entry['id']}")
    mapped = {e["source_column"] for e in entries}
    expected_other = {columns[i] for i in (0, 1, 2, 3)}
    if set(columns) != mapped | expected_other:
        raise ValueError("Unexpected or unmapped workbook fields")
    return {"questionnaire": "Final PDF, exported 2026-10-16", "source_sheet": "Form Responses 1",
            "rating_count": 47, "scales_low_to_high": SCALES, "fields": entries,
            "administrative_fields": [c for c in columns if c in expected_other]}


def load_validate(workbook: Path, mapping: dict | None = None):
    LOG.info("Loading private response workbook")
    book = pd.ExcelFile(workbook)
    if book.sheet_names != ["Form Responses 1"]:
        raise ValueError(f"Unexpected sheets: {book.sheet_names}")
    frame = pd.read_excel(workbook, sheet_name="Form Responses 1", dtype=object)
    frame.columns = [str(c) for c in frame.columns]
    actual = make_mapping(list(frame.columns))
    if mapping is not None and mapping != actual:
        raise ValueError("Saved mapping differs from workbook schema")
    fields = actual["fields"]
    invalid = {}
    for field in fields:
        if field["scale"]:
            observed = set(frame[field["source_column"]].dropna().astype(str))
            extra = observed - set(SCALES[field["scale"]])
            if extra:
                invalid[field["id"]] = sorted(extra)
    if invalid:
        raise ValueError(f"Invalid rating labels: {invalid}")
    if frame.iloc[:, 2].isna().any() or not frame.iloc[:, 2].eq(CONSENT).all():
        raise ValueError("One or more submissions lack the stated consent")
    if not frame.iloc[:, 3].eq("Yes").all():
        raise ValueError("One or more submissions lack educational-purpose acknowledgment")
    email = frame.iloc[:, 1].astype(str).str.strip().str.lower()
    duplicate_email = int(email.duplicated().sum())
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_email or duplicate_rows:
        raise ValueError(f"Potential duplicates require manual review: email={duplicate_email}, rows={duplicate_rows}")
    timestamps = pd.to_datetime(frame.iloc[:, 0], errors="raise")
    if timestamps.isna().any():
        raise ValueError("Missing timestamps")
    sha = hashlib.sha256(workbook.read_bytes()).hexdigest()
    missing = {f["id"]: int(frame[f["source_column"]].isna().sum()) for f in fields}
    LOG.info("Validated %d consenting, unique submissions and 47 rating items", len(frame))
    meta = dict(source_sha256=sha, submissions=len(frame), valid=len(frame), exclusions=0,
                unique_respondents=email.nunique(), duplicate_email=duplicate_email,
                duplicate_rows=duplicate_rows, first_timestamp=str(timestamps.min()),
                last_timestamp=str(timestamps.max()), missing=missing)
    return frame, actual, meta


def rating_table(frame: pd.DataFrame, fields: list[dict], section: str) -> pd.DataFrame:
    rows = []
    for field in (f for f in fields if f["section"] == section):
        order = SCALES[field["scale"]]
        counts = frame[field["source_column"]].value_counts(dropna=True)
        n = int(counts.sum())
        scores = frame[field["source_column"]].dropna().map({v: i+1 for i, v in enumerate(order)}).astype(float)
        row = dict(item_id=field["id"], area=field.get("area", section), item=field["label"],
                   scale=field["scale"], valid_n=n, missing_n=len(frame)-n,
                   mean=round(float(scores.mean()), 3) if n else np.nan,
                   median=float(scores.median()) if n else np.nan,
                   sample_sd=round(float(scores.std(ddof=1)), 3) if n > 1 else np.nan,
                   favorable_n=int(counts.get(order[3], 0) + counts.get(order[4], 0)),
                   favorable_pct=round(100*(counts.get(order[3], 0)+counts.get(order[4], 0))/n, 2) if n else np.nan,
                   middle_n=int(counts.get(order[2], 0)),
                   unfavorable_n=int(counts.get(order[0], 0)+counts.get(order[1], 0)))
        for label in order:
            key = f"score_{order.index(label)+1}"
            row[key+"_n"] = int(counts.get(label, 0))
            row[key+"_pct"] = round(100*row[key+"_n"]/n, 2) if n else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def profile_table(frame: pd.DataFrame, fields: list[dict]) -> pd.DataFrame:
    rows=[]
    for field in (f for f in fields if f["section"] == "profile"):
        values=frame[field["source_column"]].dropna().astype(str).value_counts()
        for response, n in values.items():
            rows.append(dict(item_id=field["id"], profile=field["label"], response=response,
                             count=int(n), valid_n=int(values.sum()), percentage=round(100*n/values.sum(),2)))
    return pd.DataFrame(rows)


THEMES = {
    "Q34": {
        "Ask AI learning support": ["ask ai", "ai assistant"],
        "Forecast information": ["prediction", "forecast", "gainer"],
        "Historical data or charts": ["historical", "chart", "data overview"],
        "Beginner/Advanced view": ["beginner and advanced", "mode toggle"],
    },
    "Q36": {
        "Tooltips and terminology": ["tooltip", "question-mark", "acronym", "jargon", "terms"],
        "First-time guidance": ["walkthrough", "guided tour"],
        "Visual design and chart legend": ["color design", "color legend"],
        "No additional change suggested": ["^none", "everything already fine", "all best for me"],
    },
}


def qualitative_table(frame: pd.DataFrame, fields: list[dict]) -> pd.DataFrame:
    import re
    rows=[]
    for q in ("Q34", "Q35", "Q36"):
        col=next(f["source_column"] for f in fields if f["id"] == q)
        texts=frame[col].fillna("").astype(str).str.strip()
        if q == "Q35":
            rows.append(dict(item_id=q, theme="Optional issue item left blank", respondent_n=int(texts.eq("").sum()),
                             denominator=len(frame), coding_rule="Blank response; does not prove no defects"))
            if texts.ne("").any():
                rows.append(dict(item_id=q, theme="Substantive issue report", respondent_n=int(texts.ne("").sum()),
                                 denominator=len(frame), coding_rule="Nonblank response; review privately before publication"))
            continue
        covered=set()
        for theme, patterns in THEMES[q].items():
            matches={i for i, s in enumerate(texts) if any(re.search(p, s, re.I) for p in patterns)}
            covered |= matches
            rows.append(dict(item_id=q, theme=theme, respondent_n=len(matches), denominator=len(frame),
                             coding_rule="case-insensitive literal/regex terms: "+", ".join(patterns)))
        unmatched=[i for i,s in enumerate(texts) if s and i not in covered]
        if unmatched:
            rows.append(dict(item_id=q, theme="Other substantive feedback for manual review", respondent_n=len(unmatched),
                             denominator=len(frame), coding_rule="Nonblank answer unmatched by listed themes"))
    return pd.DataFrame(rows)


def device_comparison(desktop: pd.DataFrame, mobile: pd.DataFrame) -> pd.DataFrame:
    # These are related experiences, but their wording and scope differ.
    pairs=[("Perceived loading", "Q29_02", "Q33_08"),
           ("Controls", "Q29_06", "Q33_07"),
           ("Readability", "Q29_07", "Q33_03"),
           ("Visual readability", "Q29_08", "Q33_04")]
    rows=[]
    for label,d,m in pairs:
        a=desktop.set_index("item_id").loc[d]; b=mobile.set_index("item_id").loc[m]
        rows.append(dict(related_construct=label, desktop_item=d, mobile_item=m,
                         desktop_valid_n=a.valid_n, mobile_valid_n=b.valid_n,
                         desktop_favorable_pct=a.favorable_pct, mobile_favorable_pct=b.favorable_pct,
                         desktop_mean=a["mean"], mobile_mean=b["mean"],
                         interpretation="Related but differently worded items; descriptive comparison only"))
    return pd.DataFrame(rows)


# Current Capstone 2 Chapter III, Requirements Traceability Matrix (Table 9).
# Each classification describes only the indicated UAT component, never the
# full requirement's technical or forecasting acceptance status.
REQUIREMENTS = [
    ("FR-01", "Display ticker, complete company name, and official PSE sector.", "Q9,Q10", "Partially supported by UAT", "Company finding/selection perceived as easy; correctness for all 15 companies requires functional verification."),
    ("FR-02", "Display historical OHLCV and volume through readable interactive views.", "Q11,Q28_01", "Partially supported by UAT", "Historical context was rated clear/helpful; displayed OHLCV values and ranges require data/output verification."),
    ("FR-03", "Display next-trading-session forecast and forecast metadata.", "Q28_02", "Partially supported by UAT", "Forecast feature rated helpful; target, price, and metadata correctness require output verification."),
    ("FR-04", "Compare forecasts with corresponding actual closing prices.", "Q12,Q28_03", "Partially supported by UAT", "Chart distinction/helpfulness rated; actual/predicted date alignment and accuracy require separate formal and output evidence."),
    ("FR-05", "Support company and sector browsing and sector-peer context.", "Q9,Q10", "Partially supported by UAT", "Company/sector finding and selection rated; approved three-peer membership and comparison behavior not directly evaluated."),
    ("FR-06", "Provide plain-language educational explanations and definitions.", "Q18,Q25,Q28_06,Q28_08,Q36", "Partially supported by UAT", "Explanation clarity/helpfulness rated; coverage and independent comprehension/task success not established."),
    ("FR-07", "Display source, freshness, dates, and relevant model/artifact information.", "Q8,Q23,Q29_05", "Partially supported by UAT", "Source/freshness visibility rated; metadata accuracy and coverage require output verification."),
    ("FR-08", "Display uncertainty, limitations, and responsible-use notices.", "Q22,Q27", "Partially supported by UAT", "Limitation/educational-purpose clarity rated; comprehension and notice coverage on every relevant page not established."),
    ("FR-09", "Support appropriate searching, filtering, navigation, and historical-range controls.", "Q9,Q10,Q29_06,Q33_07", "Partially supported by UAT", "Control ease rated; synchronized behavior and valid displayed information require functional verification."),
    ("FR-10", "Present comparative model-performance evidence.", "Q21,Q28_04", "Partially supported by UAT", "Methods explanation and model-ranking helpfulness rated; displayed metrics and rankings require comparison with approved backend artifacts."),
    ("NFR-01", "Provide clear, consistent, summary-first navigation.", "Q7,Q9,Q10,Q17,Q19,Q20,Q24,Q29_01,Q33_01", "Partially supported by UAT", "Navigation perceptions rated; unaided first-time core-task completion not recorded."),
    ("NFR-02", "Maintain readable charts, labels, spacing, contrast, and beginner-friendly language.", "Q12,Q18,Q29_07,Q29_08,Q33_03,Q33_04", "UAT rating component met", "All indicated readability ratings favorable; contrast, coverage, and accessibility need separate review."),
    ("NFR-03", "Load common pages and published outputs efficiently.", "Q29_02,Q33_08", "Requires technical verification", "Perceived speed rated; the five-second timing criterion requires measured trials."),
    ("NFR-04", "Support desktop, laptop, tablet, and mobile viewing.", "Q33_01,Q33_02,Q33_03,Q33_04,Q33_05,Q33_06,Q33_07,Q33_09", "Partially supported by UAT", "Mobile experience rated; defined-viewport overflow and compatibility require technical tests."),
    ("NFR-05", "Avoid unnecessary registration and personal-data collection.", "", "Not directly evaluated by UAT", "Anonymous access and personal-data behavior require privacy/functional tests."),
    ("NFR-06", "Provide readable Dark Mode and Light Mode presentation.", "Q6,Q32,Q29_08,Q28_09", "UAT rating component met", "Visual comfort rated favorably and dark mode preferred; light-mode legibility and theme consistency need visual/technical verification."),
]


def run(workbook: Path, output: Path = HERE) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    frame, mapping, meta=load_validate(workbook)
    (output/"uat_question_mapping.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False)+"\n")
    fields=mapping["fields"]
    tables={
        "uat_participant_profile.csv": profile_table(frame,fields),
        "uat_navigation_usability_summary.csv": rating_table(frame,fields,"navigation"),
        "uat_feature_helpfulness_summary.csv": rating_table(frame,fields,"feature"),
        "uat_desktop_experience_summary.csv": rating_table(frame,fields,"desktop"),
        "uat_mobile_experience_summary.csv": rating_table(frame,fields,"mobile"),
        "uat_qualitative_themes.csv": qualitative_table(frame,fields),
    }
    tables["uat_device_comparison.csv"]=device_comparison(tables["uat_desktop_experience_summary.csv"],tables["uat_mobile_experience_summary.csv"])
    rating_index=pd.concat([tables[k] for k in ("uat_navigation_usability_summary.csv","uat_feature_helpfulness_summary.csv","uat_desktop_experience_summary.csv","uat_mobile_experience_summary.csv")]).set_index("item_id")
    alignment=[]
    for req,definition,items,status,note in REQUIREMENTS:
        ids=[i for i in items.split(",") if i in rating_index.index]
        pct=round(float(rating_index.loc[ids,"favorable_n"].sum()/rating_index.loc[ids,"valid_n"].sum()*100),2) if ids else np.nan
        alignment.append(dict(requirement_id=req, current_requirement=definition, evidence_items=items, classification=status,
                              pooled_item_response_favorable_pct=pct, note=note))
    tables["uat_requirement_alignment.csv"]=pd.DataFrame(alignment)
    summary=[]
    for label,key in [("Navigation/usability","uat_navigation_usability_summary.csv"),
                      ("Feature helpfulness","uat_feature_helpfulness_summary.csv"),
                      ("Desktop/laptop experience","uat_desktop_experience_summary.csv"),
                      ("Tablet/mobile experience","uat_mobile_experience_summary.csv")]:
        t=tables[key]
        summary.append(dict(section=label, items=len(t), respondents=len(frame), valid_item_responses=int(t.valid_n.sum()),
                            favorable_item_responses=int(t.favorable_n.sum()),
                            favorable_item_response_pct=round(100*t.favorable_n.sum()/t.valid_n.sum(),2),
                            lowest_item_id=t.sort_values(["favorable_pct","mean"]).iloc[0].item_id,
                            lowest_item_mean=t.sort_values(["favorable_pct","mean"]).iloc[0]["mean"]))
    tables["uat_chapter4_summary.csv"]=pd.DataFrame(summary)
    for name,table in tables.items():
        table.to_csv(output/name,index=False)
    LOG.info("Wrote %d aggregate CSV tables",len(tables))
    validation=(f"# UAT data validation\n\nSource: researcher-supplied complete Google Forms response workbook, sheet `Form Responses 1`.\n\n"
                f"SHA-256: `{meta['source_sha256']}`. The private workbook is not stored here.\n\n"
                f"Submissions: {meta['submissions']}; eligible consenting responses: {meta['valid']}; exclusions: 0; unique email keys: {meta['unique_respondents']}. "
                f"Duplicate email keys: {meta['duplicate_email']}; duplicate full rows: {meta['duplicate_rows']}. "
                f"Timestamp range: {meta['first_timestamp']} to {meta['last_timestamp']} (workbook timezone unspecified).\n\n"
                f"All {meta['valid']} consented and acknowledged educational/non-advisory use. All 47 rating items use permitted final-questionnaire labels. "
                f"Missing rating responses: {sum(meta['missing'][f['id']] for f in fields if f['scale'])}; Q35 optional blanks: {meta['missing']['Q35']}. "
                f"Other missing questionnaire answers: {sum(v for k,v in meta['missing'].items() if k!='Q35')}.\n\n"
                "The PDF was exported on 2026-10-16 while responses began on 2026-10-13. The workbook has no per-response form-version field. "
                "Headers, all final matrix rows, and observed option labels are compatible with the final PDF; this does not independently prove the form version each person saw. "
                "Earlier submissions were retained as directed by the researcher. Any later version evidence should be reviewed before manuscript finalization.\n\n"
                "No emails, names, timestamps at respondent level, row-level ratings, or raw free text are published. Qualitative output contains aggregate theme counts only.\n")
    (output/"UAT_DATA_VALIDATION.md").write_text(validation)
    return dict(meta=meta,mapping=mapping,tables=tables)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=HERE)
    args=parser.parse_args()
    run(args.workbook,args.output)
