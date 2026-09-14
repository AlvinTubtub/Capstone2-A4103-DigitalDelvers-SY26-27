"""Authoritative model and chronological-tuning configuration."""

from dataclasses import dataclass, field
from enum import StrEnum


class ModelId(StrEnum):
    """Canonical model identifiers required by the frontend contract."""

    LAG_REGRESSION = "lag_reg"
    ARIMA = "arima"
    LSTM = "lstm"
    NAIVE = "naive"


@dataclass(frozen=True, slots=True)
class RegressionFeatureConfig:
    """Causal candidate-feature settings for Lag-Informed Regression."""

    return_lags: tuple[int, ...] = tuple(range(1, 21))
    rolling_return_windows: tuple[int, ...] = (5, 10, 20)
    volume_windows: tuple[int, ...] = (5, 20)
    rsi_period: int = 14
    ema_fast_period: int = 12
    ema_slow_period: int = 26
    macd_signal_period: int = 9
    bollinger_window: int = 20
    bollinger_standard_deviations: float = 2.0
    raw_price_lags: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.return_lags or not self.rolling_return_windows or not self.volume_windows:
            raise ValueError("Return lags and rolling/volume windows cannot be empty")
        positive_integer_groups = (
            self.return_lags,
            self.rolling_return_windows,
            self.volume_windows,
            self.raw_price_lags,
        )
        if any(value <= 0 for group in positive_integer_groups for value in group):
            raise ValueError("Feature lags and windows must be positive integers")
        if len(set(self.return_lags)) != len(self.return_lags):
            raise ValueError("return_lags cannot contain duplicates")
        if len(set(self.raw_price_lags)) != len(self.raw_price_lags):
            raise ValueError("raw_price_lags cannot contain duplicates")
        scalar_periods = (
            self.rsi_period,
            self.ema_fast_period,
            self.ema_slow_period,
            self.macd_signal_period,
            self.bollinger_window,
        )
        if any(period <= 0 for period in scalar_periods):
            raise ValueError("Indicator periods must be positive integers")
        if self.ema_fast_period >= self.ema_slow_period:
            raise ValueError("ema_fast_period must be smaller than ema_slow_period")
        if self.bollinger_standard_deviations <= 0:
            raise ValueError("bollinger_standard_deviations must be positive")


@dataclass(frozen=True, slots=True)
class LagRegressionConfig:
    """Chronological LASSO and fold-local PACF settings."""

    alpha_grid: tuple[float, ...] = (
        0.0001,
        0.0003,
        0.001,
        0.003,
        0.01,
        0.03,
        0.1,
        0.3,
        1.0,
        3.0,
        10.0,
        30.0,
    )
    cv_splits: int = 5
    pacf_max_lag: int = 20
    pacf_significance_z: float = 1.96
    max_iterations: int = 100_000
    tolerance: float = 1e-7
    coefficient_zero_tolerance: float = 1e-12
    features: RegressionFeatureConfig = field(default_factory=RegressionFeatureConfig)

    def __post_init__(self) -> None:
        if not self.alpha_grid or any(alpha <= 0 for alpha in self.alpha_grid):
            raise ValueError("alpha_grid must contain positive values")
        if tuple(sorted(set(self.alpha_grid))) != self.alpha_grid:
            raise ValueError("alpha_grid must be unique and strictly increasing")
        if self.cv_splits < 2:
            raise ValueError("cv_splits must be at least 2")
        if self.pacf_max_lag < 1:
            raise ValueError("pacf_max_lag must be positive")
        if self.pacf_significance_z <= 0:
            raise ValueError("pacf_significance_z must be positive")
        if self.max_iterations < 1 or self.tolerance <= 0:
            raise ValueError("LASSO convergence settings must be positive")


