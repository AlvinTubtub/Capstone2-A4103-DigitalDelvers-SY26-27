from __future__ import annotations

import builtins
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from config.companies import COMPANIES
from scripts import update_eod
from src.ingestion.cleaner import NumericCleaningError, clean_number, clean_quotation
from src.ingestion.config import IngestionSettings
from src.ingestion.downloader import (
    DownloadResult,
    FetchResponse,
    download_one,
    download_reports,
    report_filename,
    report_url,
)
from src.ingestion.merger import RawMergeError, merge_symbol, validate_raw_file
from src.ingestion.parser import (
    ParseBatchResult,
    PdfParseError,
    parse_pdf,
    parse_quotation_line,
)
from src.ingestion.pipeline import resolve_date_range, run_ingestion


def _settings(tmp_path: Path, *, retries: int = 3) -> IngestionSettings:
    return IngestionSettings(
        reports_dir=tmp_path / "pdf_reports",
        raw_dir=tmp_path / "raw",
        request_timeout_seconds=1,
        max_retries=retries,
        backoff_base_seconds=2,
    )


def _quote(day: date, *, close: str = "101.00", symbol: str = "BPI"):
    return clean_quotation(
        report_date=day,
        issue_name=next(company.pse_issue_name for company in COMPANIES if company.symbol == symbol),
        symbol=symbol,
        open_value="100.00",
        high_value="103.00",
        low_value="99.00",
        close_value=close,
        volume_value="123,000",
        traded_value="12,345,000",
    )


def _write_raw(path: Path, *, close: str = "101.0") -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "Date,Open,High,Low,Close,Volume\n"
        f"2026-09-10,100.0,103.0,99.0,{close},123000.0\n"
    ).encode()
    path.write_bytes(content)
    return content


def test_url_generation_matches_pse_edge_contract() -> None:
    assert report_url(date(2026, 9, 7)) == (
        "https://documents.pse.com.ph/market_report/September%2007,%202026-EOD.pdf"
    )


def test_pdf_filename_generation() -> None:
    assert report_filename(date(2026, 9, 7)) == "2026-09-07-EOD.pdf"


def test_transient_failure_retries_then_downloads(tmp_path: Path, readable_pdf) -> None:
    responses: list[object] = [URLError("temporary outage"), FetchResponse(200, b"%PDF-September 7, 2026")]
    waits: list[float] = []

    def fetcher(_url: str, _timeout: float) -> FetchResponse:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    status, path, message = download_one(
        date(2026, 9, 7),
        settings=_settings(tmp_path),
        fetcher=fetcher,
        sleep_fn=waits.append,
    )
    assert status == "downloaded"
    assert message is None
    assert path is not None and path.read_bytes() == b"%PDF-September 7, 2026"
    assert waits == [2]


def test_transient_server_error_retries(tmp_path: Path, readable_pdf) -> None:
    responses = [FetchResponse(503, b""), FetchResponse(200, b"%PDF-September 7, 2026")]
    waits: list[float] = []

    status, path, _message = download_one(
        date(2026, 9, 7),
        settings=_settings(tmp_path),
        fetcher=lambda _url, _timeout: responses.pop(0),
        sleep_fn=waits.append,
    )
    assert status == "downloaded"
    assert path is not None
    assert waits == [2]


