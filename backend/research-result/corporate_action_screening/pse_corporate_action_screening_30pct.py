#!/usr/bin/env python3
"""
PSE 30% Material Price-Discontinuity and Known-Event Screening

This script documents potential material price discontinuities in the finalized
15-stock PSE dataset. It does not remove, replace, adjust, winsorize, or
overwrite any OHLCV record.

Screening rules
---------------
1. Flag an absolute close-to-close change of at least 30%.
2. Flag an absolute opening gap from the previous Close of at least 30%.
3. Flag predetermined official-event dates even when the movement is below 30%.
4. Prefill the documented manual-verification results for the seven verified dates.
5. Report ticker and company-name consistency.

The only input is the immutable frozen raw CSV set in
FORECASTPH_FORMAL_20260911_01. The script never reads operational raw data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config.companies import COMPANIES, COMPANY_BY_SYMBOL
from src.formal.archive import FormalRunArchive

FORMAL_RUN_ID = "FORECASTPH_FORMAL_20260911_01"
FORMAL_CUTOFF = "2026-09-11"
START_DATE = "2020-01-02"
THRESHOLD_PCT = 30.0
EXPECTED_ROWS_PER_COMPANY = 1635
FORMAL_ROOT = BACKEND_ROOT / "artifacts/evaluations/formal-runs"
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "research-result/corporate_action_screening"
DEFAULT_SYMBOLS = [company.symbol for company in COMPANIES]

REQUIRED_COLUMNS = {"Date", "Symbol", "Open", "Close"}
SKIP_DIRS = {
    "validation_reports", "corporate_action_screening", "reports", "outputs",
    "features", "cleaned", "combined", "__pycache__",
}

# Predetermined dates from official PSE/PSE EDGE publications.
# date_rule="ON_OR_NEXT_TRADING_DAY" means that if the official date is not a
# trading date, the script maps it to the first available trading date after it.
KNOWN_EVENTS = [
    {
        "Symbol": "GLO",
        "Official_Event_Date": "2022-09-16",
        "Known_Event_Type": "Stock Rights Offering - Ex-Rights Date",
        "Known_Event_Description": (
            "Globe Telecom stock-rights offering ex-rights date; the official "
            "disclosure stated that share-price and outstanding-share "
            "adjustments would take effect on the ex-date."
        ),
        "Official_Reference": "PSE EDGE file_id=1184735",
        "Date_Rule": "ON_OR_NEXT_TRADING_DAY",
    },
    {
        "Symbol": "GLO",
        "Official_Event_Date": "2022-10-28",
        "Known_Event_Type": "Stock Rights Offering - Rights Shares Listing Date",
        "Known_Event_Description": (
            "Listing date of the additional common shares issued through "
            "Globe Telecom's 2022 stock-rights offering."
        ),
        "Official_Reference": "PSE EDGE file_id=1182753",
        "Date_Rule": "ON_OR_NEXT_TRADING_DAY",
    },
    {
        "Symbol": "BPI",
        "Official_Event_Date": "2024-01-01",
        "Known_Event_Type": "Merger Effective Date",
        "Known_Event_Description": (
            "The BPI-Robinsons Bank merger became effective with BPI as the "
            "surviving listed entity. The script checks the first available "
            "BPI trading date on or after the official date."
        ),
        "Official_Reference": "PSE EDGE file_id=1419237",
        "Date_Rule": "ON_OR_NEXT_TRADING_DAY",
    },
    {
        "Symbol": "SHLPH",
        "Official_Event_Date": "2023-03-28",
        "Known_Event_Type": "Corporate Name Change Effective in PSE Systems",
        "Known_Event_Description": (
            "Corporate name changed from Pilipinas Shell Petroleum Corporation "
            "to Shell Pilipinas Corporation; ticker remained SHLPH."
        ),
        "Official_Reference": "PSE EDGE file_id=1292349",
        "Date_Rule": "ON_OR_NEXT_TRADING_DAY",
    },
    {
        "Symbol": "JFC",
        "Official_Event_Date": "2026-01-06",
        "Known_Event_Type": "Material Spin-Off Announcement and Trading Halt",
        "Known_Event_Description": (
            "JFC announced its planned international-business spin-off and "
            "U.S. listing; the PSE imposed a one-hour trading halt."
        ),
        "Official_Reference": "PSE EDGE file_id=1854143 / file_id=1853913",
        "Date_Rule": "ON_OR_NEXT_TRADING_DAY",
    },
    {
        "Symbol": "ALI",
        "Official_Event_Date": "2022-06-29",
        "Known_Event_Type": "Voting Preferred Share Convertibility Commenced",
        "Known_Event_Description": (
            "ALI voting preferred shares became convertible into common shares "
            "under the disclosed terms."
        ),
        "Official_Reference": "PSE EDGE file_id=1123016",
        "Date_Rule": "ON_OR_NEXT_TRADING_DAY",
    },
]

# Manually verified classifications for the seven documented stock-dates.
# Keys use the resolved trading date written by the screening process.
# Any future flag not listed here remains pending manual verification.
VERIFIED_EVENT_REVIEWS = {
    ("ALI", "2022-06-29"): {
        "Original_PSE_PDF_Checked": "YES",
        "Manual_Verification_Status": "VERIFIED",
        "Confirmed_Event_Type": (
            "Voting preferred share convertibility commenced"
        ),
        "Official_PSE_or_EDGE_Reference_Checked": (
            "Original PSE Daily Quotations Report; PSE EDGE file_id=1123016"
        ),
        "Structural_Price_Scale_Event": "NO",
        "Final_Treatment": "RETAINED UNCHANGED AND DOCUMENTED",
        "Reviewer_Notes": (
            "The known share-structure event did not meet the 30% material "
            "price-discontinuity threshold and did not create an observed "
            "split-like price-scale reset."
        ),
    },
    ("APX", "2020-10-16"): {
        "Original_PSE_PDF_Checked": "YES",
        "Manual_Verification_Status": "VERIFIED",
        "Confirmed_Event_Type": (
            "Event-driven market movement associated with a mining and oil "
            "sector rally"
        ),
        "Official_PSE_or_EDGE_Reference_Checked": (
            "Original PSE Daily Quotations Report; supporting market-news "
            "documentation for the lifting of the oil-exploration moratorium"
        ),
        "Structural_Price_Scale_Event": "NO",
        "Final_Treatment": "RETAINED UNCHANGED AND FLAGGED FOR INTERPRETATION",
        "Reviewer_Notes": (
            "The observation exceeded the 30% screening benchmark, but manual "
            "verification linked the movement to a genuine event-driven market "
            "rally rather than a stock split, stock dividend, rights offering, "
            "ticker change, or extraction error."
        ),
    },
    ("BPI", "2024-01-02"): {
        "Original_PSE_PDF_Checked": "YES",
        "Manual_Verification_Status": "VERIFIED",
        "Confirmed_Event_Type": (
            "First available trading date after the BPI-Robinsons Bank merger "
            "effective date"
        ),
        "Official_PSE_or_EDGE_Reference_Checked": (
            "Original PSE Daily Quotations Report; PSE EDGE file_id=1419237"
        ),
        "Structural_Price_Scale_Event": "NO",
        "Final_Treatment": "RETAINED UNCHANGED AND DOCUMENTED",
        "Reviewer_Notes": (
            "The merger-effective date fell on 2024-01-01, so the first "
            "available trading observation on 2024-01-02 was reviewed. No "
            "material or permanent split-like price-scale discontinuity was "
            "observed."
        ),
    },
    ("GLO", "2022-09-16"): {
        "Original_PSE_PDF_Checked": "YES",
        "Manual_Verification_Status": "VERIFIED",
        "Confirmed_Event_Type": "Stock rights offering - ex-rights date",
        "Official_PSE_or_EDGE_Reference_Checked": (
            "Original PSE Daily Quotations Report; PSE EDGE file_id=1184735"
        ),
        "Structural_Price_Scale_Event": "NO",
        "Final_Treatment": "RETAINED UNCHANGED AND DOCUMENTED",
        "Reviewer_Notes": (
            "The confirmed ex-rights date did not meet the 30% screening "
            "threshold and did not create an observed split-like reset in the "
            "raw price series."
        ),
    },
    ("GLO", "2022-10-28"): {
        "Original_PSE_PDF_Checked": "YES",
        "Manual_Verification_Status": "VERIFIED",
        "Confirmed_Event_Type": (
            "Stock rights offering - additional rights shares listing date"
        ),
        "Official_PSE_or_EDGE_Reference_Checked": (
            "Original PSE Daily Quotations Report; PSE EDGE file_id=1182753"
        ),
        "Structural_Price_Scale_Event": "NO",
        "Final_Treatment": "RETAINED UNCHANGED AND DOCUMENTED",
        "Reviewer_Notes": (
            "The rights-shares listing date did not meet the 30% screening "
            "threshold and showed no observed permanent price-scale reset."
        ),
    },
    ("JFC", "2026-01-06"): {
        "Original_PSE_PDF_Checked": "YES",
        "Manual_Verification_Status": "VERIFIED",
        "Confirmed_Event_Type": (
            "Material spin-off announcement and temporary trading halt"
        ),
        "Official_PSE_or_EDGE_Reference_Checked": (
            "Original PSE Daily Quotations Report; PSE EDGE "
            "file_id=1854143 / file_id=1853913"
        ),
        "Structural_Price_Scale_Event": "NO",
        "Final_Treatment": "RETAINED UNCHANGED AND DOCUMENTED",
        "Reviewer_Notes": (
            "The movement was associated with a material announcement. The "
            "spin-off had not been completed within the study period, and the "
            "date did not meet the 30% material-discontinuity threshold."
        ),
    },
    ("SHLPH", "2023-03-28"): {
        "Original_PSE_PDF_Checked": "YES",
        "Manual_Verification_Status": "VERIFIED",
        "Confirmed_Event_Type": (
            "Corporate name change effective in PSE systems; ticker unchanged"
        ),
        "Official_PSE_or_EDGE_Reference_Checked": (
            "Original PSE Daily Quotations Report; PSE EDGE file_id=1292349"
        ),
        "Structural_Price_Scale_Event": "NO",
        "Final_Treatment": (
            "RETAINED UNCHANGED; SOURCE NAMES MAPPED TO ONE CANONICAL COMPANY"
        ),
        "Reviewer_Notes": (
            "The event was a company-name change only. The ticker remained "
            "SHLPH, so the observations form one continuous stock series. The "
            "raw source-reported names are preserved, while Shell Pilipinas "
            "Corporation may be used as the canonical display name."
        ),
    },
}

# Old report's verified stock-date OHLCV, used only as a guard before carrying
# its human classification forward. September metrics are always recomputed.
VERIFIED_OHLCV = {
    ("ALI", "2022-06-29"): (27.2, 27.8, 26.8, 26.8, 9339400),
    ("APX", "2020-10-16"): (2.32, 2.32, 2.0, 2.09, 198650000),
    ("BPI", "2024-01-02"): (104.0, 105.8, 104.0, 105.8, 1153110),
    ("GLO", "2022-09-16"): (2102.0, 2190.0, 2094.0, 2118.0, 115725),
    ("GLO", "2022-10-28"): (2280.0, 2358.0, 2272.0, 2322.0, 77630),
    ("JFC", "2026-01-06"): (190.5, 210.0, 188.4, 210.0, 4641800),
    ("SHLPH", "2023-03-28"): (16.2, 16.2, 16.06, 16.08, 152500),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Flag >=30% PSE price discontinuities and predetermined official "
            "event dates without modifying any OHLCV record."
        )
    )
    parser.add_argument("--formal-root", type=Path, default=FORMAL_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


def normalize_column(name: object) -> str:
    raw = str(name).strip()
    key = re.sub(r"[^a-z0-9]+", "", raw.lower())
    mapping = {
        "date": "Date",
        "tradingdate": "Date",
        "symbol": "Symbol",
        "ticker": "Symbol",
        "stocksymbol": "Symbol",
        "name": "Name",
        "companyname": "Name",
        "sector": "Sector",
        "open": "Open",
        "openingprice": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "closingprice": "Close",
        "volume": "Volume",
        "value": "Value_PHP",
        "valuephp": "Value_PHP",
        "sourcefile": "Source_File",
    }
    return mapping.get(key, raw)


def to_numeric(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip()
    text = text.replace(
        {
            "": pd.NA,
            "-": pd.NA,
            "--": pd.NA,
            "—": pd.NA,
            "N/A": pd.NA,
            "NA": pd.NA,
            "null": pd.NA,
            "None": pd.NA,
        }
    )
    text = text.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    text = text.str.replace(",", "", regex=False)
    text = text.str.replace("₱", "", regex=False)
    text = text.str.replace("PHP", "", regex=False)
    text = text.str.replace("%", "", regex=False)
    text = text.str.replace(r"\s+", "", regex=True)
    return pd.to_numeric(text, errors="coerce")


def skip_file(path: Path, output_dir: Path) -> bool:
    try:
        path.resolve().relative_to(output_dir.resolve())
        return True
    except ValueError:
        pass
    return bool({part.lower() for part in path.parts} & SKIP_DIRS)


def infer_symbol(path: Path, symbols: set[str]) -> str | None:
    stem = path.stem.upper()
    matches = [
        symbol
        for symbol in symbols
        if re.search(rf"(^|[^A-Z0-9]){re.escape(symbol)}([^A-Z0-9]|$)", stem)
    ]
    return matches[0] if len(matches) == 1 else None


def load_data(
    input_dir: Path,
    output_dir: Path,
    symbols: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Read only the integrity-checked frozen formal CSV set."""
    archive = FormalRunArchive(FORMAL_RUN_ID, root=input_dir.parent.parent)
    if input_dir != archive.path / "frozen_raw" or not archive.verify_integrity():
        raise ValueError("Frozen formal archive is missing or fails integrity verification")
    frames: list[pd.DataFrame] = []
    accepted_files: list[str] = []
    actual = {path.name for path in input_dir.iterdir() if path.is_file()}
    expected = {f"{symbol}.csv" for symbol in symbols}
    if actual != expected:
        raise ValueError(f"Frozen symbol coverage mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    for symbol in symbols:
        path = input_dir / f"{symbol}.csv"
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(frame.columns):
            raise ValueError(f"{symbol}: missing frozen OHLCV columns")
        frame["Symbol"] = symbol
        frame["Name"] = COMPANY_BY_SYMBOL[symbol].name
        frame["Sector"] = COMPANY_BY_SYMBOL[symbol].sector
        frame["Value_PHP"] = pd.NA  # Not recorded by this frozen formal source.
        frame["Source_File"] = f"frozen_raw/{symbol}.csv"
        frame["Input_CSV_File"] = f"frozen_raw/{symbol}.csv"
        frames.append(frame)
        accepted_files.append(f"frozen_raw/{symbol}.csv")
    return pd.concat(frames, ignore_index=True, sort=False), accepted_files


def prepare_data(
    raw: pd.DataFrame,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    data = raw.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="raise").dt.normalize()
    data["Symbol"] = data["Symbol"].astype("string").str.strip().str.upper()

    for col in ["Open", "High", "Low", "Close", "Volume", "Value_PHP"]:
        if col in data.columns:
            data[col] = to_numeric(data[col])
    required_numbers = ["Open", "High", "Low", "Close", "Volume"]
    if data[required_numbers].isna().any().any():
        raise ValueError("Malformed frozen OHLCV numeric value")
    if (data[["Open", "High", "Low", "Close"]] <= 0).any().any() or (data["Volume"] < 0).any():
        raise ValueError("Invalid frozen OHLCV range")

    for optional in ["Name", "Sector", "High", "Low", "Volume", "Value_PHP", "Source_File"]:
        if optional not in data.columns:
            data[optional] = pd.NA

    data = data[
        data["Symbol"].isin(symbols)
        & data["Date"].between(start_date, end_date, inclusive="both")
    ].copy()
    data = data[data["Date"].notna()].copy()

    order = {symbol: index for index, symbol in enumerate(symbols)}
    data["_Symbol_Order"] = data["Symbol"].map(order)
    return data.sort_values(
        ["_Symbol_Order", "Date", "Input_CSV_File"], kind="stable"
    ).reset_index(drop=True)


def duplicate_report(data: pd.DataFrame) -> pd.DataFrame:
    mask = data.duplicated(["Symbol", "Date"], keep=False)
    cols = [
        "Symbol", "Name", "Date", "Open", "High", "Low", "Close", "Volume",
        "Value_PHP", "Source_File", "Input_CSV_File",
    ]
    return data.loc[mask, cols].sort_values(
        ["Symbol", "Date", "Input_CSV_File"]
    )


def calculate_metrics(data: pd.DataFrame) -> pd.DataFrame:
    if data.duplicated(["Symbol", "Date"]).any():
        raise ValueError("Duplicate symbol-date rows cannot be silently deduplicated")
    result = data.sort_values(["_Symbol_Order", "Date"]).reset_index(drop=True)
    grouped = result.groupby("Symbol", sort=False)

    result["Previous_Trading_Date"] = grouped["Date"].shift(1)
    result["Next_Trading_Date"] = grouped["Date"].shift(-1)
    result["Previous_Close"] = grouped["Close"].shift(1)
    result["Next_Close"] = grouped["Close"].shift(-1)
    result["Previous_Volume"] = grouped["Volume"].shift(1)

    valid_prev_close = result["Previous_Close"].notna() & (result["Previous_Close"] != 0)
    result["Close_to_Close_Change_Pct"] = np.where(
        valid_prev_close,
        (result["Close"] / result["Previous_Close"] - 1.0) * 100.0,
        np.nan,
    )
    result["Opening_Gap_Pct"] = np.where(
        valid_prev_close,
        (result["Open"] / result["Previous_Close"] - 1.0) * 100.0,
        np.nan,
    )

    valid_prev_volume = result["Previous_Volume"].notna() & (result["Previous_Volume"] != 0)
    result["Volume_Change_Pct"] = np.where(
        valid_prev_volume,
        (result["Volume"] / result["Previous_Volume"] - 1.0) * 100.0,
        np.nan,
    )

    # Context only: five observations before and after each date.
    result["Pre_5Day_Median_Close"] = grouped["Close"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).median()
    )
    result["Post_5Day_Median_Close"] = grouped["Close"].transform(
        lambda s: s.shift(-1).iloc[::-1].rolling(5, min_periods=1).median().iloc[::-1]
    )
    valid_pre = result["Pre_5Day_Median_Close"].notna() & (
        result["Pre_5Day_Median_Close"] != 0
    )
    result["Post_vs_Pre_5Day_Median_Change_Pct"] = np.where(
        valid_pre,
        (result["Post_5Day_Median_Close"] / result["Pre_5Day_Median_Close"] - 1.0)
        * 100.0,
        np.nan,
    )
    return result


