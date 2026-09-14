"""Deterministic read model for append-only forecast ledger events."""

from dataclasses import dataclass

from src.ledger.schema import (
    ForecastIssued,
    ForecastOutcomeObserved,
    LedgerEvent,
    LedgerValidationError,
)


@dataclass(frozen=True, slots=True)
class ProspectiveForecastRecord:
    issuance: ForecastIssued
    outcome: ForecastOutcomeObserved | None

    @property
    def pending(self) -> bool:
        return self.outcome is None

    @property
    def resolved(self) -> bool:
        return self.outcome is not None

    def as_dict(self) -> dict[str, object]:
        outcome = self.outcome
        return {
            "status": "pending" if outcome is None else "resolved",
            "forecast_id": self.issuance.forecast_id,
            "created_at": self.issuance.created_at.isoformat(),
            "symbol": self.issuance.symbol,
            "origin_date": self.issuance.origin_date.isoformat(),
            "target_date": self.issuance.target_date.isoformat(),
            "method": self.issuance.method.value,
            "model_version": self.issuance.model_version,
            "prediction": self.issuance.prediction,
            "production_run_id": self.issuance.production_run_id,
            "source_commit": self.issuance.source_commit,
            "observed_at": outcome.observed_at.isoformat() if outcome else None,
            "actual_close": outcome.actual_close if outcome else None,
            "error": outcome.error if outcome else None,
            "absolute_error": outcome.absolute_error if outcome else None,
            "squared_error": outcome.squared_error if outcome else None,
        }


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    records: tuple[ProspectiveForecastRecord, ...]

    @property
    def pending(self) -> tuple[ProspectiveForecastRecord, ...]:
        return tuple(record for record in self.records if record.pending)

    @property
    def resolved(self) -> tuple[ProspectiveForecastRecord, ...]:
        return tuple(record for record in self.records if record.resolved)

    def by_id(self) -> dict[str, ProspectiveForecastRecord]:
        return {record.issuance.forecast_id: record for record in self.records}

    def as_dict(self) -> dict[str, object]:
        return {
            "record_count": len(self.records),
            "pending_count": len(self.pending),
            "resolved_count": len(self.resolved),
            "records": [record.as_dict() for record in self.records],
        }


def materialize_events(events: tuple[LedgerEvent, ...]) -> LedgerSnapshot:
    """Replay ledger order, rejecting conflicts instead of truncating or repairing."""

    issuances: dict[str, ForecastIssued] = {}
    outcomes: dict[str, ForecastOutcomeObserved] = {}
    for event in events:
        if isinstance(event, ForecastIssued):
            previous = issuances.get(event.forecast_id)
            if previous is None:
                issuances[event.forecast_id] = event
            elif previous.immutable_payload() != event.immutable_payload():
                raise LedgerValidationError(
                    f"Conflicting issuance for forecast_id={event.forecast_id}"
                )
            continue
        issuance = issuances.get(event.forecast_id)
        if issuance is None:
            raise LedgerValidationError(
                f"Outcome has no prior issuance forecast_id={event.forecast_id}"
            )
        event.validate_against(issuance)
        previous_outcome = outcomes.get(event.forecast_id)
        if previous_outcome is None:
            outcomes[event.forecast_id] = event
        elif previous_outcome.immutable_payload() != event.immutable_payload():
            raise LedgerValidationError(
                f"Conflicting outcome for forecast_id={event.forecast_id}"
            )

    records = tuple(
        ProspectiveForecastRecord(issuance, outcomes.get(forecast_id))
        for forecast_id, issuance in sorted(
            issuances.items(),
            key=lambda item: (
                item[1].target_date,
                item[1].symbol,
                item[1].method.value,
                item[0],
            ),
        )
    )
    return LedgerSnapshot(records)
