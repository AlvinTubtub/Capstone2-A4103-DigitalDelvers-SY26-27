# ForecastPH Historical Raw-Data Provenance Recovery

## Evidence searched

The review covered the current formal provenance schema, the root commit that introduced all 15 raw CSVs and the PSE ingestion implementation, the tracked aligned manuscript, the historical research documentation, narrow Git searches for alternative providers, and the researcher-supplied original downloader, batch log, and Google Drive metadata.

Relevant evidence:

- `docs/research-history/formal-study/FORMAL_CORRECTED_20260828_02/ForecastPH_Capstone_Aligned_Formal_Run_02.docx` states that the primary source was the official PSE Daily Quotations Report; that reports were obtained as PDFs from the official PSE document repository; and that the 15 ticker CSVs were created from those reports. Appendix I names `PSE_PDF_Downloader.py`, the archived January 2020 through June 2026 reports, and `official_final_extract_2020_2026_pse_stocks.py`.
- Root commit `9f6539464a2144fbbfe4c64c68a13e5b178d48e3` introduced all 15 raw CSVs together. Its PSE downloader identifies `https://documents.pse.com.ph/market_report` as the provider endpoint and states that it preserved the behavior of the standalone historical downloader. The commit contains no download log or reliable retrieval timestamp for the original historical archive.
- No repository or Git-history match was found for `yfinance`, `yf.download`, Yahoo Finance, `Ticker.history`, or Yahoo query endpoints.
- The researcher-supplied `PSE_PDF_Downloader.py` configures the historical range from 2020-01-01 through 2026-06-30, downloads official PSE DQR PDFs, and overwrites `pse_download_log.txt` when the batch completes. The retained log confirms successful report downloads through 2026-06-30.
- Google Drive metadata for the original `pse_download_log.txt` records a modification date of 2026-07-17 and a later Drive creation date of 2026-07-22. The modification date is retained as batch-log metadata evidence; the later Drive date reflects subsequent storage and is not used as the retrieval date.
- Commit `2928a1aaa45c756fbd577ad08a2b167efb66855d` separately records the two verified PSE DQR corrections applied to every symbol.

## Original source determination

Source name: Philippine Stock Exchange Daily Quotation Reports

Status: PROVEN

Evidence: The tracked aligned manuscript directly identifies the primary OHLCV source and describes the completed PDF download and ticker-level extraction process. This is consistent with the PSE downloader and raw-data pipeline introduced alongside all 15 CSVs in the root commit.

## Source reference determination

Source reference: https://documents.pse.com.ph/market_report

Status: PROVEN as a provider-level reference

Evidence: The root commit's PSE downloader declares this exact official document-repository endpoint and says its URL behavior was preserved from the standalone downloader. The reference is not an archived URL for every historical report and must not be represented as one.

## Retrieval date determination

Retrieval date: 2026-07-17

Status: RECOVERED — PRESERVED BATCH-LOG METADATA EVIDENCE

Evidence:

1. `PSE_PDF_Downloader.py` downloads official PSE DQR PDFs and overwrites `pse_download_log.txt` when the batch completes.
2. The retained `pse_download_log.txt` confirms successful downloads through 2026-06-30.
3. Google Drive metadata for the original log records `Modified: July 17, 2026`.
4. Its later `Created in Drive: July 22, 2026` date represents subsequent Drive storage or upload and was not used.
5. The raw CSV Git introduction date of 2026-08-12 was not used as the retrieval date.

The date 2026-07-17 is preserved batch-log metadata evidence. It is not described as a timestamp supplied by the PSE server.

## Per-symbol applicability

All 15 raw CSVs were introduced together, contain the common study period and schema, and are described by the same historical download and extraction process. The same source name, provider-level reference, and batch retrieval date therefore apply to ALI, APX, BPI, GLO, ICT, JFC, MBT, MEG, MER, NIKL, PGOLD, SCC, SECB, SHLPH, and SMPH. No artificial symbol-specific retrieval event is asserted.

The original downloader's historical report range ends on 2026-06-30. The final raw dataset later extends through 2026-09-11 through subsequent ingestion and separately documented corrections. The July 2026 historical batch is not claimed to have downloaded reports after 2026-06-30.

## PSE DQR corrections

The separately verified records for 2022-12-29 and 2024-05-29 remain documented in `backend/data/corrections/`. Two correction-history entries were added for each symbol using the official report URL already preserved by that evidence. These corrections do not redefine or independently prove the source of the remaining historical rows.

## Remaining formal-readiness provenance blocker

The three required formal provenance fields are now populated for all 15 symbols. The retrieval date is based specifically on preserved batch-log modification metadata supplied by the researcher, not the Git introduction date, current date, last observation date, or PSE server metadata.
