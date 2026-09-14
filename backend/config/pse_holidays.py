"""
Reviewed PSE/SCCP closure calendar.

Historical formal-study coverage (2020-2025) is based on official PSE and
SCCP annual holiday memoranda, settlement advisories, and exceptional trading
suspension notices. Dates are explicitly enumerated; no closure is inferred
from missing OHLCV observations.

Key annual SCCP sources:
2020: Memo 01-1119 — Proclamation No. 845
2021: Memo 01-0820 / Proclamation No. 986 as amended by Proclamation No. 1107
2022: Memo 04-1221 — Proclamation No. 1236
2023: Memo 02-1122 — amended Proclamation No. 90
2024: Memo 03-1023 — Proclamation No. 368
2025: Memo 01-1124 — Proclamation No. 727

Exceptional PSE/SCCP closures are explicitly included, including:
2020-01-13, 2020-03-17/18, 2020-11-12,
2022-01-04, 2022-09-26,
2024-07-24.

2022-12-29 and 2024-05-29 are verified trading sessions and MUST NOT be
classified as closures.

2026+ remains maintained from current PSE/SCCP notices.
"""

from datetime import date


PSE_CLOSURE_ISO_DATES = (
    # 2020 — 20 verified closures
    "2020-01-13",
    "2020-02-25",
    "2020-03-17",
    "2020-03-18",
    "2020-04-09",
    "2020-04-10",
    "2020-05-01",
    "2020-05-25",
    "2020-06-12",
    "2020-07-31",
    "2020-08-21",
    "2020-08-31",
    "2020-11-02",
    "2020-11-12",
    "2020-11-30",
    "2020-12-08",
    "2020-12-24",
    "2020-12-25",
    "2020-12-30",
    "2020-12-31",

    # 2021 — 13 verified closures
    "2021-01-01",
    "2021-02-12",
    "2021-02-25",
    "2021-04-01",
    "2021-04-02",
    "2021-04-09",
    "2021-05-13",
    "2021-07-20",
    "2021-08-30",
    "2021-11-01",
    "2021-11-30",
    "2021-12-08",
    "2021-12-30",

    # 2022 — 15 verified closures
    # 2022-12-29 is intentionally excluded: verified PSE trading session.
    "2022-01-04",
    "2022-02-01",
    "2022-02-25",
    "2022-04-14",
    "2022-04-15",
    "2022-05-03",
    "2022-05-09",
    "2022-08-29",
    "2022-09-26",
    "2022-10-31",
    "2022-11-01",
    "2022-11-30",
    "2022-12-08",
    "2022-12-26",
    "2022-12-30",

    # 2023 — 18 verified closures
    "2023-01-02",
    "2023-02-24",
    "2023-04-06",
    "2023-04-07",
    "2023-04-10",
    "2023-04-21",
    "2023-05-01",
    "2023-06-12",
    "2023-06-28",
    "2023-08-21",
    "2023-08-28",
    "2023-10-30",
    "2023-11-01",
    "2023-11-02",
    "2023-11-27",
    "2023-12-08",
    "2023-12-25",
    "2023-12-26",

    # 2024 — 17 verified closures
    # 2024-05-29 is intentionally excluded: verified PSE trading session.
    "2024-01-01",
    "2024-02-09",
    "2024-03-28",
    "2024-03-29",
    "2024-04-09",
    "2024-04-10",
    "2024-05-01",
    "2024-06-12",
    "2024-06-17",
    "2024-07-24",
    "2024-08-23",
    "2024-08-26",
    "2024-11-01",
    "2024-12-24",
    "2024-12-25",
    "2024-12-30",
    "2024-12-31",

    # 2025 — 18 verified closures
    "2025-01-01",
    "2025-01-29",
    "2025-04-01",
    "2025-04-09",
    "2025-04-17",
    "2025-04-18",
    "2025-05-01",
    "2025-05-12",
    "2025-06-06",
    "2025-06-12",
    "2025-08-21",
    "2025-08-25",
    "2025-10-31",
    "2025-12-08",
    "2025-12-24",
    "2025-12-25",
    "2025-12-30",
    "2025-12-31",

    # 2026 — reviewed PSE/SCCP closures
    "2026-01-01",
    "2026-02-17",
    "2026-03-20",
    "2026-04-02",
    "2026-04-03",
    "2026-04-04",
    "2026-04-09",
    "2026-05-01",
    "2026-05-27",
    "2026-06-12",
    "2026-08-21",
    "2026-08-31",
    "2026-11-01",
    "2026-11-02",
    "2026-11-30",
    "2026-12-08",
    "2026-12-24",
    "2026-12-25",
    "2026-12-30",
    "2026-12-31",
)


PSE_CLOSURES = frozenset(
    date.fromisoformat(value) for value in PSE_CLOSURE_ISO_DATES
)