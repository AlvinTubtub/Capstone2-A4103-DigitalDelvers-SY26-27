"""Separated diagnostics for selected ARIMA fits and OOS forecast errors."""

from collections.abc import Sequence
from dataclasses import dataclass
import math
import warnings

import numpy as np
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf


STANDARDIZED_RESIDUAL_SOURCE = "state_space_standardized_forecast_error"
BURN_IN_RULE = (
    "maximum exposed non-negative initialization count across "
    "result/filter_results loglikelihood_burn and nobs_diffuse; "
    "fallback zero only when no burn metadata is exposed"
)


@dataclass(frozen=True, slots=True)
class LjungBoxDiagnostic:
    available: bool
    observations: int
    lag: int | None
    model_df: int
    statistic: float | None
    p_value: float | None
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "observations": self.observations,
            "lag": self.lag,
            "model_df": self.model_df,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class FittedResidualDiagnostics:
    available: bool
    observations: int
    source: str
    standardized_residuals: tuple[float, ...]
    burn_in_removed: int
    burn_in_rule: str
    burn_in_sources: tuple[tuple[str, int], ...]
    residual_count: int
    model_df: int
    diagnostic_lag: int | None
    standardization_status: str
    acf: tuple[tuple[int, float | None], ...]
    acf_available: bool
    ljung_box: LjungBoxDiagnostic
    acf_unavailable_reason: str | None = None
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "observations": self.observations,
            "source": self.source,
            "standardized_residuals": list(self.standardized_residuals),
            "burn_in_removed": self.burn_in_removed,
            "burn_in_rule": self.burn_in_rule,
            "burn_in_sources": [
                {"source": source, "count": count}
                for source, count in self.burn_in_sources
            ],
            "residual_count": self.residual_count,
            "model_df": self.model_df,
            "diagnostic_lag": self.diagnostic_lag,
            "standardization_status": self.standardization_status,
            "acf_available": self.acf_available,
            "acf": [
                {"lag": lag, "value": value} for lag, value in self.acf
            ],
            "acf_unavailable_reason": self.acf_unavailable_reason,
            "ljung_box": self.ljung_box.as_dict(),
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class SelectedArimaFitDiagnostics:
    available: bool
    order: tuple[int, int, int]
    model_df: int
    ar_roots: tuple[tuple[float, float], ...]
    ar_root_moduli: tuple[float, ...]
    stability_flag: bool | None
    ma_roots: tuple[tuple[float, float], ...]
    ma_root_moduli: tuple[float, ...]
    invertibility_flag: bool | None
    fitted_residuals: FittedResidualDiagnostics
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "order": list(self.order),
            "model_df": self.model_df,
            "ar_roots": [
                {"real": real, "imaginary": imaginary}
                for real, imaginary in self.ar_roots
            ],
            "ar_root_moduli": list(self.ar_root_moduli),
            "stability_flag": self.stability_flag,
            "ma_roots": [
                {"real": real, "imaginary": imaginary}
                for real, imaginary in self.ma_roots
            ],
            "ma_root_moduli": list(self.ma_root_moduli),
            "invertibility_flag": self.invertibility_flag,
            "fitted_residuals": self.fitted_residuals.as_dict(),
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class HoldoutErrorDiagnostics:
    observations: int
    ljung_box: LjungBoxDiagnostic

    def as_dict(self) -> dict[str, object]:
        return {
            "source": "complete_aligned_holdout_forecast_errors",
            "observations": self.observations,
            "ljung_box": self.ljung_box.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ArimaDiagnostics:
    selected_fitted_model: SelectedArimaFitDiagnostics
    holdout_forecast_errors: HoldoutErrorDiagnostics

    def as_dict(self) -> dict[str, object]:
        return {
            "selected_fitted_model": self.selected_fitted_model.as_dict(),
            "holdout_forecast_errors": self.holdout_forecast_errors.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class StandardizedResidualSample:
    """Auditable extraction result for fitted state-space innovations."""

    available: bool
    values: tuple[float, ...]
    burn_in_removed: int
    burn_in_sources: tuple[tuple[str, int], ...]
    status: str
    unavailable_reason: str | None = None


def _finite_series(values: Sequence[float]) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64).reshape(-1)
    return vector[np.isfinite(vector)]


def _diagnostic_lag(observations: int, model_df: int) -> int | None:
    if observations < 3 or observations <= model_df + 1:
        return None
    proposed = max(model_df + 1, min(10, observations // 5))
    return min(proposed, observations - 1)


def compute_ljung_box(
    values: Sequence[float],
    *,
    model_df: int = 0,
) -> LjungBoxDiagnostic:
    """Compute one deterministic Ljung-Box result or explicit unavailability."""

    vector = _finite_series(values)
    observations = int(vector.size)
    lag = _diagnostic_lag(observations, model_df)
    if lag is None:
        return LjungBoxDiagnostic(
            available=False,
            observations=observations,
            lag=None,
            model_df=model_df,
            statistic=None,
            p_value=None,
            unavailable_reason="insufficient finite observations for requested model_df",
        )
    try:
        frame = acorr_ljungbox(
            vector,
            lags=[lag],
            model_df=model_df,
            return_df=True,
        )
        statistic = float(frame["lb_stat"].iloc[-1])
        p_value = float(frame["lb_pvalue"].iloc[-1])
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        return LjungBoxDiagnostic(
            available=False,
            observations=observations,
            lag=lag,
            model_df=model_df,
            statistic=None,
            p_value=None,
            unavailable_reason=f"{type(exc).__name__}: {exc}",
        )
    if not math.isfinite(statistic) or not math.isfinite(p_value):
        return LjungBoxDiagnostic(
            available=False,
            observations=observations,
            lag=lag,
            model_df=model_df,
            statistic=None,
            p_value=None,
            unavailable_reason="Ljung-Box returned a non-finite result",
        )
    return LjungBoxDiagnostic(
        available=True,
        observations=observations,
        lag=lag,
        model_df=model_df,
        statistic=statistic,
        p_value=p_value,
    )


def _unavailable_residuals(
    reason: str,
    *,
    model_df: int,
    burn_in_removed: int = 0,
    burn_in_sources: tuple[tuple[str, int], ...] = (),
    status: str = "unavailable",
) -> FittedResidualDiagnostics:
    ljung_box = LjungBoxDiagnostic(False, 0, None, model_df, None, None, reason)
    residuals = FittedResidualDiagnostics(
        available=False,
        observations=0,
        source=STANDARDIZED_RESIDUAL_SOURCE,
        standardized_residuals=(),
        burn_in_removed=burn_in_removed,
        burn_in_rule=BURN_IN_RULE,
        burn_in_sources=burn_in_sources,
        residual_count=0,
        model_df=model_df,
        diagnostic_lag=None,
        standardization_status=status,
        acf=(),
        acf_available=False,
        ljung_box=ljung_box,
        acf_unavailable_reason=reason,
        unavailable_reason=reason,
    )
    return residuals


def _unavailable_fitted(
    reason: str,
    *,
    order: tuple[int, int, int],
) -> SelectedArimaFitDiagnostics:
    model_df = order[0] + order[2]
    return SelectedArimaFitDiagnostics(
        available=False,
        order=order,
        model_df=model_df,
        ar_roots=(),
        ar_root_moduli=(),
        stability_flag=None,
        ma_roots=(),
        ma_root_moduli=(),
        invertibility_flag=None,
        fitted_residuals=_unavailable_residuals(reason, model_df=model_df),
        unavailable_reason=reason,
    )


def _burn_count(value: object, *, source: str) -> int:
    """Validate one optional state-space initialization count."""

    array = np.asarray(value)
    if array.size != 1:
        raise ValueError(f"{source} must be one scalar count")
    scalar = array.reshape(-1)[0]
    if isinstance(scalar, (bool, np.bool_)):
        raise ValueError(f"{source} must not be boolean")
    try:
        numeric = float(scalar)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source} is not numeric") from exc
    if not math.isfinite(numeric) or numeric < 0.0 or not numeric.is_integer():
        raise ValueError(f"{source} must be a non-negative integer")
    return int(numeric)


def extract_standardized_fitted_residuals(
    result: object,
) -> StandardizedResidualSample:
    """Extract univariate state-space standardized innovations after initialization."""

    filter_results = getattr(result, "filter_results", None)
    if filter_results is None:
        return StandardizedResidualSample(
            False,
            (),
            0,
            (),
            "unavailable_missing_filter_results",
            "fitted result does not expose filter_results",
        )
    raw = getattr(filter_results, "standardized_forecasts_error", None)
    if raw is None:
        return StandardizedResidualSample(
            False,
            (),
            0,
            (),
            "unavailable_missing_standardized_forecast_error",
            "filter_results does not expose standardized_forecasts_error",
        )
    try:
        array = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        return StandardizedResidualSample(
            False,
            (),
            0,
            (),
            "unavailable_invalid_standardized_forecast_error",
            f"cannot convert standardized forecast errors: {exc}",
        )
    if array.ndim == 1:
        series = array
    elif array.ndim == 2 and array.shape[0] == 1:
        series = array[0]
    elif array.ndim == 2 and array.shape[1] == 1:
        series = array[:, 0]
    else:
        return StandardizedResidualSample(
            False,
            (),
            0,
            (),
            "unavailable_ambiguous_multivariate_standardized_error",
            f"expected univariate standardized forecast errors, got shape {array.shape}",
        )

    burn_sources: list[tuple[str, int]] = []
    for owner_name, owner in (("result", result), ("filter_results", filter_results)):
        for attribute in ("loglikelihood_burn", "nobs_diffuse"):
            value = getattr(owner, attribute, None)
            if value is not None:
                source = f"{owner_name}.{attribute}"
                try:
                    burn_sources.append((source, _burn_count(value, source=source)))
                except ValueError as exc:
                    return StandardizedResidualSample(
                        False,
                        (),
                        0,
                        tuple(burn_sources),
                        "unavailable_invalid_burn_metadata",
                        str(exc),
                    )
    burn_in_removed = max((count for _, count in burn_sources), default=0)
    if burn_in_removed >= series.size:
        return StandardizedResidualSample(
            False,
            (),
            burn_in_removed,
            tuple(burn_sources),
            "unavailable_burn_consumes_residual_sample",
            "initialization burn-in leaves no standardized residual observations",
        )
    cleaned = np.asarray(series[burn_in_removed:], dtype=np.float64).reshape(-1)
    if not np.isfinite(cleaned).all():
        return StandardizedResidualSample(
            False,
            (),
            burn_in_removed,
            tuple(burn_sources),
            "unavailable_non_finite_after_burn_in",
            "non-finite standardized forecast errors remain after declared burn-in",
        )
    status = (
        "available_exposed_burn_metadata"
        if burn_sources
        else "available_zero_burn_fallback_no_exposed_metadata"
    )
    return StandardizedResidualSample(
        True,
        tuple(float(value) for value in cleaned),
        burn_in_removed,
        tuple(burn_sources),
        status,
    )


def _roots(values: object) -> tuple[tuple[float, float], ...]:
    vector = np.asarray(values, dtype=np.complex128).reshape(-1)
    if not np.isfinite(vector.real).all() or not np.isfinite(vector.imag).all():
        raise ValueError("ARIMA roots must be finite")
    return tuple((float(value.real), float(value.imag)) for value in vector)


def compute_fitted_arima_diagnostics(
    result: object | None,
    *,
    order: tuple[int, int, int],
) -> SelectedArimaFitDiagnostics:
    """Inspect roots and residuals from the selected fitted ARIMA result."""

    if result is None:
        return _unavailable_fitted(
            "fitted ARIMA result is unavailable",
            order=order,
        )
    try:
        ar_roots = _roots(getattr(result, "arroots"))
        ma_roots = _roots(getattr(result, "maroots"))
    except (AttributeError, TypeError, ValueError) as exc:
        return _unavailable_fitted(
            f"{type(exc).__name__}: {exc}",
            order=order,
        )
    ar_moduli = tuple(float(math.hypot(real, imaginary)) for real, imaginary in ar_roots)
    ma_moduli = tuple(float(math.hypot(real, imaginary)) for real, imaginary in ma_roots)
    model_df = order[0] + order[2]
    extracted = extract_standardized_fitted_residuals(result)
    if not extracted.available:
        reason = extracted.unavailable_reason or "standardized diagnostics unavailable"
        residual_diagnostics = _unavailable_residuals(
            reason,
            model_df=model_df,
            burn_in_removed=extracted.burn_in_removed,
            burn_in_sources=extracted.burn_in_sources,
            status=extracted.status,
        )
        return SelectedArimaFitDiagnostics(
            available=False,
            order=order,
            model_df=model_df,
            ar_roots=ar_roots,
            ar_root_moduli=ar_moduli,
            stability_flag=all(value > 1.0 for value in ar_moduli),
            ma_roots=ma_roots,
            ma_root_moduli=ma_moduli,
            invertibility_flag=all(value > 1.0 for value in ma_moduli),
            fitted_residuals=residual_diagnostics,
            unavailable_reason=reason,
        )
    residual_values = np.asarray(extracted.values, dtype=np.float64)
    ljung_box = compute_ljung_box(residual_values, model_df=model_df)
    acf_values: tuple[tuple[int, float | None], ...] = ()
    acf_unavailable_reason: str | None = None
    if residual_values.size:
        nlags = min(40, max(0, int(residual_values.size) - 1))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                values = np.asarray(
                    acf(residual_values, nlags=nlags, fft=True, missing="raise"),
                    dtype=np.float64,
                )
            acf_values = tuple(
                (index, float(value) if math.isfinite(float(value)) else None)
                for index, value in enumerate(values)
            )
            if not any(value is not None for _, value in acf_values):
                acf_unavailable_reason = "residual ACF returned no finite values"
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            acf_unavailable_reason = f"{type(exc).__name__}: {exc}"
    else:
        acf_unavailable_reason = "no finite fitted residuals"
    residual_diagnostics = FittedResidualDiagnostics(
        available=True,
        observations=int(residual_values.size),
        source=STANDARDIZED_RESIDUAL_SOURCE,
        standardized_residuals=extracted.values,
        burn_in_removed=extracted.burn_in_removed,
        burn_in_rule=BURN_IN_RULE,
        burn_in_sources=extracted.burn_in_sources,
        residual_count=int(residual_values.size),
        model_df=model_df,
        diagnostic_lag=ljung_box.lag,
        standardization_status=extracted.status,
        acf=acf_values,
        acf_available=bool(acf_values) and acf_unavailable_reason is None,
        ljung_box=ljung_box,
        acf_unavailable_reason=acf_unavailable_reason,
        unavailable_reason=None,
    )
    return SelectedArimaFitDiagnostics(
        available=True,
        order=order,
        model_df=model_df,
        ar_roots=ar_roots,
        ar_root_moduli=ar_moduli,
        stability_flag=all(value > 1.0 for value in ar_moduli),
        ma_roots=ma_roots,
        ma_root_moduli=ma_moduli,
        invertibility_flag=all(value > 1.0 for value in ma_moduli),
        fitted_residuals=residual_diagnostics,
    )


def compute_holdout_error_diagnostics(
    forecast_errors: Sequence[float],
) -> HoldoutErrorDiagnostics:
    """Compute Ljung-Box separately on complete OOS forecast errors."""

    errors = _finite_series(forecast_errors)
    return HoldoutErrorDiagnostics(
        observations=int(errors.size),
        ljung_box=compute_ljung_box(errors, model_df=0),
    )