def resolve_known_events(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for event in KNOWN_EVENTS:
        event_date = pd.Timestamp(event["Official_Event_Date"]).normalize()
        stock = metrics[metrics["Symbol"] == event["Symbol"]].sort_values("Date")
        candidates = stock[stock["Date"] >= event_date]

        row = dict(event)
        if stock.empty:
            row.update(
                {
                    "Resolved_Trading_Date": pd.NaT,
                    "Resolution_Status": "SYMBOL_NOT_FOUND",
                    "Resolution_Note": "No observations found for the event ticker.",
                }
            )
        elif candidates.empty:
            row.update(
                {
                    "Resolved_Trading_Date": pd.NaT,
                    "Resolution_Status": "NO_DATE_ON_OR_AFTER_EVENT",
                    "Resolution_Note": "No available trading observation on or after the event.",
                }
            )
        else:
            resolved = candidates.iloc[0]["Date"]
            if resolved == event_date:
                status = "EXACT_TRADING_DATE"
                note = "Official event date exists in the stock series."
            else:
                status = "NEXT_AVAILABLE_TRADING_DATE"
                note = (
                    f"Official date {event_date.date()} was not present; mapped to "
                    f"the first available trading date {resolved.date()}."
                )
            row.update(
                {
                    "Resolved_Trading_Date": resolved,
                    "Resolution_Status": status,
                    "Resolution_Note": note,
                }
            )
        rows.append(row)

    resolved = pd.DataFrame(rows)
    resolved["Official_Event_Date"] = pd.to_datetime(
        resolved["Official_Event_Date"], errors="coerce"
    )
    return resolved


def combine_flags(
    metrics: pd.DataFrame,
    known_events: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    result = metrics.copy()
    result["Close_Threshold_Flag"] = (
        result["Close_to_Close_Change_Pct"].abs() >= threshold
    )
    result["Opening_Gap_Threshold_Flag"] = (
        result["Opening_Gap_Pct"].abs() >= threshold
    )
    result["Thirty_Percent_Statistical_Flag"] = (
        result["Close_Threshold_Flag"] | result["Opening_Gap_Threshold_Flag"]
    )

    valid = known_events[known_events["Resolved_Trading_Date"].notna()].copy()
    valid = valid.rename(columns={"Resolved_Trading_Date": "Date"})

    event_cols = [
        "Symbol", "Date", "Official_Event_Date", "Known_Event_Type",
        "Known_Event_Description", "Official_Reference", "Resolution_Status",
        "Resolution_Note",
    ]
    valid = valid[event_cols]

    # Aggregate in case more than one known event resolves to one stock-date.
    if not valid.empty:
        valid = valid.groupby(["Symbol", "Date"], as_index=False).agg(
            {
                "Official_Event_Date": lambda x: " | ".join(
                    sorted({pd.Timestamp(v).strftime("%Y-%m-%d") for v in x})
                ),
                "Known_Event_Type": lambda x: " | ".join(dict.fromkeys(map(str, x))),
                "Known_Event_Description": lambda x: " | ".join(dict.fromkeys(map(str, x))),
                "Official_Reference": lambda x: " | ".join(dict.fromkeys(map(str, x))),
                "Resolution_Status": lambda x: " | ".join(dict.fromkeys(map(str, x))),
                "Resolution_Note": lambda x: " | ".join(dict.fromkeys(map(str, x))),
            }
        )

    result = result.merge(valid, on=["Symbol", "Date"], how="left")
    result["Known_Official_Event_Flag"] = result["Known_Event_Type"].notna()
    result["Final_Documentation_Flag"] = (
        result["Thirty_Percent_Statistical_Flag"]
        | result["Known_Official_Event_Flag"]
    )

    def reason(row: pd.Series) -> str:
        reasons: list[str] = []
        if row["Close_Threshold_Flag"]:
            reasons.append(f"Absolute close-to-close change >= {threshold:g}%")
        if row["Opening_Gap_Threshold_Flag"]:
            reasons.append(f"Absolute opening gap >= {threshold:g}%")
        if row["Known_Official_Event_Flag"]:
            reasons.append("Predetermined official-event date")
        return " | ".join(reasons)

    result["Flag_Reason"] = result.apply(reason, axis=1)
    flagged = result[result["Final_Documentation_Flag"]].copy()
    flagged["Screening_Threshold_Pct"] = threshold
    flagged["Automated_Classification"] = (
        "POTENTIAL_MATERIAL_DISCONTINUITY_REQUIRING_MANUAL_VERIFICATION"
    )
    flagged["Planned_Treatment"] = "RETAIN_UNCHANGED_PENDING_MANUAL_VERIFICATION"
    flagged["Removal_or_Adjustment_Performed"] = "NO"

    columns = [
        "Symbol", "Name", "Sector", "Date", "Previous_Trading_Date",
        "Next_Trading_Date", "Previous_Close", "Open", "High", "Low", "Close",
        "Next_Close", "Volume", "Previous_Volume", "Value_PHP",
        "Close_to_Close_Change_Pct", "Opening_Gap_Pct", "Volume_Change_Pct",
        "Pre_5Day_Median_Close", "Post_5Day_Median_Close",
        "Post_vs_Pre_5Day_Median_Change_Pct", "Close_Threshold_Flag",
        "Opening_Gap_Threshold_Flag", "Thirty_Percent_Statistical_Flag",
        "Known_Official_Event_Flag", "Official_Event_Date", "Known_Event_Type",
        "Known_Event_Description", "Official_Reference", "Resolution_Status",
        "Resolution_Note", "Flag_Reason", "Screening_Threshold_Pct",
        "Automated_Classification", "Planned_Treatment",
        "Removal_or_Adjustment_Performed", "Source_File", "Input_CSV_File",
    ]
    return flagged[[c for c in columns if c in flagged.columns]].sort_values(
        ["Symbol", "Date"]
    ).reset_index(drop=True)


def manual_template(flagged: pd.DataFrame) -> pd.DataFrame:
    """
    Create the manual-verification report and prefill already verified dates.

    Any new statistical flag or known-event date not listed in
    VERIFIED_EVENT_REVIEWS remains clearly marked as pending review.
    """
    template = flagged.copy()

    manual_columns = [
        "Original_PSE_PDF_Checked",
        "Manual_Verification_Status",
        "Confirmed_Event_Type",
        "Official_PSE_or_EDGE_Reference_Checked",
        "Structural_Price_Scale_Event",
        "Final_Treatment",
        "Reviewer_Name_or_Initials",
        "Verification_Date",
        "Reviewer_Notes",
    ]
    for column in manual_columns:
        template[column] = ""

    for index, row in template.iterrows():
        symbol = str(row["Symbol"]).strip().upper()
        resolved_date = pd.Timestamp(row["Date"]).strftime("%Y-%m-%d")
        review = VERIFIED_EVENT_REVIEWS.get((symbol, resolved_date))
        expected_ohlcv = VERIFIED_OHLCV.get((symbol, resolved_date))
        if review is not None and expected_ohlcv is not None:
            actual_ohlcv = tuple(float(row[column]) for column in ("Open", "High", "Low", "Close", "Volume"))
            if not np.allclose(actual_ohlcv, expected_ohlcv, rtol=0, atol=1e-9):
                review = None

        if review is None:
            template.at[index, "Manual_Verification_Status"] = "PENDING REVIEW"
            template.at[index, "Final_Treatment"] = (
                "RETAINED UNCHANGED PENDING MANUAL VERIFICATION"
            )
            template.at[index, "Reviewer_Notes"] = (
                "No pre-verified classification is stored for this newly "
                "flagged stock-date. Verify it against the original PSE Daily "
                "Quotations Report and relevant official disclosure before "
                "assigning a final classification."
            )
            continue

        for column, value in review.items():
            template.at[index, column] = value

    return template


def consistency_report(data: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        stock = data[data["Symbol"] == symbol]
        # Frozen modeling CSVs have no source issue-name column. A configured
        # display name is not evidence of historical source-name continuity.
        names: list[str] = []
        rows.append(
            {
                "Symbol": symbol,
                "First_Date": stock["Date"].min() if not stock.empty else pd.NaT,
                "Last_Date": stock["Date"].max() if not stock.empty else pd.NaT,
                "Observation_Count": int(len(stock)),
                "Unique_Company_Name_Count": len(names),
                "Observed_Company_Names": " | ".join(names),
                "Name_Review_Needed": "NOT ASSESSABLE FROM FROZEN OHLCV",
                "Ticker_Treatment_Performed": "NONE; SYMBOL COVERAGE VERIFIED",
            }
        )
    return pd.DataFrame(rows)


def summary_report(
    metrics: pd.DataFrame,
    flagged: pd.DataFrame,
    symbols: list[str],
    threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        stock = metrics[metrics["Symbol"] == symbol]
        flags = flagged[flagged["Symbol"] == symbol]
        statistical = (
            flags[flags["Thirty_Percent_Statistical_Flag"]]
            if not flags.empty
            else flags
        )
        known = (
            flags[flags["Known_Official_Event_Flag"]]
            if not flags.empty
            else flags
        )
        rows.append(
            {
                "Symbol": symbol,
                "Records_Screened": int(len(stock)),
                "First_Date": stock["Date"].min() if not stock.empty else pd.NaT,
                "Last_Date": stock["Date"].max() if not stock.empty else pd.NaT,
                "Threshold_Pct": threshold,
                "Unique_30Pct_Statistical_Flagged_Dates": int(
                    statistical["Date"].nunique()
                ) if not statistical.empty else 0,
                "Known_Official_Event_Flagged_Dates": int(
                    known["Date"].nunique()
                ) if not known.empty else 0,
                "Total_Unique_Flagged_Dates": int(flags["Date"].nunique())
                if not flags.empty else 0,
                "Maximum_Absolute_Close_Change_Pct": (
                    float(stock["Close_to_Close_Change_Pct"].abs().max())
                    if stock["Close_to_Close_Change_Pct"].notna().any()
                    else np.nan
                ),
                "Maximum_Absolute_Opening_Gap_Pct": (
                    float(stock["Opening_Gap_Pct"].abs().max())
                    if stock["Opening_Gap_Pct"].notna().any()
                    else np.nan
                ),
                "Records_Removed_or_Adjusted": 0,
                "Current_Treatment": "ALL FLAGGED RECORDS RETAINED UNCHANGED",
            }
        )
    return pd.DataFrame(rows)


def format_dates(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for col in output.columns:
        if pd.api.types.is_datetime64_any_dtype(output[col]):
            output[col] = output[col].dt.strftime("%Y-%m-%d")
    return output


def validate_formal_dataset(data: pd.DataFrame, symbols: list[str]) -> None:
    if symbols != DEFAULT_SYMBOLS or len(symbols) != 15:
        raise ValueError("Formal selected-symbol set changed")
    if len(data) != 24525 or data.duplicated(["Symbol", "Date"]).any():
        raise ValueError("Formal row count or duplicate symbol-date invariant failed")
    counts = data.groupby("Symbol").size().to_dict()
    if set(counts) != set(symbols) or any(count != EXPECTED_ROWS_PER_COMPANY for count in counts.values()):
        raise ValueError(f"Formal company coverage failed: {counts}")
    if data["Date"].min().strftime("%Y-%m-%d") != START_DATE or data["Date"].max().strftime("%Y-%m-%d") != FORMAL_CUTOFF:
        raise ValueError("Formal date range invariant failed")
    for symbol in symbols:
        stock = data[data["Symbol"] == symbol]
        if stock["Date"].iloc[0].strftime("%Y-%m-%d") != START_DATE or stock["Date"].iloc[-1].strftime("%Y-%m-%d") != FORMAL_CUTOFF:
            raise ValueError(f"{symbol}: formal date coverage failed")


def cross_check_data_quality(metrics: pd.DataFrame) -> None:
    path = BACKEND_ROOT / "research-result/data_quality.csv"
    rules = BACKEND_ROOT / "research-result/data_quality_rules.csv"
    quality = pd.read_csv(path, dtype=str, keep_default_na=False)
    rule_rows = pd.read_csv(rules, dtype=str, keep_default_na=False)
    rule = rule_rows[rule_rows["rule_name"] == "material_discontinuity"]
    if len(rule) != 1 or float(rule.iloc[0]["threshold_value"]) != 0.30:
        raise ValueError("Frozen material-discontinuity rule mismatch")
    if set(quality["symbol"]) != set(DEFAULT_SYMBOLS):
        raise ValueError("Frozen data-quality company coverage mismatch")
    for _, quality_row in quality.iterrows():
        stock = metrics[metrics["Symbol"] == quality_row["symbol"]]
        flagged = stock.loc[stock["Close_to_Close_Change_Pct"].abs() >= THRESHOLD_PCT, "Date"]
        dates = "|".join(flagged.dt.strftime("%Y-%m-%d").tolist())
        if dates != quality_row["material_discontinuity_dates"] or len(flagged) != int(quality_row["material_discontinuity_count"]):
            raise ValueError(f"Frozen data-quality contradiction: {quality_row['symbol']}")


PACKAGE_FILES = (
    "pse_corporate_action_screening_30pct.py",
    "ticker_name_consistency_report.csv",
    "screening_summary_by_symbol.csv",
    "screening_run.log",
    "screening_run_metadata.json",
    "material_price_discontinuity_flags.csv",
    "manual_verification_template.csv",
    "known_official_events_resolved.csv",
    "duplicate_symbol_date_report.csv",
)
MANIFEST_NAME = "manifest.csv"


def _csv_payload(frame: pd.DataFrame) -> bytes:
    return format_dates(frame).to_csv(index=False, lineterminator="\n", float_format="%.15g").encode("utf-8")


def _build_evidence(formal_root: Path) -> dict[str, bytes]:
    archive = FormalRunArchive(FORMAL_RUN_ID, root=formal_root)
    if not archive.verify_integrity():
        raise ValueError("Formal archive integrity check failed")
    run = json.loads((archive.path / "run.json").read_text(encoding="utf-8"))
    if run["run_id"] != FORMAL_RUN_ID or run["cutoff_date"] != FORMAL_CUTOFF:
        raise ValueError("Wrong formal run or cutoff")
    symbols = DEFAULT_SYMBOLS
    raw, accepted_files = load_data(archive.path / "frozen_raw", archive.path, symbols)
    prepared = prepare_data(raw, symbols, pd.Timestamp(START_DATE), pd.Timestamp(FORMAL_CUTOFF))
    duplicates = duplicate_report(prepared)
    if not duplicates.empty:
        raise ValueError(f"Frozen data contains {len(duplicates)} duplicate symbol-date rows")
    validate_formal_dataset(prepared, symbols)
    logging.info("Validated formal archive %s: %d symbols, %d rows", FORMAL_RUN_ID, len(symbols), len(prepared))
    metrics = calculate_metrics(prepared)
    cross_check_data_quality(metrics)
    resolved = resolve_known_events(metrics)
    if len(resolved) != len(KNOWN_EVENTS) or resolved["Resolved_Trading_Date"].isna().any():
        raise ValueError("Known-event date resolution failed")
    flagged = combine_flags(metrics, resolved, THRESHOLD_PCT)
    verification = manual_template(flagged)
    consistency = consistency_report(metrics, symbols)
    summary = summary_report(metrics, flagged, symbols, THRESHOLD_PCT)
    statistical = int(flagged["Thirty_Percent_Statistical_Flag"].sum())
    known = int(flagged["Known_Official_Event_Flag"].sum())
    pending = int((verification["Manual_Verification_Status"] != "VERIFIED").sum())
    script = Path(__file__).read_bytes()
    script_hash = hashlib.sha256(script).hexdigest()
    source_manifest = json.loads((archive.path / "integrity_manifest.json").read_text(encoding="utf-8"))
    metadata = {
        "formal_run_id": FORMAL_RUN_ID,
        "formal_cutoff": FORMAL_CUTOFF,
        "formal_git_sha": run["git_state"]["commit"],
        "formal_archive_sha256": source_manifest["aggregate_sha256"],
        "script_name": Path(__file__).name,
        "script_sha256": script_hash,
        "start_date": START_DATE,
        "end_date": FORMAL_CUTOFF,
        "threshold_pct": THRESHOLD_PCT,
        "selected_symbols": symbols,
        "loaded_symbols": sorted(prepared["Symbol"].unique().tolist()),
        "missing_symbols": [],
        "company_count": len(symbols),
        "rows_per_company": EXPECTED_ROWS_PER_COMPANY,
        "rows_screened": len(prepared),
        "duplicate_symbol_date_rows": 0,
        "unique_flagged_stock_dates": len(flagged),
        "statistical_flag_count": statistical,
        "known_event_count": known,
        "pending_review_count": pending,
        "records_removed": 0,
        "records_adjusted": 0,
        "input_provenance": {
            "archive": f"backend/artifacts/evaluations/formal-runs/{FORMAL_RUN_ID}",
            "files": accepted_files,
            "source": "frozen formal raw OHLCV; verified by archive integrity manifest",
            "value_php": "unavailable in frozen formal OHLCV",
            "issue_name": "unavailable in frozen formal OHLCV; configured display names are not source-name evidence",
        },
        "output_files": list(PACKAGE_FILES),
        "screening_policy": "Absolute close change or opening gap >=30%, plus predeclared official dates. All source observations retained unchanged; unknown flags require manual review.",
    }
    log = (
        f"formal_run={FORMAL_RUN_ID}\nformal_cutoff={FORMAL_CUTOFF}\n"
        f"symbols={','.join(symbols)}\nperiod={START_DATE}..{FORMAL_CUTOFF}\n"
        f"threshold_pct={THRESHOLD_PCT:g}\ninput=frozen formal raw OHLCV\n"
        f"rows_screened={len(prepared)}\nduplicates=0\nstatistical_flags={statistical}\n"
        f"known_events={known}\ndocumented_stock_dates={len(flagged)}\n"
        f"pending_reviews={pending}\nrecords_removed=0\nrecords_adjusted=0\nstatus=PASS\n"
    )
    payloads = {
        PACKAGE_FILES[0]: script,
        "ticker_name_consistency_report.csv": _csv_payload(consistency),
        "screening_summary_by_symbol.csv": _csv_payload(summary),
        "screening_run.log": log.encode("utf-8"),
        "screening_run_metadata.json": (json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"),
        "material_price_discontinuity_flags.csv": _csv_payload(flagged),
        "manual_verification_template.csv": _csv_payload(verification),
        "known_official_events_resolved.csv": _csv_payload(resolved),
        "duplicate_symbol_date_report.csv": _csv_payload(duplicates),
    }
    manifest = io.StringIO(newline="")
    writer = csv.writer(manifest, lineterminator="\n")
    writer.writerow(("filename", "sha256", "formal_run_id", "formal_cutoff"))
    for name in PACKAGE_FILES:
        writer.writerow((name, hashlib.sha256(payloads[name]).hexdigest(), FORMAL_RUN_ID, FORMAL_CUTOFF))
    payloads[MANIFEST_NAME] = manifest.getvalue().encode("utf-8")
    logging.info("Screening complete: statistical=%d, known=%d, pending=%d", statistical, known, pending)
    return payloads


def validate_screening_package(directory: Path) -> dict[str, object]:
    directory = Path(directory)
    expected = set(PACKAGE_FILES) | {MANIFEST_NAME}
    actual = {p.name for p in directory.iterdir()}
    if actual != expected or any(not p.is_file() for p in directory.iterdir()):
        raise ValueError(f"Screening package membership mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    metadata = json.loads((directory / "screening_run_metadata.json").read_text(encoding="utf-8"))
    if metadata["formal_run_id"] != FORMAL_RUN_ID or metadata["formal_cutoff"] != FORMAL_CUTOFF or metadata["start_date"] != START_DATE:
        raise ValueError("Screening package formal identity mismatch")
    if metadata["script_sha256"] != hashlib.sha256((directory / PACKAGE_FILES[0]).read_bytes()).hexdigest() or (directory / PACKAGE_FILES[0]).read_bytes() != Path(__file__).read_bytes():
        raise ValueError("Screening script copy/hash mismatch")
    with (directory / MANIFEST_NAME).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(PACKAGE_FILES) or [row["filename"] for row in rows] != list(PACKAGE_FILES):
        raise ValueError("Screening manifest membership mismatch")
    for row in rows:
        if row["formal_run_id"] != FORMAL_RUN_ID or row["formal_cutoff"] != FORMAL_CUTOFF or row["sha256"] != hashlib.sha256((directory / row["filename"]).read_bytes()).hexdigest():
            raise ValueError(f"Screening manifest corruption: {row['filename']}")
    summary = pd.read_csv(directory / "screening_summary_by_symbol.csv")
    flags = pd.read_csv(directory / "material_price_discontinuity_flags.csv")
    manual = pd.read_csv(directory / "manual_verification_template.csv")
    duplicates = pd.read_csv(directory / "duplicate_symbol_date_report.csv")
    if set(summary["Symbol"]) != set(DEFAULT_SYMBOLS) or len(summary) != 15 or int(summary["Records_Screened"].sum()) != 24525:
        raise ValueError("Screening summary coverage mismatch")
    if any(summary["Records_Screened"] != EXPECTED_ROWS_PER_COMPANY) or int(summary["Total_Unique_Flagged_Dates"].sum()) != len(flags):
        raise ValueError("Screening summary counts mismatch")
    if len(duplicates) != 0 or len(flags) != len(manual) or flags.duplicated(["Symbol", "Date"]).any():
        raise ValueError("Screening duplicate/manual alignment mismatch")
    if metadata["rows_screened"] != 24525 or metadata["unique_flagged_stock_dates"] != len(flags) or metadata["statistical_flag_count"] != int(flags["Thirty_Percent_Statistical_Flag"].sum()) or metadata["known_event_count"] != int(flags["Known_Official_Event_Flag"].sum()) or metadata["pending_review_count"] != int((manual["Manual_Verification_Status"] != "VERIFIED").sum()):
        raise ValueError("Screening metadata total mismatch")
    if metadata["records_removed"] != 0 or metadata["records_adjusted"] != 0:
        raise ValueError("Screening package claims changed source records")
    return metadata


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging()
    try:
        payloads = _build_evidence(args.formal_root)
        output = args.output_dir
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            validate_screening_package(output)
            if {name: (output / name).read_bytes() for name in payloads} != payloads:
                raise ValueError("Existing screening package differs; refusing overwrite")
            logging.info("Existing screening package is byte-identical; no changes")
            return 0
        with tempfile.TemporaryDirectory(prefix=".screening-", dir=output.parent) as temp:
            staging = Path(temp) / output.name
            staging.mkdir()
            for name, payload in payloads.items():
                (staging / name).write_bytes(payload)
            validate_screening_package(staging)
            staging.rename(output)
        logging.info("Published %d verified screening files", len(payloads))
        return 0
    except Exception as exc:
        logging.exception("Screening failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
