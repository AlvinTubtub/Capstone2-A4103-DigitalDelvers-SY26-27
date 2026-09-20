"""Causal OHLCV-derived features for Lag-Informed Regression."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import logging
import math

import numpy as np
from numpy.typing import NDArray

from config.model_config import RegressionFeatureConfig
from src.data.validator import OhlcvRecord, require_chronological_records


LOGGER = logging.getLogger(__name__)
FloatArray = NDArray[np.float64]


class FeatureConstructionError(ValueError):
    """Raised when a causal feature cannot be computed safely."""


class RegressionFeatureGroup(StrEnum):
    """Semantic groups for the existing LIR candidate predictors."""

    RAW_PRICE_LEVEL_FEATURES = "raw_price_level_features"
    RETURN_FEATURES = "return_features"
    NORMALIZED_PRICE_FEATURES = "normalized_price_features"
    NORMALIZED_VOLUME_FEATURES = "normalized_volume_features"
    TRANSFORMED_VOLUME_LEVEL_FEATURES = "transformed_volume_level_features"
    RAW_VOLUME_LEVEL_FEATURES = "raw_volume_level_features"


@dataclass(frozen=True, slots=True)
class RegressionFeatureContract:
    """Validated taxonomy for the unchanged ordered regression feature set."""

    candidate_feature_names: tuple[str, ...]
    feature_groups: tuple[tuple[RegressionFeatureGroup, tuple[str, ...]], ...]
    target_name: str = "next_day_close_delta"
    causal_origin_rule: str = "predictors_use_only_values_available_at_or_before_origin"
    schema_id: str = "forecastph.lir-feature-contract"
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.candidate_feature_names:
            raise FeatureConstructionError("Feature contract cannot be empty")
        if len(set(self.candidate_feature_names)) != len(self.candidate_feature_names):
            raise FeatureConstructionError("Candidate feature names must be unique")
        group_names = tuple(group for group, _ in self.feature_groups)
        if len(set(group_names)) != len(group_names):
            raise FeatureConstructionError("Feature groups must be unique")
        grouped = tuple(
            name for _, names in self.feature_groups for name in names
        )
        if len(grouped) != len(set(grouped)):
            raise FeatureConstructionError(
                "Every candidate feature must belong to exactly one group"
            )
        if set(grouped) != set(self.candidate_feature_names):
            missing = sorted(set(self.candidate_feature_names) - set(grouped))
            extra = sorted(set(grouped) - set(self.candidate_feature_names))
            raise FeatureConstructionError(
                f"Feature-group union mismatch; missing={missing} extra={extra}"
            )
        forbidden = {"target_delta", "target_date", "actual_close"}
        invalid = tuple(
            name
            for name in self.candidate_feature_names
            if name in forbidden or name.startswith("target_")
        )
        if invalid:
            raise FeatureConstructionError(
                f"Target fields cannot be candidate predictors: {invalid}"
            )

    def as_dict(self) -> dict[str, object]:
        membership = {
            name: group.value
            for group, names in self.feature_groups
            for name in names
        }
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "target_name": self.target_name,
            "causal_origin_rule": self.causal_origin_rule,
            "ordered_candidate_feature_names": list(self.candidate_feature_names),
            "ordered_feature_groups": [
                group.value for group, _ in self.feature_groups
            ],
            "groups": {
                group.value: list(names) for group, names in self.feature_groups
            },
            "group_membership": {
                name: membership[name] for name in self.candidate_feature_names
            },
        }


@dataclass(frozen=True, slots=True)
class RegressionSample:
    """Features known at an origin and its next-session delta target."""

    origin_date: date
    target_date: date
    origin_close: float
    actual_close: float
    target_delta: float
    feature_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class RegressionOriginFeatures:
    """Causal feature row for an origin whose next-session target is unknown."""

    origin_date: date
    origin_close: float
    feature_names: tuple[str, ...]
    feature_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class RegressionDataset:
    """Causal feature samples plus dated returns used for fold-local PACF."""

    feature_names: tuple[str, ...]
    samples: tuple[RegressionSample, ...]
    return_dates: tuple[date, ...]
    daily_returns: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.samples:
            raise FeatureConstructionError("Regression dataset contains no usable samples")
        if len(self.return_dates) != len(self.daily_returns):
            raise FeatureConstructionError("Return dates and values must align")
        expected_width = len(self.feature_names)
        if any(len(sample.feature_values) != expected_width for sample in self.samples):
            raise FeatureConstructionError("Feature rows do not match feature_names")

    @property
    def target_dates(self) -> tuple[date, ...]:
        return tuple(sample.target_date for sample in self.samples)

    def matrix(
        self,
        samples: Sequence[RegressionSample] | None = None,
        *,
        feature_names: Sequence[str] | None = None,
    ) -> FloatArray:
        chosen_samples = self.samples if samples is None else samples
        selected_names = self.feature_names if feature_names is None else tuple(feature_names)
        index_by_name = {name: index for index, name in enumerate(self.feature_names)}
        try:
            indices = [index_by_name[name] for name in selected_names]
        except KeyError as exc:
            raise FeatureConstructionError(f"Unknown feature requested: {exc.args[0]}") from exc
        return np.asarray(
            [[sample.feature_values[index] for index in indices] for sample in chosen_samples],
            dtype=np.float64,
        )

    @staticmethod
    def targets(samples: Sequence[RegressionSample]) -> FloatArray:
        return np.asarray([sample.target_delta for sample in samples], dtype=np.float64)

    @staticmethod
    def origin_closes(samples: Sequence[RegressionSample]) -> FloatArray:
        return np.asarray([sample.origin_close for sample in samples], dtype=np.float64)

    def returns_through(self, cutoff: date) -> FloatArray:
        """Return only daily returns observable by a fold's training cutoff."""

        return np.asarray(
            [value for value_date, value in zip(self.return_dates, self.daily_returns) if value_date <= cutoff],
            dtype=np.float64,
        )

    def samples_for_target_dates(
        self, target_dates: Iterable[date]
    ) -> tuple[RegressionSample, ...]:
        """Select exact common-plan targets without reordering or silent omission."""

        requested = tuple(target_dates)
        by_date = {sample.target_date: sample for sample in self.samples}
        missing = [value for value in requested if value not in by_date]
        if missing:
            formatted = ", ".join(value.isoformat() for value in missing[:5])
            raise FeatureConstructionError(f"Missing planned target dates: {formatted}")
        return tuple(by_date[value] for value in requested)


