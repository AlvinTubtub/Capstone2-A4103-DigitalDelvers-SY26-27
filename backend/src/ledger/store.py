"""Locked append-only JSONL storage for prospective forecast evidence."""

from collections.abc import Sequence
from dataclasses import dataclass
import fcntl
import json
import logging
import os
from pathlib import Path

from config.ledger_config import DEFAULT_FORECAST_LEDGER_PATH
from src.ledger.materializer import LedgerSnapshot, materialize_events
from src.ledger.schema import (
    ForecastIssued,
    ForecastOutcomeObserved,
    LedgerEvent,
    LedgerValidationError,
    parse_ledger_event,
)


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AppendResult:
    forecast_id: str
    appended: bool


class ForecastLedger:
    """Validate the full event stream before appending complete JSON lines."""

    def __init__(self, path: Path = DEFAULT_FORECAST_LEDGER_PATH) -> None:
        self.path = Path(path)

    @staticmethod
    def _decode(text: str) -> tuple[LedgerEvent, ...]:
        events: list[LedgerEvent] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                raise LedgerValidationError(
                    f"Blank ledger event at line {line_number}"
                )
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerValidationError(
                    f"Invalid ledger JSON at line {line_number}"
                ) from exc
            events.append(parse_ledger_event(payload))
        return tuple(events)

    def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return self.path.open("a+", encoding="utf-8")

    def read(self) -> LedgerSnapshot:
        if not self.path.exists():
            return LedgerSnapshot(())
        with self.path.open("r", encoding="utf-8") as source:
            fcntl.flock(source.fileno(), fcntl.LOCK_SH)
            try:
                return materialize_events(self._decode(source.read()))
            finally:
                fcntl.flock(source.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _issuance_result(
        event: ForecastIssued,
        snapshot: LedgerSnapshot,
    ) -> AppendResult:
        previous = snapshot.by_id().get(event.forecast_id)
        if previous is None:
            return AppendResult(event.forecast_id, True)
        if previous.issuance.immutable_payload() != event.immutable_payload():
            if previous.issuance.prediction != event.prediction:
                reason = "changed prediction"
            else:
                reason = "changed immutable metadata"
            raise LedgerValidationError(
                f"Forecast issuance conflict ({reason}) forecast_id={event.forecast_id}"
            )
        return AppendResult(event.forecast_id, False)

    @staticmethod
    def _outcome_result(
        event: ForecastOutcomeObserved,
        snapshot: LedgerSnapshot,
    ) -> AppendResult:
        previous = snapshot.by_id().get(event.forecast_id)
        if previous is None:
            raise LedgerValidationError(
                f"Cannot append outcome without issuance forecast_id={event.forecast_id}"
            )
        event.validate_against(previous.issuance)
        if previous.outcome is None:
            return AppendResult(event.forecast_id, True)
        if previous.outcome.immutable_payload() != event.immutable_payload():
            raise LedgerValidationError(
                f"Conflicting observed outcome forecast_id={event.forecast_id}"
            )
        return AppendResult(event.forecast_id, False)

    def _append(self, proposed: Sequence[LedgerEvent]) -> tuple[AppendResult, ...]:
        events = tuple(proposed)
        if not events:
            return ()
        with self._open() as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                stream.seek(0)
                existing = self._decode(stream.read())
                working = list(existing)
                results: list[AppendResult] = []
                to_append: list[LedgerEvent] = []
                for event in events:
                    snapshot = materialize_events(tuple(working))
                    result = (
                        self._issuance_result(event, snapshot)
                        if isinstance(event, ForecastIssued)
                        else self._outcome_result(event, snapshot)
                    )
                    results.append(result)
                    if result.appended:
                        working.append(event)
                        to_append.append(event)
                materialize_events(tuple(working))
                if to_append:
                    stream.seek(0, os.SEEK_END)
                    for event in to_append:
                        stream.write(
                            json.dumps(
                                event.as_dict(),
                                sort_keys=True,
                                separators=(",", ":"),
                                allow_nan=False,
                            )
                            + "\n"
                        )
                    stream.flush()
                    os.fsync(stream.fileno())
                LOGGER.info(
                    "Forecast ledger append completed requested=%d appended=%d path=%s",
                    len(events),
                    len(to_append),
                    self.path,
                )
                return tuple(results)
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def append_issued(self, event: ForecastIssued) -> AppendResult:
        return self._append((event,))[0]

    def append_issuances(
        self,
        events: Sequence[ForecastIssued],
    ) -> tuple[AppendResult, ...]:
        return self._append(events)

    def append_outcome(self, event: ForecastOutcomeObserved) -> AppendResult:
        return self._append((event,))[0]

    def append_outcomes(
        self,
        events: Sequence[ForecastOutcomeObserved],
    ) -> tuple[AppendResult, ...]:
        return self._append(events)
