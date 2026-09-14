"""Operational drift evidence from resolved prospective ledger records only."""

from dataclasses import dataclass
from enum import StrEnum
import math

from config.ledger_config import DEFAULT_DRIFT_POLICY, DriftPolicy
from config.model_config import ModelId
from src.ledger.materializer import LedgerSnapshot, ProspectiveForecastRecord


PRINCIPAL_METHODS = (
    ModelId.LAG_REGRESSION,
    ModelId.ARIMA,
    ModelId.LSTM,
)


class DriftMonitoringError(ValueError):
    """Raised when prospective comparison evidence is incomplete or misaligned."""


class DriftStatus(StrEnum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    OK = "OK"
    WATCH = "WATCH"
    DRIFT_SIGNAL = "DRIFT_SIGNAL"


@dataclass(frozen=True, slots=True)
class RollingPerformance:
    window: int
    available_sessions: int
    start_target_date: str | None
    end_target_date: str | None
    rolling_mae: float | None
    rolling_bias: float | None
    naive_rolling_mae: float | None
    mae_ratio_to_naive: float | None
    win_count_vs_naive: int
    win_proportion_vs_naive: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "window": self.window,
            "available_sessions": self.available_sessions,
            "start_target_date": self.start_target_date,
            "end_target_date": self.end_target_date,
            "rolling_mae": self.rolling_mae,
            "rolling_signed_error_bias": self.rolling_bias,
            "naive_rolling_mae": self.naive_rolling_mae,
            "mae_ratio_to_naive": self.mae_ratio_to_naive,
            "win_count_vs_naive": self.win_count_vs_naive,
            "win_proportion_vs_naive": self.win_proportion_vs_naive,
        }


@dataclass(frozen=True, slots=True)
class MethodDriftReport:
    symbol: str
    method: ModelId
    status: DriftStatus
    resolved_session_count: int
    review_window: RollingPerformance
    consideration_window: RollingPerformance
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "method": self.method.value,
            "status": self.status.value,
            "evidence_source": "resolved_prospective_forecast_ledger_only",
            "resolved_session_count": self.resolved_session_count,
            "review_window": self.review_window.as_dict(),
            "consideration_window": self.consideration_window.as_dict(),
            "reasons": list(self.reasons),
            "automatic_action": None,
        }


@dataclass(frozen=True, slots=True)
class CompanyDriftReport:
    symbol: str
    status: DriftStatus
    policy: DriftPolicy
    methods: tuple[MethodDriftReport, ...]

    def report_for(self, method: ModelId) -> MethodDriftReport:
        try:
            return {item.method: item for item in self.methods}[method]
        except KeyError as exc:
            raise DriftMonitoringError(f"No drift report for {method.value}") from exc

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "status": self.status.value,
            "evidence_source": "resolved_prospective_forecast_ledger_only",
            "policy": {
                "review_window": self.policy.review_window,
                "consideration_window": self.policy.consideration_window,
                "watch_mae_ratio": self.policy.watch_mae_ratio,
                "drift_mae_ratio": self.policy.drift_mae_ratio,
                "watch_win_proportion": self.policy.watch_win_proportion,
                "drift_win_proportion": self.policy.drift_win_proportion,
                "watch_bias_to_naive_mae": self.policy.watch_bias_to_naive_mae,
                "drift_bias_to_naive_mae": self.policy.drift_bias_to_naive_mae,
            },
            "methods": [item.as_dict() for item in self.methods],
            "automatic_training": False,
            "automatic_refit": False,
            "automatic_promotion": False,
        }


def _paired_records(
    snapshot: LedgerSnapshot,
    symbol: str,
    method: ModelId,
) -> tuple[
    tuple[ProspectiveForecastRecord, ProspectiveForecastRecord], ...
]:
    resolved = tuple(
        record
        for record in snapshot.resolved
        if record.issuance.symbol == symbol
    )
    naive_by_slot = {
        (record.issuance.origin_date, record.issuance.target_date): record
        for record in resolved
        if record.issuance.method is ModelId.NAIVE
    }
    principals = tuple(
        record for record in resolved if record.issuance.method is method
    )
    paired = []
    for principal in principals:
        slot = (principal.issuance.origin_date, principal.issuance.target_date)
        naive = naive_by_slot.get(slot)
        if naive is None:
            raise DriftMonitoringError(
                f"Resolved {method.value} forecast has no resolved Naive peer on "
                f"{principal.issuance.target_date}"
            )
        if principal.outcome.actual_close != naive.outcome.actual_close:
            raise DriftMonitoringError("Principal and Naive actual Close values disagree")
        paired.append((principal, naive))
    return tuple(
        sorted(paired, key=lambda item: item[0].issuance.target_date)
    )