def _ema(values: Sequence[float], period: int) -> list[float]:
    alpha = 2.0 / (period + 1.0)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1.0 - alpha) * result[-1])
    return result


def _mean_std(values: Sequence[float]) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    return float(np.mean(array)), float(np.std(array, ddof=0))


def _safe_relative(numerator: float, denominator: float, *, name: str, origin: date) -> float:
    if denominator == 0.0:
        raise FeatureConstructionError(f"{name} has a zero denominator at {origin.isoformat()}")
    return numerator / denominator


def _minimum_origin_index(config: RegressionFeatureConfig) -> int:
    candidates = [
        max(config.return_lags),
        max(config.rolling_return_windows),
        max(config.volume_windows) - 1,
        config.rsi_period,
        config.ema_slow_period + config.macd_signal_period - 2,
        config.bollinger_window - 1,
        1,
    ]
    if config.raw_price_lags:
        candidates.append(max(config.raw_price_lags))
    return max(candidates)


def regression_feature_names(config: RegressionFeatureConfig) -> tuple[str, ...]:
    """Return the deterministic candidate-feature order."""

    names: list[str] = []
    names.extend(f"return_lag_{lag}" for lag in config.return_lags)
    for window in config.rolling_return_windows:
        names.extend((f"return_mean_{window}", f"return_std_{window}"))
    names.extend(("volume_log", "volume_change_1"))
    for window in config.volume_windows:
        names.extend((f"volume_ratio_{window}", f"volume_z_{window}"))
    names.extend(("range_pct", "open_close_spread_pct", "close_location_in_range"))
    names.extend(f"close_relative_sma_{window}" for window in config.rolling_return_windows)
    names.append(f"rsi_{config.rsi_period}")
    names.extend(
        (
            f"ema_relative_{config.ema_fast_period}",
            f"ema_relative_{config.ema_slow_period}",
            "macd_relative",
            "macd_signal_relative",
            "macd_histogram_relative",
            f"bollinger_z_{config.bollinger_window}",
            f"bollinger_width_{config.bollinger_window}",
            f"bollinger_position_{config.bollinger_window}",
        )
    )
    names.extend(f"raw_close_lag_{lag}" for lag in config.raw_price_lags)
    return tuple(names)


