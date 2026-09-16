"""Build verified post-formal chart history without changing formal evidence."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import json
import logging
import math
from pathlib import Path
from typing import Final

from config.ledger_config import DEFAULT_FORECAST_LEDGER_PATH
from config.model_config import ModelId
from config.settings import BACKEND_ROOT, SETTINGS
from src.data.calendar import PSETradingCalendar
from src.data.validator import OhlcvRecord, require_chronological_records
from src.inference.next_day import predict_next_day_with_artifacts
from src.inference.predictor import load_production_model
from src.ledger.materializer import LedgerSnapshot, ProspectiveForecastRecord
from src.ledger.store import ForecastLedger
from src.training.production_refit import PRINCIPAL_MODELS


LOGGER = logging.getLogger(__name__)
PROSPECTIVE_SOURCE: Final[str] = "prospective"
POST_FORMAL_BACKFILL_SOURCE: Final[str] = "post_formal_backfill"
POST_FORMAL_BACKFILL_SCHEMA_ID: Final[str] = "forecastph.post-formal-backfill"
POST_FORMAL_BACKFILL_SCHEMA_VERSION: Final[int] = 1
DEFAULT_POST_FORMAL_BACKFILL_PATH: Final[Path] = (
    BACKEND_ROOT / "data" / "post_formal_history" / "2026-09-14.json"
)
REQUIRED_PRODUCTION_MODELS: Final[tuple[ModelId, ...]] = (
    ModelId.LAG_REGRESSION,
    ModelId.ARIMA,
    ModelId.LSTM,
)
DISPLAY_HISTORY_MODELS: Final[tuple[ModelId, ...]] = (
    *REQUIRED_PRODUCTION_MODELS,
    ModelId.NAIVE,
)


class ProductionHistoryError(ValueError):
    """Raised when post-formal evidence is ambiguous or inconsistent."""


@dataclass(frozen=True, slots=True)
class ProductionModelEvidence:
    method: ModelId
    prediction: float
    error: float
    model_version: str
    production_run_id: str | None = None
    source_commit: str | None = None
    forecast_id: str | None = None
    created_at: str | None = None
    observed_at: str | None = None
    artifact_sha256: str | None = None
    artifact_created_at: str | None = None
    artifact_trained_through: date | None = None


@dataclass(frozen=True, slots=True)
class ProductionHistoryPoint:
    symbol: str
    origin_date: date
    target_date: date
    actual_close: float
    models: tuple[ProductionModelEvidence, ...]
    source: str = PROSPECTIVE_SOURCE

    def evidence_for(self, model: ModelId) -> ProductionModelEvidence:
        matches = tuple(item for item in self.models if item.method is model)
        if len(matches) != 1:
            raise ProductionHistoryError(
                f"Expected one {model.value} record for {self.symbol}/{self.target_date}"
            )
        return matches[0]


def _validated_ledger_evidence(
    record: ProspectiveForecastRecord,
) -> ProductionModelEvidence:
    outcome = record.outcome
    if outcome is None:
        raise ProductionHistoryError("Pending records cannot become realized history")
    issuance = record.issuance
    outcome.validate_against(issuance)
    expected_error = issuance.prediction - outcome.actual_close
    if not math.isclose(
        outcome.error,
        expected_error,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ProductionHistoryError(
            f"Ledger error is inconsistent forecast_id={issuance.forecast_id}"
        )
    if issuance.created_at >= outcome.observed_at:
        raise ProductionHistoryError(
            f"Outcome must follow issuance forecast_id={issuance.forecast_id}"
        )
    return ProductionModelEvidence(
        forecast_id=issuance.forecast_id,
        method=issuance.method,
        prediction=float(issuance.prediction),
        error=float(outcome.error),
        model_version=issuance.model_version,
        production_run_id=issuance.production_run_id,
        source_commit=issuance.source_commit,
        created_at=issuance.created_at.isoformat(),
        observed_at=outcome.observed_at.isoformat(),
    )


def select_resolved_production_history(
    snapshot: LedgerSnapshot,
    *,
    formal_cutoffs: Mapping[str, date],
) -> dict[str, tuple[ProductionHistoryPoint, ...]]:
    """Select complete post-cutoff model records from the append-only ledger."""

    grouped: dict[
        tuple[str, date], dict[ModelId, ProspectiveForecastRecord]
    ] = defaultdict(dict)
    resolved_after_cutoff = 0
    for record in snapshot.resolved:
        issuance = record.issuance
        cutoff = formal_cutoffs.get(issuance.symbol)
        if cutoff is None or issuance.target_date <= cutoff:
            continue
        if issuance.method not in DISPLAY_HISTORY_MODELS:
            continue
        resolved_after_cutoff += 1
        key = (issuance.symbol, issuance.target_date)
        if issuance.method in grouped[key]:
            raise ProductionHistoryError(
                "Duplicate production method for "
                f"{issuance.symbol}/{issuance.target_date}/{issuance.method.value}"
            )
        grouped[key][issuance.method] = record

    LOGGER.info(
        "Selected resolved prospective ledger records records=%d dates=%d",
        resolved_after_cutoff,
        len(grouped),
    )
    selected: dict[str, list[ProductionHistoryPoint]] = defaultdict(list)
    required = set(DISPLAY_HISTORY_MODELS)
    for (symbol, target_date), by_model in sorted(grouped.items()):
        if set(by_model) != required:
            LOGGER.info(
                "Skipped incomplete production date symbol=%s target_date=%s models=%s",
                symbol,
                target_date,
                sorted(model.value for model in by_model),
            )
            continue
        records = tuple(by_model[model] for model in DISPLAY_HISTORY_MODELS)
        actual_values = {record.outcome.actual_close for record in records if record.outcome}
        origin_dates = {record.issuance.origin_date for record in records}
        if len(actual_values) != 1:
            raise ProductionHistoryError(
                f"Production actual Close differs across methods for {symbol}/{target_date}"
            )
        if len(origin_dates) != 1:
            raise ProductionHistoryError(
                f"Production origin date differs across methods for {symbol}/{target_date}"
            )
        evidence = tuple(_validated_ledger_evidence(record) for record in records)
        selected[symbol].append(
            ProductionHistoryPoint(
                symbol=symbol,
                origin_date=next(iter(origin_dates)),
                target_date=target_date,
                actual_close=float(next(iter(actual_values))),
                models=evidence,
            )
        )

    result = {symbol: tuple(points) for symbol, points in sorted(selected.items())}
    LOGGER.info(
        "Prepared prospective history for frontend symbols=%d dates=%d",
        len(result),
        sum(len(points) for points in result.values()),
    )
    return result


def load_resolved_production_history(
    *,
    formal_cutoffs: Mapping[str, date],
    ledger_path: Path = DEFAULT_FORECAST_LEDGER_PATH,
) -> dict[str, tuple[ProductionHistoryPoint, ...]]:
    """Load and materialize the append-only ledger through its authoritative API."""

    ledger = ForecastLedger(ledger_path)
    snapshot = ledger.read()
    LOGGER.info(
        "Loaded prospective forecast ledger records=%d pending=%d resolved=%d path=%s",
        len(snapshot.records),
        len(snapshot.pending),
        len(snapshot.resolved),
        ledger.path,
    )
    return select_resolved_production_history(
        snapshot,
        formal_cutoffs=formal_cutoffs,
    )


def reconstruct_post_formal_backfill(
    *,
    symbol: str,
    records: Sequence[OhlcvRecord],
    formal_cutoff: date,
    target_date: date,
    calendar: PSETradingCalendar,
    artifacts_root: Path = SETTINGS.artifacts_dir,
) -> ProductionHistoryPoint:
    """Recreate one bridge forecast using only cutoff history and saved model state."""

    all_records = tuple(records)
    require_chronological_records(all_records)
    cutoff_history = tuple(
        record for record in all_records if record.trading_date <= formal_cutoff
    )
    if not cutoff_history or cutoff_history[-1].trading_date != formal_cutoff:
        raise ProductionHistoryError(
            f"Formal cutoff is absent from raw history for {symbol}: {formal_cutoff}"
        )
    actual_matches = tuple(
        record for record in all_records if record.trading_date == target_date
    )
    if len(actual_matches) != 1:
        raise ProductionHistoryError(
            f"Expected one validated target observation for {symbol}/{target_date}"
        )
    artifacts = tuple(
        load_production_model(symbol, model, artifacts_root=artifacts_root)
        for model in PRINCIPAL_MODELS
    )
    for artifact in artifacts:
        metadata = artifact.metadata
        if (
            metadata.trained_through != formal_cutoff
            or metadata.data_row_count != len(cutoff_history)
        ):
            raise ProductionHistoryError(
                "Backfill artifact does not match the frozen cutoff "
                f"symbol={symbol} model={artifact.model_family.value}"
            )
    forecast = predict_next_day_with_artifacts(
        symbol,
        cutoff_history,
        artifacts,
        calendar=calendar,
    )
    if forecast.origin_date != formal_cutoff or forecast.forecast_for != target_date:
        raise ProductionHistoryError(
            f"Backfill chronology is invalid for {symbol}/{target_date}"
        )
    actual_close = float(actual_matches[0].close)
    artifact_by_model = {artifact.model_family: artifact for artifact in artifacts}
    prediction_by_model = {
        prediction.model: prediction for prediction in forecast.predictions
    }
    evidence = tuple(
        ProductionModelEvidence(
            method=model,
            prediction=float(prediction_by_model[model].predicted_close),
            error=float(prediction_by_model[model].predicted_close - actual_close),
            model_version=(
                f"{artifact_by_model[model].metadata.implementation_version}:"
                f"{artifact_by_model[model].metadata.artifact_sha256}"
            ),
            artifact_sha256=artifact_by_model[model].metadata.artifact_sha256,
            artifact_created_at=artifact_by_model[model].metadata.created_at.isoformat(),
            artifact_trained_through=artifact_by_model[model].metadata.trained_through,
        )
        for model in PRINCIPAL_MODELS
    )
    naive_prediction = float(cutoff_history[-1].close)
    evidence += (
        ProductionModelEvidence(
            method=ModelId.NAIVE,
            prediction=naive_prediction,
            error=naive_prediction - actual_close,
            model_version="naive-origin-close-v1",
            artifact_trained_through=formal_cutoff,
        ),
    )
    LOGGER.info(
        "Reconstructed post-formal bridge symbol=%s origin=%s target=%s models=%d",
        symbol,
        formal_cutoff,
        target_date,
        len(evidence),
    )
    return ProductionHistoryPoint(
        symbol=symbol,
        origin_date=formal_cutoff,
        target_date=target_date,
        actual_close=actual_close,
        models=evidence,
        source=POST_FORMAL_BACKFILL_SOURCE,
    )


def build_post_formal_backfill_document(
    points: Sequence[ProductionHistoryPoint],
    *,
    reconstructed_at: datetime,
) -> dict[str, object]:
    """Serialize immutable backfill evidence separately from the prospective ledger."""

    if reconstructed_at.tzinfo is None or reconstructed_at.utcoffset() is None:
        raise ProductionHistoryError("Backfill reconstruction timestamp must be aware")
    records: list[dict[str, object]] = []
    for point in sorted(points, key=lambda item: (item.target_date, item.symbol)):
        if point.source != POST_FORMAL_BACKFILL_SOURCE:
            raise ProductionHistoryError("Backfill document contains a non-backfill point")
        principal_evidence = tuple(
            point.evidence_for(model) for model in REQUIRED_PRODUCTION_MODELS
        )
        created_values = {item.artifact_created_at for item in principal_evidence}
        boundary_values = {item.artifact_trained_through for item in principal_evidence}
        implementation_versions = {
            item.model_version.split(":", maxsplit=1)[0] for item in principal_evidence
        }
        if (
            len(created_values) != 1
            or None in created_values
            or len(boundary_values) != 1
            or None in boundary_values
            or len(implementation_versions) != 1
        ):
            raise ProductionHistoryError("Backfill artifact provenance is inconsistent")
        records.append(
            {
                "symbol": point.symbol,
                "origin_date": point.origin_date.isoformat(),
                "target_date": point.target_date.isoformat(),
                "actual_close": point.actual_close,
                "predictions": {
                    evidence.method.value: evidence.prediction
                    for evidence in point.models
                },
                "model_implementation_version": next(iter(implementation_versions)),
                "artifact_sha256": {
                    evidence.method.value: evidence.artifact_sha256
                    for evidence in point.models
                    if evidence.method in REQUIRED_PRODUCTION_MODELS
                },
                "artifact_created_at": next(iter(created_values)),
                "artifact_trained_through": next(iter(boundary_values)).isoformat(),
            }
        )
    return {
        "schema_id": POST_FORMAL_BACKFILL_SCHEMA_ID,
        "schema_version": POST_FORMAL_BACKFILL_SCHEMA_VERSION,
        "source": POST_FORMAL_BACKFILL_SOURCE,
        "reconstructed_at": reconstructed_at.isoformat(),
        "records": records,
    }


def load_post_formal_backfill(
    *,
    formal_cutoffs: Mapping[str, date],
    records_by_symbol: Mapping[str, Sequence[OhlcvRecord]],
    path: Path = DEFAULT_POST_FORMAL_BACKFILL_PATH,
) -> dict[str, tuple[ProductionHistoryPoint, ...]]:
    """Load frozen bridge evidence and verify it against the current raw actuals."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionHistoryError(f"Cannot read post-formal backfill: {path}") from exc
    if not isinstance(payload, dict) or (
        payload.get("schema_id") != POST_FORMAL_BACKFILL_SCHEMA_ID
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != POST_FORMAL_BACKFILL_SCHEMA_VERSION
        or payload.get("source") != POST_FORMAL_BACKFILL_SOURCE
    ):
        raise ProductionHistoryError("Post-formal backfill identity is incompatible")
    try:
        reconstructed_at = datetime.fromisoformat(payload["reconstructed_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProductionHistoryError("Backfill reconstruction timestamp is invalid") from exc
    if reconstructed_at.tzinfo is None or reconstructed_at.utcoffset() is None:
        raise ProductionHistoryError("Backfill reconstruction timestamp must be aware")
    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        raise ProductionHistoryError("Backfill records must be an array")

    selected: dict[str, list[ProductionHistoryPoint]] = defaultdict(list)
    seen: set[tuple[str, date]] = set()
    for raw_point in raw_records:
        if not isinstance(raw_point, dict):
            raise ProductionHistoryError("Backfill point must be an object")
        try:
            symbol = str(raw_point["symbol"])
            origin_date = date.fromisoformat(raw_point["origin_date"])
            target_date = date.fromisoformat(raw_point["target_date"])
            actual_close = float(raw_point["actual_close"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProductionHistoryError("Backfill point fields are invalid") from exc
        cutoff = formal_cutoffs.get(symbol)
        if cutoff is None or origin_date != cutoff or target_date <= cutoff:
            raise ProductionHistoryError(
                f"Backfill point does not follow the formal cutoff for {symbol}"
            )
        if PSETradingCalendar().next_trading_day(cutoff) != target_date:
            raise ProductionHistoryError(
                f"Backfill target is not the next configured PSE session for {symbol}"
            )
        key = (symbol, target_date)
        if key in seen:
            raise ProductionHistoryError(f"Duplicate backfill point for {symbol}/{target_date}")
        seen.add(key)
        history = tuple(records_by_symbol.get(symbol, ()))
        require_chronological_records(history)
        actual_matches = tuple(
            record for record in history if record.trading_date == target_date
        )
        if len(actual_matches) != 1 or not math.isclose(
            actual_close,
            actual_matches[0].close,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ProductionHistoryError(
                f"Backfill actual does not match raw data for {symbol}/{target_date}"
            )
        if not math.isfinite(actual_close):
            raise ProductionHistoryError("Backfill actual Close must be finite")
        predictions = raw_point.get("predictions")
        implementation_version = raw_point.get("model_implementation_version")
        artifact_hashes = raw_point.get("artifact_sha256")
        artifact_created = raw_point.get("artifact_created_at")
        artifact_boundaries = raw_point.get("artifact_trained_through")
        if not isinstance(predictions, dict) or not isinstance(artifact_hashes, dict):
            raise ProductionHistoryError("Backfill model provenance must use mappings")
        if set(predictions) != {model.value for model in DISPLAY_HISTORY_MODELS}:
            raise ProductionHistoryError(
                f"Backfill model coverage is incomplete for {symbol}/{target_date}"
            )
        principal_keys = {model.value for model in REQUIRED_PRODUCTION_MODELS}
        if (
            set(artifact_hashes) != principal_keys
            or not isinstance(implementation_version, str)
            or not implementation_version
            or not isinstance(artifact_created, str)
            or not isinstance(artifact_boundaries, str)
        ):
            raise ProductionHistoryError("Backfill artifact provenance is incomplete")
        try:
            parsed_created_at = datetime.fromisoformat(artifact_created)
            trained_through = date.fromisoformat(artifact_boundaries)
        except ValueError as exc:
            raise ProductionHistoryError("Backfill artifact timestamps are invalid") from exc
        if (
            parsed_created_at.tzinfo is None
            or parsed_created_at.utcoffset() is None
            or trained_through != cutoff
        ):
            raise ProductionHistoryError("Backfill artifact provenance is inconsistent")
        evidence: list[ProductionModelEvidence] = []
        for method in DISPLAY_HISTORY_MODELS:
            try:
                prediction = float(predictions[method.value])
            except (KeyError, TypeError, ValueError) as exc:
                raise ProductionHistoryError("Backfill model evidence is invalid") from exc
            if not math.isfinite(prediction):
                raise ProductionHistoryError("Backfill predictions must be finite")
            error = prediction - actual_close
            sha: str | None = None
            artifact_created_at: str | None = None
            model_version = "naive-origin-close-v1"
            if method in REQUIRED_PRODUCTION_MODELS:
                sha = artifact_hashes.get(method.value)
                artifact_created_at = artifact_created
                if (
                    not isinstance(sha, str)
                    or len(sha) != 64
                    or any(character not in "0123456789abcdef" for character in sha)
                ):
                    raise ProductionHistoryError("Backfill artifact provenance is invalid")
                model_version = f"{implementation_version}:{sha}"
            elif method is ModelId.NAIVE:
                origin_matches = tuple(
                    record for record in history if record.trading_date == cutoff
                )
                if len(origin_matches) != 1 or prediction != origin_matches[0].close:
                    raise ProductionHistoryError("Naive backfill is not the origin Close")
            evidence.append(
                ProductionModelEvidence(
                    method=method,
                    prediction=prediction,
                    error=error,
                    model_version=model_version,
                    artifact_sha256=sha,
                    artifact_created_at=artifact_created_at,
                    artifact_trained_through=trained_through,
                )
            )
        selected[symbol].append(
            ProductionHistoryPoint(
                symbol=symbol,
                origin_date=origin_date,
                target_date=target_date,
                actual_close=actual_close,
                models=tuple(evidence),
                source=POST_FORMAL_BACKFILL_SOURCE,
            )
        )
    result = {
        symbol: tuple(sorted(points, key=lambda point: point.target_date))
        for symbol, points in sorted(selected.items())
    }
    if set(result) != set(formal_cutoffs):
        missing = sorted(set(formal_cutoffs) - set(result))
        extra = sorted(set(result) - set(formal_cutoffs))
        raise ProductionHistoryError(
            f"Backfill company coverage mismatch; missing={missing} extra={extra}"
        )
    LOGGER.info(
        "Loaded post-formal backfill symbols=%d dates=%d path=%s",
        len(result),
        sum(len(points) for points in result.values()),
        path,
    )
    return result


def combine_post_formal_history(
    *histories: Mapping[str, Sequence[ProductionHistoryPoint]],
) -> dict[str, tuple[ProductionHistoryPoint, ...]]:
    """Merge bridge and prospective points with unique chronological dates."""

    combined: dict[str, list[ProductionHistoryPoint]] = defaultdict(list)
    for history in histories:
        for symbol, points in history.items():
            combined[symbol].extend(points)
    result: dict[str, tuple[ProductionHistoryPoint, ...]] = {}
    for symbol, points in sorted(combined.items()):
        ordered = tuple(sorted(points, key=lambda point: point.target_date))
        dates = tuple(point.target_date for point in ordered)
        if len(dates) != len(set(dates)):
            raise ProductionHistoryError(
                f"Duplicate post-formal target date while combining history for {symbol}"
            )
        if any(point.symbol != symbol for point in ordered):
            raise ProductionHistoryError("Post-formal history symbol mismatch")
        result[symbol] = ordered
    return result
