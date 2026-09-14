"""Separated diagnostics for selected ARIMA fits and OOS forecast errors."""

from collections.abc import Sequence
from dataclasses import dataclass
import math
import warnings

import numpy as np
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import acf


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
    acf: tuple[tuple[int, float | None], ...]
    acf_available: bool
    ljung_box: LjungBoxDiagnostic
    acf_unavailable_reason: str | None = None
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "observations": self.observations,
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


def _unavailable_fitted(reason: str) -> SelectedArimaFitDiagnostics:
    ljung_box = LjungBoxDiagnostic(False, 0, None, 0, None, None, reason)
    residuals = FittedResidualDiagnostics(
        False,
        0,
        (),
        False,
        ljung_box,
        reason,
        reason,
    )
    return SelectedArimaFitDiagnostics(
        available=False,
        ar_roots=(),
        ar_root_moduli=(),
        stability_flag=None,
        ma_roots=(),
        ma_root_moduli=(),
        invertibility_flag=None,
        fitted_residuals=residuals,
        unavailable_reason=reason,
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
        return _unavailable_fitted("fitted ARIMA result is unavailable")
    try:
        ar_roots = _roots(getattr(result, "arroots"))
        ma_roots = _roots(getattr(result, "maroots"))
        residual_values = _finite_series(getattr(result, "resid"))
    except (AttributeError, TypeError, ValueError) as exc:
        return _unavailable_fitted(f"{type(exc).__name__}: {exc}")
    ar_moduli = tuple(float(math.hypot(real, imaginary)) for real, imaginary in ar_roots)
    ma_moduli = tuple(float(math.hypot(real, imaginary)) for real, imaginary in ma_roots)
    model_df = order[0] + order[2]
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
        available=bool(residual_values.size),
        observations=int(residual_values.size),
        acf=acf_values,
        acf_available=bool(acf_values) and acf_unavailable_reason is None,
        ljung_box=ljung_box,
        acf_unavailable_reason=acf_unavailable_reason,
        unavailable_reason=None if residual_values.size else "no finite fitted residuals",
    )
    return SelectedArimaFitDiagnostics(
        available=True,
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