def regression_feature_contract(
    config: RegressionFeatureConfig,
) -> RegressionFeatureContract:
    """Classify every current candidate without changing names, order, or values."""

    candidate_names = regression_feature_names(config)
    return_features = tuple(
        [f"return_lag_{lag}" for lag in config.return_lags]
        + [
            name
            for window in config.rolling_return_windows
            for name in (f"return_mean_{window}", f"return_std_{window}")
        ]
    )
    normalized_price_features = (
        "range_pct",
        "open_close_spread_pct",
        "close_location_in_range",
        *(f"close_relative_sma_{window}" for window in config.rolling_return_windows),
        f"rsi_{config.rsi_period}",
        f"ema_relative_{config.ema_fast_period}",
        f"ema_relative_{config.ema_slow_period}",
        "macd_relative",
        "macd_signal_relative",
        "macd_histogram_relative",
        f"bollinger_z_{config.bollinger_window}",
        f"bollinger_width_{config.bollinger_window}",
        f"bollinger_position_{config.bollinger_window}",
    )
    normalized_volume_features = (
        "volume_change_1",
        *(
            name
            for window in config.volume_windows
            for name in (f"volume_ratio_{window}", f"volume_z_{window}")
        ),
    )
    feature_groups = (
        (
            RegressionFeatureGroup.RAW_PRICE_LEVEL_FEATURES,
            tuple(f"raw_close_lag_{lag}" for lag in config.raw_price_lags),
        ),
        (RegressionFeatureGroup.RETURN_FEATURES, return_features),
        (
            RegressionFeatureGroup.NORMALIZED_PRICE_FEATURES,
            normalized_price_features,
        ),
        (
            RegressionFeatureGroup.NORMALIZED_VOLUME_FEATURES,
            normalized_volume_features,
        ),
        (
            RegressionFeatureGroup.TRANSFORMED_VOLUME_LEVEL_FEATURES,
            ("volume_log",),
        ),
        (RegressionFeatureGroup.RAW_VOLUME_LEVEL_FEATURES, ()),
    )
    contract = RegressionFeatureContract(
        candidate_feature_names=candidate_names,
        feature_groups=feature_groups,
    )
    if contract.candidate_feature_names != regression_feature_names(config):
        raise FeatureConstructionError("Feature-contract ordering is not deterministic")
    return contract


@dataclass(frozen=True, slots=True)
class _RegressionFeatureContext:
    closes: tuple[float, ...]
    volumes: tuple[float, ...]
    returns: tuple[float, ...]
    ema_fast: tuple[float, ...]
    ema_slow: tuple[float, ...]
    macd: tuple[float, ...]
    macd_signal: tuple[float, ...]


def _build_feature_context(
    records: Sequence[OhlcvRecord],
    config: RegressionFeatureConfig,
) -> _RegressionFeatureContext:
    closes = tuple(record.close for record in records)
    volumes = tuple(record.volume for record in records)
    returns = (math.nan,) + tuple(
        _safe_relative(
            closes[index],
            closes[index - 1],
            name="daily return",
            origin=records[index].trading_date,
        )
        - 1.0
        for index in range(1, len(records))
    )
    ema_fast = tuple(_ema(closes, config.ema_fast_period))
    ema_slow = tuple(_ema(closes, config.ema_slow_period))
    macd = tuple(fast - slow for fast, slow in zip(ema_fast, ema_slow))
    macd_signal = tuple(_ema(macd, config.macd_signal_period))
    return _RegressionFeatureContext(
        closes=closes,
        volumes=volumes,
        returns=returns,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        macd=macd,
        macd_signal=macd_signal,
    )