def test_existing_pdf_is_skipped_without_network_call(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    destination = settings.reports_dir / report_filename(date(2026, 9, 7))
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing")

    def unexpected_fetch(_url: str, _timeout: float) -> FetchResponse:
        pytest.fail("existing report must not be downloaded again")

    status, path, message = download_one(
        date(2026, 9, 7), settings=settings, fetcher=unexpected_fetch
    )
    assert (status, path, message) == ("already_present", destination, None)
    assert destination.read_bytes() == b"existing"


class _Page:
    def __init__(self, text: str | None):
        self.text = text

    def extract_text(self) -> str | None:
        return self.text


class _Pdf:
    def __init__(self, pages: list[_Page]):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


QUOTE_LINES = {
    company.symbol: (
        f"{company.pse_issue_name} {company.symbol} 99 100 100 103 99 101 123,000 12,345,000 1"
    )
    for company in COMPANIES
}


@pytest.fixture
def readable_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    import pdfplumber

    def open_pdf(path: Path) -> _Pdf:
        report_date, separator, quote_text = (
            path.read_bytes().removeprefix(b"%PDF-").decode().partition("\n")
        )
        if not separator:
            quote_text = "\n".join(QUOTE_LINES.values())
        return _Pdf(
            [
                _Page(
                    f"Daily Quotation Report {report_date}\n{quote_text}"
                )
            ]
        )

    monkeypatch.setattr(pdfplumber, "open", open_pdf)


INCIDENT_DATE = date(2026, 11, 13)
INCIDENT_PRIMARY_URL = "https://documents.pse.com.ph/market_report/November%2013,%202026-EOD.pdf"
INCIDENT_ARCHIVE_URL = (
    "https://documents.pse.com.ph/wp-content/uploads/sites/15/2026/11/stockQuotes_11132026.pdf"
)


@pytest.mark.parametrize("primary_status", [200, 404], ids=["primary", "archive"])
def test_ingestion_uses_first_available_source(
    tmp_path: Path, readable_pdf, caplog: pytest.LogCaptureFixture, primary_status: int
) -> None:
    checked = []

    def fetcher(url: str, _timeout: float) -> FetchResponse:
        checked.append(url)
        if url == INCIDENT_PRIMARY_URL and primary_status == 404:
            raise HTTPError(url, 404, "Not Found", None, None)
        return FetchResponse(200, b"%PDF-November 13, 2026")

    with caplog.at_level("INFO"):
        result = run_ingestion(
            start_date=INCIDENT_DATE,
            end_date=INCIDENT_DATE,
            settings=_settings(tmp_path),
            download_function=partial(download_reports, fetcher=fetcher),
        )

    assert result.successful
    assert result.rows_added == len(COMPANIES)
    if primary_status == 200:
        assert checked == [INCIDENT_PRIMARY_URL]
        assert f"source=primary url={INCIDENT_PRIMARY_URL}" in caplog.text
    else:
        assert checked == [INCIDENT_PRIMARY_URL, INCIDENT_ARCHIVE_URL]
        assert f"source=archive url={INCIDENT_ARCHIVE_URL}" in caplog.text


def test_both_sources_404_on_latest_trading_day_is_no_update(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    raw = settings.raw_dir / "BPI.csv"
    original = _write_raw(raw)
    checked = []

    def fetcher(url: str, _timeout: float) -> FetchResponse:
        checked.append(url)
        return FetchResponse(404, b"")

    result = run_ingestion(
        start_date=INCIDENT_DATE,
        end_date=INCIDENT_DATE,
        settings=settings,
        download_function=partial(
            download_reports, fetcher=fetcher, sleep_fn=lambda _: pytest.fail("404 must not retry")
        ),
    )

    assert checked == [INCIDENT_PRIMARY_URL, INCIDENT_ARCHIVE_URL]
    assert result.successful
    assert result.unpublished_dates == [INCIDENT_DATE]
    assert result.validation_status == "not_required_no_published_reports"
    assert raw.read_bytes() == original


def test_invalid_archive_pdf_is_rejected_before_caching(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    result = run_ingestion(
        start_date=INCIDENT_DATE,
        end_date=INCIDENT_DATE,
        settings=settings,
        download_function=partial(
            download_reports,
            fetcher=lambda url, _: (
                FetchResponse(404, b"") if url == INCIDENT_PRIMARY_URL
                else FetchResponse(200, b"<html>Not a PDF</html>")
            ),
        ),
    )

    assert not result.successful
    assert result.validation_status == "failed"
    [(day, message)] = result.failed_downloads
    assert day == INCIDENT_DATE
    assert f"archive ({INCIDENT_ARCHIVE_URL})" in message
    assert "Could not read" in message
    assert not list(settings.reports_dir.iterdir())
    assert not settings.raw_dir.exists()


def test_misdated_archive_is_rejected_before_caching(tmp_path: Path, readable_pdf) -> None:
    settings = _settings(tmp_path)
    status, path, message = download_one(
        INCIDENT_DATE,
        settings=settings,
        fetcher=lambda url, _: (
            FetchResponse(404, b"") if url == INCIDENT_PRIMARY_URL
            else FetchResponse(200, b"%PDF-November 12, 2026")
        ),
    )

    assert (status, path) == ("failed", None)
    assert message is not None
    assert f"archive ({INCIDENT_ARCHIVE_URL})" in message
    assert "Report date 2026-11-12 does not match staged filename date 2026-11-13" in message
    assert not list(settings.reports_dir.iterdir())


def test_missing_earlier_session_blocks_later_raw_updates(
    tmp_path: Path, readable_pdf
) -> None:
    settings = _settings(tmp_path)
    raw = settings.raw_dir / "BPI.csv"
    original = _write_raw(raw)
    later_date = date(2026, 11, 16)
    later_url = report_url(later_date)
    checked = []

    def fetcher(url: str, _timeout: float) -> FetchResponse:
        checked.append(url)
        if url == later_url:
            return FetchResponse(200, b"%PDF-November 16, 2026")
        return FetchResponse(404, b"")

    result = run_ingestion(
        start_date=INCIDENT_DATE,
        end_date=later_date,
        settings=settings,
        download_function=partial(download_reports, fetcher=fetcher),
    )

    assert checked == [INCIDENT_PRIMARY_URL, INCIDENT_ARCHIVE_URL, later_url]
    assert not result.successful
    assert result.validation_status == "failed"
    assert result.rows_added == 0
    [error] = result.errors
    assert "Missing expected PSE trading session 2026-11-13" in error
    assert "before available session 2026-11-16" in error
    assert INCIDENT_PRIMARY_URL in error
    assert INCIDENT_ARCHIVE_URL in error
    assert raw.read_bytes() == original


@pytest.mark.parametrize("cached", [False, True], ids=["downloaded", "cached"])
@pytest.mark.parametrize(
    ("bpi_line", "detail"),
    [
        ("", "missing symbols BPI"),
        ("BANK PH ISLANDS BPI 99 100 - - - - - - -", "no usable quote for BPI"),
        ("BANK PH ISLANDS BPI 99 100 100 103 99 101 0 0 0", "no usable quote for BPI"),
    ],
    ids=["missing-ticker", "missing-close", "zero-volume"],
)
def test_incomplete_report_blocks_entire_batch(
    tmp_path: Path, readable_pdf, cached: bool, bpi_line: str, detail: str
) -> None:
    settings = _settings(tmp_path)
    raw = settings.raw_dir / "BPI.csv"
    original = _write_raw(raw)
    later_date = date(2026, 11, 16)
    quote_lines = {**QUOTE_LINES, "BPI": bpi_line}
    incomplete = "\n".join(["%PDF-November 16, 2026", *quote_lines.values()]).encode()
    incomplete_path = settings.reports_dir / report_filename(later_date)
    if cached:
        incomplete_path.parent.mkdir()
        incomplete_path.write_bytes(incomplete)

    def fetcher(url: str, _timeout: float) -> FetchResponse:
        if url == INCIDENT_PRIMARY_URL:
            return FetchResponse(200, b"%PDF-November 13, 2026")
        assert url == report_url(later_date)
        return FetchResponse(200, incomplete)

    result = run_ingestion(
        start_date=INCIDENT_DATE,
        end_date=later_date,
        settings=settings,
        download_function=partial(download_reports, fetcher=fetcher),
    )

    assert not result.successful
    assert result.validation_status == "failed"
    assert result.rows_added == 0
    details = result.errors if cached else [message for _, message in result.failed_downloads]
    assert any(f"{later_date}: {detail}" in message for message in details)
    assert any("operator review required" in message for message in details)
    assert incomplete_path.exists() is cached
    assert list(settings.raw_dir.iterdir()) == [raw]
    assert raw.read_bytes() == original


def test_trailing_404_does_not_block_available_report_and_skips_closures(
    tmp_path: Path, readable_pdf
) -> None:
    friday = date(2026, 10, 30)
    tuesday = date(2026, 11, 3)
    checked = []

    def fetcher(url: str, _timeout: float) -> FetchResponse:
        checked.append(url)
        if url == report_url(friday):
            return FetchResponse(200, b"%PDF-October 30, 2026")
        return FetchResponse(404, b"")

    result = run_ingestion(
        start_date=friday,
        end_date=tuesday,
        settings=_settings(tmp_path),
        download_function=partial(download_reports, fetcher=fetcher),
    )

    assert checked == [
        report_url(friday),
        report_url(tuesday),
        "https://documents.pse.com.ph/wp-content/uploads/sites/15/2026/11/stockQuotes_11032026.pdf",
    ]
    assert result.successful
    assert result.unpublished_dates == [tuesday]
    assert result.rows_added == len(COMPANIES)


def test_parser_extracts_only_configured_company_rows(tmp_path: Path) -> None:
    path = tmp_path / "2026-09-07-EOD.pdf"
    path.write_bytes(b"placeholder")
    text = "\n".join(
        (
            "END OF DAY QUOTATION REPORT September 7, 2026",
            "BANK PH ISLANDS BPI 99 100 100 103 99 101 123,000 12,345,000 1",
            "UNKNOWN COMPANY XYZ 1 2 1 2 1 2 0 5 10",
        )
    )
    records = parse_pdf(path, pdf_opener=lambda _path: _Pdf([_Page(text)]))
    assert len(records) == 1
    record = records[0]
    assert record.symbol == "BPI"
    assert record.issue_name == "BANK PH ISLANDS"
    assert record.open == Decimal("100")
    assert record.close == Decimal("101")
    assert record.volume == Decimal("123000")
    assert record.value == Decimal("12345000")


def test_parser_quotation_layout_matches_actual_pse_columns() -> None:
    record = parse_quotation_line(
        "BANK PH ISLANDS BPI 99 100 100 103 99 101 123,000 12,345,000 1",
        date(2026, 9, 7),
    )
    assert record is not None
    assert (record.open, record.high, record.low, record.close) == (
        Decimal("100"),
        Decimal("103"),
        Decimal("99"),
        Decimal("101"),
    )
    assert record.volume == Decimal("123000")
    assert record.value == Decimal("12345000")


def test_glo_token_inside_unrelated_issue_name_is_not_a_target_row() -> None:
    assert (
        parse_quotation_line(
            "GLO PREF ANV GLOBA 1,925 1,964 - - - - - - -",
            date(2026, 9, 11),
        )
        is None
    )


def test_genuine_glo_common_stock_row_is_parsed_once_and_correctly() -> None:
    record = parse_quotation_line(
        "GLOBE TELECOM GLO 1,598 1,600 1,620 1,623 1,595 1,600 "
        "31,180 49,938,475 (21,146,560)",
        date(2026, 9, 11),
    )
    assert record is not None
    assert record.symbol == "GLO"
    assert record.issue_name == "GLOBE TELECOM"
    assert record.open == Decimal("1620")
    assert record.high == Decimal("1623")
    assert record.low == Decimal("1595")
    assert record.close == Decimal("1600")
    assert record.volume == Decimal("31180")
    assert record.value == Decimal("49938475")


def test_genuine_target_row_with_malformed_ohlcv_remains_strict() -> None:
    with pytest.raises(PdfParseError, match="Malformed quotation row for GLO"):
        parse_quotation_line(
            "GLOBE TELECOM GLO 1,598 1,600 bad 1,623 1,595 1,600 "
            "31,180 49,938,475 (21,146,560)",
            date(2026, 9, 11),
        )


def test_false_positive_line_cannot_invalidate_full_configured_report(
    tmp_path: Path,
) -> None:
    path = tmp_path / "2026-09-11-EOD.pdf"
    path.write_bytes(b"placeholder")
    quote_lines = [
        f"{company.pse_issue_name} {company.symbol} "
        "99 100 100 103 99 101 123,000 12,345,000 1"
        for company in COMPANIES
    ]
    text = "\n".join(
        [
            "Daily Quotation Report September 11, 2026",
            "GLO PREF ANV GLOBA 1,925 1,964 - - - - - - -",
            *quote_lines,
        ]
    )
    records = parse_pdf(path, pdf_opener=lambda _path: _Pdf([_Page(text)]))
    assert len(records) == len(COMPANIES) == 15
    assert {record.symbol for record in records} == {
        company.symbol for company in COMPANIES
    }
    assert sum(record.symbol == "GLO" for record in records) == 1


def test_numeric_cleaning_is_deterministic_and_strict() -> None:
    assert clean_number(" 1,234.50 ") == Decimal("1234.50")
    assert clean_number("(2,500)") == Decimal("-2500")
    assert clean_number("-") is None
    with pytest.raises(NumericCleaningError, match="Malformed numeric"):
        clean_number("1O0.00")


def test_duplicate_incoming_date_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(RawMergeError, match="Duplicate incoming date"):
        merge_symbol(
            "BPI",
            [_quote(date(2026, 9, 11)), _quote(date(2026, 9, 11))],
            raw_dir=tmp_path / "raw",
        )


def test_idempotent_merge_does_not_rewrite_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "raw" / "BPI.csv"
    original = _write_raw(path)
    summary = merge_symbol(
        "BPI", [_quote(date(2026, 9, 10))], raw_dir=path.parent
    )
    assert summary.rows_added == 0
    assert path.read_bytes() == original


def test_conflicting_historical_row_is_rejected_without_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "raw" / "BPI.csv"
    original = _write_raw(path)
    with pytest.raises(RawMergeError, match="Conflicting historical row"):
        merge_symbol(
            "BPI",
            [_quote(date(2026, 9, 10), close="102.00")],
            raw_dir=path.parent,
        )
    assert path.read_bytes() == original


def test_merge_runs_authoritative_raw_validation(tmp_path: Path) -> None:
    path = tmp_path / "raw" / "BPI.csv"
    _write_raw(path)
    summary = merge_symbol(
        "BPI", [_quote(date(2026, 9, 11))], raw_dir=path.parent
    )
    records = validate_raw_file(summary.path)
    assert [record.trading_date for record in records] == [
        date(2026, 9, 10),
        date(2026, 9, 11),
    ]
    assert summary.rows_added == 1


def test_default_range_starts_after_latest_raw_date(tmp_path: Path) -> None:
    _write_raw(tmp_path / "raw" / "BPI.csv")
    start, end = resolve_date_range(
        raw_dir=tmp_path / "raw",
        start_date=None,
        end_date=None,
        now=datetime.fromisoformat("2026-09-12T00:30:00+08:00"),
    )
    assert start == date(2026, 9, 11)
    assert end == date(2026, 9, 12)


def test_ingestion_has_no_training_or_forecast_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guarded_prefixes = (
        "src.training",
        "src.models",
        "src.evaluation",
        "src.inference",
        "src.export",
    )
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(guarded_prefixes):
            pytest.fail(f"ingestion imported out-of-scope module {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    def all_unpublished(_start, _end, *, settings):
        return DownloadResult(unpublished=[date(2026, 9, 6)])

    result = run_ingestion(
        start_date=date(2026, 9, 6),
        end_date=date(2026, 9, 6),
        settings=_settings(tmp_path),
        download_function=all_unpublished,
    )
    assert result.successful
    assert result.validation_status == "not_required_no_published_reports"
    assert not (tmp_path / "artifacts").exists()


def test_pipeline_validates_raw_after_merge(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = settings.reports_dir / report_filename(date(2026, 9, 11))
    report.parent.mkdir(parents=True)
    report.write_bytes(b"placeholder")

    def downloaded(_start, _end, *, settings):
        return DownloadResult(already_present=[report])

    def parsed(_paths, *, settings):
        return ParseBatchResult(
            records=[_quote(date(2026, 9, 11), symbol=company.symbol) for company in COMPANIES],
            parsed_reports=[report],
        )

    result = run_ingestion(
        start_date=date(2026, 9, 11),
        end_date=date(2026, 9, 11),
        settings=settings,
        download_function=downloaded,
        parse_function=parsed,
    )
    assert result.successful
    assert result.validation_status == "passed"
    assert result.rows_added == len(COMPANIES)
    assert validate_raw_file(settings.raw_dir / "BPI.csv")[-1].trading_date == date(
        2026, 9, 11
    )


def test_cli_summary_and_nonzero_failure_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failure = update_eod.IngestionResult(
        requested_start_date=date(2026, 9, 7),
        requested_end_date=date(2026, 9, 7),
        failed_downloads=[(date(2026, 9, 7), "HTTP 503")],
        validation_status="not_required_no_published_reports",
        errors=["One or more requested reports failed to download"],
    )
    monkeypatch.setattr(update_eod, "run_ingestion", lambda **_kwargs: failure)
    assert update_eod.main(["--start-date", "2026-09-07", "--end-date", "2026-09-07"]) == 1
    output = capsys.readouterr().out
    assert "Requested date range: 2026-09-07 to 2026-09-07" in output
    assert "Failed downloads (1): 2026-09-07: HTTP 503" in output
    assert "Validation status: not_required_no_published_reports" in output
