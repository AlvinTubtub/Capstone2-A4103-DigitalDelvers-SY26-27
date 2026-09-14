"""Operational policy for the prospective forecast ledger and drift reports."""

from dataclasses import dataclass
from pathlib import Path

from config.settings import BACKEND_ROOT


DEFAULT_FORECAST_LEDGER_PATH = (
    BACKEND_ROOT / "data" / "forecast_ledger" / "events.jsonl"
)


@dataclass(frozen=True, slots=True)
class DriftPolicy:
    """Review thresholds; these are operational defaults, not statistical truths."""

    review_window: int = 20
    consideration_window: int = 60
    watch_mae_ratio: float = 1.0
    drift_mae_ratio: float = 1.10
    watch_win_proportion: float = 0.50
    drift_win_proportion: float = 0.40
    watch_bias_to_naive_mae: float = 0.50
    drift_bias_to_naive_mae: float = 0.75

    def __post_init__(self) -> None:
        if self.review_window < 1:
            raise ValueError("review_window must be positive")
        if self.consideration_window < self.review_window:
            raise ValueError("consideration_window cannot be shorter than review_window")
        if not 0.0 <= self.drift_win_proportion <= self.watch_win_proportion <= 1.0:
            raise ValueError("Win-proportion thresholds must be ordered within 0..1")
        if not 0.0 < self.watch_mae_ratio <= self.drift_mae_ratio:
            raise ValueError("MAE-ratio thresholds must be positive and ordered")
        if not 0.0 < self.watch_bias_to_naive_mae <= self.drift_bias_to_naive_mae:
            raise ValueError("Bias-ratio thresholds must be positive and ordered")


DEFAULT_DRIFT_POLICY = DriftPolicy()