def _feature_values_at(
    records: Sequence[OhlcvRecord],
    index: int,
    config: RegressionFeatureConfig,
    context: _RegressionFeatureContext,
) -> tuple[float, ...]:
    origin = records[index]
    values: list[float] = []
    values.extend(context.returns[index - lag + 1] for lag in config.return_lags)
    for window in config.rolling_return_windows:
        return_window = context.returns[index - window + 1 : index + 1]
        mean_return, std_return = _mean_std(return_window)
        values.extend((mean_return, std_return))

    values.append(math.log1p(origin.volume))
    values.append(
        _safe_relative(
            origin.volume,
            records[index - 1].volume,
            name="volume change",
            origin=origin.trading_date,
        )
        - 1.0
    )
    for window in config.volume_windows:
        volume_window = context.volumes[index - window + 1 : index + 1]
        mean_volume, std_volume = _mean_std(volume_window)
        values.append(
            _safe_relative(
                origin.volume,
                mean_volume,
                name=f"volume ratio {window}",
                origin=origin.trading_date,
            )
            - 1.0
        )
        values.append(
            0.0 if std_volume == 0.0 else (origin.volume - mean_volume) / std_volume
        )

    values.append((origin.high - origin.low) / origin.close)
    values.append((origin.close - origin.open) / origin.open)
    day_range = origin.high - origin.low
    values.append(0.5 if day_range == 0.0 else (origin.close - origin.low) / day_range)
    for window in config.rolling_return_windows:
        mean_close, _ = _mean_std(context.closes[index - window + 1 : index + 1])
        values.append(origin.close / mean_close - 1.0)

    rsi_returns = context.returns[index - config.rsi_period + 1 : index + 1]
    average_gain = sum(max(value, 0.0) for value in rsi_returns) / config.rsi_period
    average_loss = sum(max(-value, 0.0) for value in rsi_returns) / config.rsi_period
    if average_gain == 0.0 and average_loss == 0.0:
        rsi = 50.0
    elif average_loss == 0.0:
        rsi = 100.0
    else:
        relative_strength = average_gain / average_loss
        rsi = 100.0 - (100.0 / (1.0 + relative_strength))
    values.append(rsi)
    values.extend(
        (
            origin.close / context.ema_fast[index] - 1.0,
            origin.close / context.ema_slow[index] - 1.0,
            context.macd[index] / origin.close,
            context.macd_signal[index] / origin.close,
            (context.macd[index] - context.macd_signal[index]) / origin.close,
        )
    )

    bollinger_closes = context.closes[
        index - config.bollinger_window + 1 : index + 1
    ]
    bollinger_mean, bollinger_std = _mean_std(bollinger_closes)
    if bollinger_std == 0.0:
        bollinger_z = 0.0
        bollinger_width = 0.0
        bollinger_position = 0.5
    else:
        band_distance = config.bollinger_standard_deviations * bollinger_std
        lower_band = bollinger_mean - band_distance
        upper_band = bollinger_mean + band_distance
        bollinger_z = (origin.close - bollinger_mean) / bollinger_std
        bollinger_width = (upper_band - lower_band) / bollinger_mean
        bollinger_position = (origin.close - lower_band) / (upper_band - lower_band)
    values.extend((bollinger_z, bollinger_width, bollinger_position))
    values.extend(context.closes[index - lag] for lag in config.raw_price_lags)
    if not all(math.isfinite(value) for value in values):
        raise FeatureConstructionError(
            f"Non-finite derived feature at origin {origin.trading_date.isoformat()}"
        )
    return tuple(values)


def build_regression_origin_features(
    records: Sequence[OhlcvRecord],
    config: RegressionFeatureConfig = RegressionFeatureConfig(),
) -> RegressionOriginFeatures:
    """Build the latest causal row without inventing a future target observation."""

    require_chronological_records(records)
    minimum_origin = _minimum_origin_index(config)
    if len(records) <= minimum_origin:
        raise FeatureConstructionError(
            f"Need more than {minimum_origin} records for configured feature warm-up"
        )
    context = _build_feature_context(records, config)
    index = len(records) - 1
    return RegressionOriginFeatures(
        origin_date=records[index].trading_date,
        origin_close=records[index].close,
        feature_names=regression_feature_names(config),
        feature_values=_feature_values_at(records, index, config, context),
    )


def build_regression_dataset(
    records: Sequence[OhlcvRecord],
    config: RegressionFeatureConfig = RegressionFeatureConfig(),
) -> RegressionDataset:
    """Build strictly causal predictors and Date[t+1] delta targets.

    Indicator warm-up rows are deliberately excluded. No raw value or derived
    feature is forward-filled or backward-filled.
    """

    require_chronological_records(records)
    minimum_origin = _minimum_origin_index(config)
    if len(records) <= minimum_origin + 1:
        raise FeatureConstructionError(
            f"Need more than {minimum_origin + 1} records for configured feature warm-up"
        )

    context = _build_feature_context(records, config)
    names = regression_feature_names(config)

    samples: list[RegressionSample] = []
    for index in range(minimum_origin, len(records) - 1):
        origin = records[index]
        target = records[index + 1]
        values = _feature_values_at(records, index, config, context)
        samples.append(
            RegressionSample(
                origin_date=origin.trading_date,
                target_date=target.trading_date,
                origin_close=origin.close,
                actual_close=target.close,
                target_delta=target.close - origin.close,
                feature_values=values,
            )
        )

    dataset = RegressionDataset(
        feature_names=names,
        samples=tuple(samples),
        return_dates=tuple(record.trading_date for record in records[1:]),
        daily_returns=context.returns[1:],
    )
    LOGGER.info(
        "Built causal LIR features samples=%d features=%d first_origin=%s last_origin=%s",
        len(dataset.samples),
        len(dataset.feature_names),
        dataset.samples[0].origin_date,
        dataset.samples[-1].origin_date,
    )
    return dataset


def feature_names_for_pacf_lags(
    candidate_names: Sequence[str], selected_lags: Sequence[int]
) -> tuple[str, ...]:
    """Keep non-return-lag features plus fold-selected return lags."""

    selected = {f"return_lag_{lag}" for lag in selected_lags}
    return tuple(
        name
        for name in candidate_names
        if not name.startswith("return_lag_") or name in selected
    )