def _rolling(
    pairs: tuple[tuple[ProspectiveForecastRecord, ProspectiveForecastRecord], ...],
    window: int,
) -> RollingPerformance:
    selected = pairs[-window:]
    if not selected:
        return RollingPerformance(window, 0, None, None, None, None, None, None, 0, None)
    principal_errors = tuple(item[0].outcome.error for item in selected)
    principal_absolute = tuple(item[0].outcome.absolute_error for item in selected)
    naive_absolute = tuple(item[1].outcome.absolute_error for item in selected)
    mae = sum(principal_absolute) / len(selected)
    bias = sum(principal_errors) / len(selected)
    naive_mae = sum(naive_absolute) / len(selected)
    ratio = None if naive_mae == 0.0 else mae / naive_mae
    wins = sum(
        principal < naive
        for principal, naive in zip(principal_absolute, naive_absolute, strict=True)
    )
    return RollingPerformance(
        window=window,
        available_sessions=len(selected),
        start_target_date=selected[0][0].issuance.target_date.isoformat(),
        end_target_date=selected[-1][0].issuance.target_date.isoformat(),
        rolling_mae=mae,
        rolling_bias=bias,
        naive_rolling_mae=naive_mae,
        mae_ratio_to_naive=ratio,
        win_count_vs_naive=wins,
        win_proportion_vs_naive=wins / len(selected),
    )


def _threshold_reasons(
    performance: RollingPerformance,
    *,
    mae_ratio: float,
    win_proportion: float,
    bias_ratio: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if performance.mae_ratio_to_naive is None:
        if performance.rolling_mae and performance.rolling_mae > 0:
            reasons.append("Naive MAE is zero while principal MAE is positive")
    elif performance.mae_ratio_to_naive > mae_ratio:
        reasons.append(
            f"MAE ratio {performance.mae_ratio_to_naive:.6g} > {mae_ratio:.6g}"
        )
    if (
        performance.rolling_mae > performance.naive_rolling_mae
        and performance.win_proportion_vs_naive <= win_proportion
    ):
        reasons.append(
            f"win proportion {performance.win_proportion_vs_naive:.6g} "
            f"<= {win_proportion:.6g}"
        )
    naive_mae = performance.naive_rolling_mae
    bias = performance.rolling_bias
    if naive_mae == 0.0:
        if bias and not math.isclose(bias, 0.0):
            reasons.append("nonzero bias while Naive MAE is zero")
    elif naive_mae is not None and bias is not None and abs(bias) / naive_mae >= bias_ratio:
        reasons.append(
            f"absolute-bias/Naive-MAE ratio {abs(bias) / naive_mae:.6g} "
            f">= {bias_ratio:.6g}"
        )
    return tuple(reasons)


def monitor_company_drift(
    snapshot: LedgerSnapshot,
    symbol: str,
    *,
    policy: DriftPolicy = DEFAULT_DRIFT_POLICY,
) -> CompanyDriftReport:
    """Calculate evidence only; this function has no training or deployment hooks."""

    reports: list[MethodDriftReport] = []
    for method in PRINCIPAL_METHODS:
        pairs = _paired_records(snapshot, symbol, method)
        review = _rolling(pairs, policy.review_window)
        consideration = _rolling(pairs, policy.consideration_window)
        if len(pairs) < policy.review_window:
            status = DriftStatus.INSUFFICIENT_DATA
            reasons = (
                f"{len(pairs)} resolved aligned sessions; "
                f"{policy.review_window} required for ordinary review",
            )
        elif len(pairs) >= policy.consideration_window and (
            reasons := _threshold_reasons(
                consideration,
                mae_ratio=policy.drift_mae_ratio,
                win_proportion=policy.drift_win_proportion,
                bias_ratio=policy.drift_bias_to_naive_mae,
            )
        ):
            status = DriftStatus.DRIFT_SIGNAL
        elif reasons := _threshold_reasons(
            review,
            mae_ratio=policy.watch_mae_ratio,
            win_proportion=policy.watch_win_proportion,
            bias_ratio=policy.watch_bias_to_naive_mae,
        ):
            status = DriftStatus.WATCH
        else:
            status = DriftStatus.OK
            reasons = ("No configured operational threshold was crossed",)
        reports.append(
            MethodDriftReport(
                symbol=symbol,
                method=method,
                status=status,
                resolved_session_count=len(pairs),
                review_window=review,
                consideration_window=consideration,
                reasons=tuple(reasons),
            )
        )
    statuses = {item.status for item in reports}
    if DriftStatus.DRIFT_SIGNAL in statuses:
        overall = DriftStatus.DRIFT_SIGNAL
    elif DriftStatus.WATCH in statuses:
        overall = DriftStatus.WATCH
    elif DriftStatus.INSUFFICIENT_DATA in statuses:
        overall = DriftStatus.INSUFFICIENT_DATA
    else:
        overall = DriftStatus.OK
    return CompanyDriftReport(symbol, overall, policy, tuple(reports))
