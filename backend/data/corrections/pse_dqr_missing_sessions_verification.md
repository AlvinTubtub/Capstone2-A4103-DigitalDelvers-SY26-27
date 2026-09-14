# ForecastPH Missing Trading Session Source Verification

This report records source verification for 30 OHLCV rows that are absent from the ForecastPH raw files. It does not apply the rows to `backend/data/raw`. Values were extracted only from the official Philippine Stock Exchange Daily Quotation Reports and then checked independently by visually re-reading each source row.

## Sources

- Date: 2022-12-29
  - Official URL: https://www.pse.com.ph/wp-content/uploads/sites/15/2022/12/December-29-2022.pdf
  - Filename: `December-29-2022.pdf`
  - SHA-256: `1401a65c53c0bfcc21c82e224296c6fe1e799d4b05d5a6443894b4eee0bc7068`
  - File size: 391,450 bytes
- Date: 2024-05-29
  - Official URL: https://documents.pse.com.ph/wp-content/uploads/sites/15/2024/05/May-29-2024-EOD.pdf
  - Filename: `May-29-2024-EOD.pdf`
  - SHA-256: `eca5563a524ace0a2d3ee775f726e3db0c93d36c10654390315b88a226226158`
  - File size: 395,829 bytes

Both downloads begin with a valid PDF signature and were parsed as PDF 1.4 documents. Neither download was an HTML error page.

## 2022-12-29

| Symbol | Open | High | Low | Close | Volume | Verification |
|---|---:|---:|---:|---:|---:|---|
| ALI | 30.1 | 30.8 | 29.95 | 30.8 | 10,155,300 | VERIFIED |
| APX | 1.84 | 1.9 | 1.83 | 1.85 | 5,265,000 | VERIFIED |
| BPI | 98.8 | 102 | 98.6 | 102 | 775,120 | VERIFIED |
| GLO | 2,220 | 2,234 | 2,180 | 2,180 | 21,460 | VERIFIED |
| ICT | 198.2 | 204.4 | 196.7 | 200 | 1,111,840 | VERIFIED |
| JFC | 232 | 232 | 229.4 | 230 | 500,210 | VERIFIED |
| MBT | 54.7 | 54.85 | 54 | 54 | 1,146,450 | VERIFIED |
| MEG | 2.13 | 2.15 | 2 | 2 | 20,638,000 | VERIFIED |
| MER | 294.8 | 298.8 | 291.6 | 298.8 | 179,630 | VERIFIED |
| NIKL | 5.7 | 5.85 | 5.7 | 5.84 | 10,299,700 | VERIFIED |
| PGOLD | 34.8 | 35 | 34.55 | 34.9 | 2,484,200 | VERIFIED |
| SCC | 34.75 | 34.95 | 34 | 34.5 | 3,928,500 | VERIFIED |
| SECB | 88.6 | 88.6 | 87 | 87 | 225,610 | VERIFIED |
| SHLPH | 16.72 | 16.9 | 16.72 | 16.9 | 31,600 | VERIFIED |
| SMPH | 34.9 | 35.5 | 34.65 | 35.5 | 37,985,700 | VERIFIED |

## 2024-05-29

| Symbol | Open | High | Low | Close | Volume | Verification |
|---|---:|---:|---:|---:|---:|---|
| ALI | 27.2 | 27.3 | 26.8 | 26.8 | 12,344,700 | VERIFIED |
| APX | 3.96 | 4.03 | 3.88 | 3.94 | 2,820,000 | VERIFIED |
| BPI | 124.9 | 125 | 120 | 120.8 | 3,496,450 | VERIFIED |
| GLO | 1,973 | 1,975 | 1,930 | 1,954 | 68,680 | VERIFIED |
| ICT | 334 | 336 | 327 | 329.6 | 1,985,430 | VERIFIED |
| JFC | 221 | 224.4 | 220.6 | 221 | 295,140 | VERIFIED |
| MBT | 68.2 | 68.95 | 67 | 67 | 2,583,980 | VERIFIED |
| MEG | 1.9 | 1.9 | 1.84 | 1.85 | 15,306,000 | VERIFIED |
| MER | 366 | 370 | 366 | 369.2 | 179,900 | VERIFIED |
| NIKL | 4.12 | 4.12 | 4.04 | 4.1 | 7,537,000 | VERIFIED |
| PGOLD | 24 | 24 | 23.45 | 23.75 | 369,100 | VERIFIED |
| SCC | 32.9 | 33.05 | 32.7 | 32.9 | 587,300 | VERIFIED |
| SECB | 69 | 69.15 | 68.8 | 69 | 334,750 | VERIFIED |
| SHLPH | 10.66 | 10.66 | 10.46 | 10.46 | 338,100 | VERIFIED |
| SMPH | 27.2 | 27.4 | 26.55 | 26.55 | 14,899,600 | VERIFIED |

## Validation summary

- Expected rows: 30
- Extracted rows: 30
- Verified rows: 30
- Review-required rows: 0
- Missing symbols: none
- Duplicate symbol/date records: 0
- OHLC consistency failures: 0

The independent source check re-read the rendered quotation-table row for each company. It confirmed the row's issue name and exact common-stock symbol before comparing Open, High, Low, Close, and Volume. Bid, Ask, Previous Close, Value, and Net Foreign Buying or Selling were not used. Preferred shares and later report sections containing repeated ticker text were excluded.

## Source correction conclusion

READY FOR CONTROLLED RAW-DATA CORRECTION
