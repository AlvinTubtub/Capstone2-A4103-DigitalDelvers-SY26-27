"""Logic checks using synthetic answers only; no participant records are stored."""
import json
import unittest
from pathlib import Path

import pandas as pd

from uat_analysis import REQUIREMENTS, make_mapping, qualitative_table, rating_table


HERE = Path(__file__).resolve().parent


class UATAnalysisTests(unittest.TestCase):
    def test_favorable_helpfulness_excludes_middle_category(self):
        field = {"id": "Q28_01", "section": "feature", "label": "Feature",
                 "source_column": "Feature", "scale": "helpfulness"}
        answers = pd.DataFrame({"Feature": ["Not Helpful", "Slightly Helpful",
                                             "Moderately Helpful", "Very Helpful",
                                             "Extremely Helpful", None]})
        row = rating_table(answers, [field], "feature").iloc[0]
        self.assertEqual((row.valid_n, row.missing_n, row.favorable_n), (5, 1, 2))
        self.assertEqual(row.favorable_pct, 40.0)
        self.assertEqual(row["mean"], 3.0)
        self.assertEqual(row["median"], 3.0)
        self.assertEqual(sum(row[f"score_{i}_n"] for i in range(1, 6)), 5)

    def test_schema_drift_is_rejected(self):
        mapping = json.loads((HERE / "uat_question_mapping.json").read_text())
        columns = [*mapping["administrative_fields"]]
        columns += [next(f["source_column"] for f in mapping["fields"] if f["id"] == f"Q{i}") for i in range(4, 28)]
        columns += [next(f["source_column"] for f in mapping["fields"] if f["id"] == f"Q28_{i:02d}") for i in range(1, 10)]
        columns += [next(f["source_column"] for f in mapping["fields"] if f["id"] == f"Q29_{i:02d}") for i in range(1, 9)]
        columns += [next(f["source_column"] for f in mapping["fields"] if f["id"] == f"Q{i}") for i in range(30, 33)]
        columns += [next(f["source_column"] for f in mapping["fields"] if f["id"] == f"Q33_{i:02d}") for i in range(1, 10)]
        columns += [next(f["source_column"] for f in mapping["fields"] if f["id"] == f"Q{i}") for i in range(34, 37)]
        self.assertEqual(make_mapping(columns)["rating_count"], 47)
        columns[26] = "Obsolete principal-versus-Naive question"
        with self.assertRaises(ValueError):
            make_mapping(columns)

    def test_qualitative_counts_distinct_respondents_and_blanks(self):
        fields = [{"id": q, "section": "qualitative", "source_column": q} for q in ("Q34", "Q35", "Q36")]
        answers = pd.DataFrame({"Q34": ["Ask AI and forecast chart", "Ask AI", "Forecast chart"],
                                "Q35": [None, "", None],
                                "Q36": ["Add tooltips and a guided tour", "None", "Improve color legend"]})
        table = qualitative_table(answers, fields).set_index(["item_id", "theme"])
        self.assertEqual(table.loc[("Q34", "Ask AI learning support"), "respondent_n"], 2)
        self.assertEqual(table.loc[("Q34", "Forecast information"), "respondent_n"], 2)
        self.assertEqual(table.loc[("Q35", "Optional issue item left blank"), "respondent_n"], 3)
        self.assertEqual(table.loc[("Q36", "First-time guidance"), "respondent_n"], 1)

    def test_current_chapter_three_rtm_definitions(self):
        requirements = {row[0]: row for row in REQUIREMENTS}
        self.assertEqual(len(requirements), 16)
        self.assertEqual(set(requirements), {*(f"FR-{i:02d}" for i in range(1, 11)),
                                             *(f"NFR-{i:02d}" for i in range(1, 7))})
        self.assertEqual(requirements["FR-05"][1],
                         "Support company and sector browsing and sector-peer context.")
        self.assertEqual(requirements["FR-10"][1],
                         "Present comparative model-performance evidence.")
        self.assertEqual(requirements["FR-10"][2], "Q21,Q28_04")
        self.assertNotIn("upload", " ".join(str(x) for row in REQUIREMENTS for x in row).lower())
        self.assertTrue(all("UAT" in row[3] or row[3] == "Requires technical verification"
                            for row in REQUIREMENTS))

    def test_verified_final_output_counts_and_absence_of_removed_item(self):
        mapping = json.loads((HERE / "uat_question_mapping.json").read_text())
        rating_fields = [f for f in mapping["fields"] if f["scale"]]
        self.assertEqual(len(rating_fields), 47)
        self.assertFalse(any("principal" in f["source_column"].lower() and
                             "naive" in f["source_column"].lower() for f in mapping["fields"]))
        files = ("uat_navigation_usability_summary.csv", "uat_feature_helpfulness_summary.csv",
                 "uat_desktop_experience_summary.csv", "uat_mobile_experience_summary.csv")
        tables = [pd.read_csv(HERE / name) for name in files]
        self.assertEqual([len(t) for t in tables], [21, 9, 8, 9])
        self.assertEqual(sum(int(t.valid_n.sum()) for t in tables), 376)
        self.assertEqual(sum(int(t.favorable_n.sum()) for t in tables), 376)
        self.assertTrue(all(t.valid_n.eq(8).all() and t.missing_n.eq(0).all() for t in tables))
        feature = tables[1].set_index("item_id")
        self.assertEqual(feature.loc["Q28_02", "mean"], 4.625)
        self.assertEqual(feature.loc["Q28_08", "mean"], 4.750)
        self.assertEqual(tables[3].set_index("item_id").loc["Q33_06", "mean"], 4.375)


if __name__ == "__main__":
    unittest.main()