@dataclass(frozen=True, slots=True)
class ArimaConfig:
    """Search bounds, trend policy, and convergence settings for ARIMA."""

    p_values: tuple[int, ...] = (0, 1, 2, 3)
    d_values: tuple[int, ...] = (0, 1, 2)
    q_values: tuple[int, ...] = (0, 1, 2, 3)
    trend_options_by_d: tuple[tuple[int, tuple[str, ...]], ...] = (
        (0, ("n", "c")),
        (1, ("n", "t")),
        (2, ("n",)),
    )
    cv_splits: int = 5
    retry_max_iterations: tuple[int, ...] = (200, 1_000)
    enforce_stationarity: bool = False
    enforce_invertibility: bool = False
    require_confirmed_convergence: bool = True

    def __post_init__(self) -> None:
        integer_grids = (
            ("p_values", self.p_values, 0, 3),
            ("d_values", self.d_values, 0, 2),
            ("q_values", self.q_values, 0, 3),
        )
        for name, values, lower, upper in integer_grids:
            if not values:
                raise ValueError(f"{name} cannot be empty")
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{name} must be unique and strictly increasing")
            if any(value < lower or value > upper for value in values):
                raise ValueError(f"{name} must stay within {lower}..{upper}")

        trend_map = dict(self.trend_options_by_d)
        if len(trend_map) != len(self.trend_options_by_d):
            raise ValueError("trend_options_by_d cannot repeat a differencing order")
        valid_trends = {"n", "c", "t", "ct"}
        for differencing in self.d_values:
            options = trend_map.get(differencing)
            if not options:
                raise ValueError(f"No trend options configured for d={differencing}")
            if len(set(options)) != len(options) or any(
                option not in valid_trends for option in options
            ):
                raise ValueError(
                    "Trend options must be unique values drawn from n, c, t, and ct"
                )
        if self.cv_splits < 2:
            raise ValueError("cv_splits must be at least 2")
        if (
            not self.retry_max_iterations
            or tuple(sorted(set(self.retry_max_iterations)))
            != self.retry_max_iterations
            or any(value < 1 for value in self.retry_max_iterations)
        ):
            raise ValueError(
                "retry_max_iterations must be unique, positive, and strictly increasing"
            )

    def trends_for_d(self, differencing: int) -> tuple[str, ...]:
        """Return the predeclared trend choices for one differencing order."""

        try:
            return dict(self.trend_options_by_d)[differencing]
        except KeyError as exc:
            raise ValueError(f"No trend options configured for d={differencing}") from exc


@dataclass(frozen=True, slots=True)
class LstmConfig:
    """Central univariate LSTM search and chronological-stopping configuration."""

    lookback_lengths: tuple[int, ...] = (5, 10, 20)
    hidden_sizes: tuple[int, ...] = (16, 32)
    learning_rates: tuple[float, ...] = (0.001, 0.003)
    batch_sizes: tuple[int, ...] = (32,)
    tuning_seeds: tuple[int, ...] = (11, 29, 47)
    cv_splits: int = 5
    max_epochs: int = 100
    early_stopping_patience: int = 10
    early_stopping_min_delta: float = 1e-6
    stopping_tail_proportion: float = 0.15
    minimum_stopping_samples: int = 5
    final_seed: int = 42

    def __post_init__(self) -> None:
        positive_integer_grids = (
            ("lookback_lengths", self.lookback_lengths),
            ("hidden_sizes", self.hidden_sizes),
            ("batch_sizes", self.batch_sizes),
        )
        for name, values in positive_integer_grids:
            if not values or any(value < 1 for value in values):
                raise ValueError(f"{name} must contain positive integers")
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{name} must be unique and strictly increasing")
        if (
            not self.learning_rates
            or any(value <= 0 for value in self.learning_rates)
            or tuple(sorted(set(self.learning_rates))) != self.learning_rates
        ):
            raise ValueError(
                "learning_rates must be positive, unique, and strictly increasing"
            )
        if len(self.tuning_seeds) != 3 or len(set(self.tuning_seeds)) != 3:
            raise ValueError("Exactly three unique tuning_seeds are required")
        if any(seed < 0 for seed in self.tuning_seeds):
            raise ValueError("tuning_seeds cannot be negative")
        if self.cv_splits < 2:
            raise ValueError("cv_splits must be at least 2")
        if self.max_epochs < 1 or self.early_stopping_patience < 1:
            raise ValueError("Epoch and patience settings must be positive")
        if self.early_stopping_min_delta < 0:
            raise ValueError("early_stopping_min_delta cannot be negative")
        if not 0.0 < self.stopping_tail_proportion < 1.0:
            raise ValueError("stopping_tail_proportion must be between zero and one")
        if self.minimum_stopping_samples < 1:
            raise ValueError("minimum_stopping_samples must be positive")
        if self.final_seed != 42:
            raise ValueError("The final development and production seed must remain 42")


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Settings that must be identical across model evaluations."""

    evaluation_proportion: float = 0.15
    random_seed: int = 42
    lag_regression: LagRegressionConfig = field(default_factory=LagRegressionConfig)
    arima: ArimaConfig = field(default_factory=ArimaConfig)
    lstm: LstmConfig = field(default_factory=LstmConfig)

    def __post_init__(self) -> None:
        if not 0.0 < self.evaluation_proportion < 1.0:
            raise ValueError("evaluation_proportion must be strictly between 0 and 1")


DEFAULT_MODEL_CONFIG = ModelConfig()
