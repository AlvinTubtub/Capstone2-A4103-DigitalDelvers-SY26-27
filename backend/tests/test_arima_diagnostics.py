"""Selected-fit standardized and holdout-error ARIMA diagnostics tests."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from statsmodels.tsa.stattools import acf

from config.model_config import ArimaConfig, DEFAULT_MODEL_CONFIG
from src.evaluation.arima_diagnostics import (
    ArimaDiagnostics,
    STANDARDIZED_RESIDUAL_SOURCE,
    compute_fitted_arima_diagnostics,
    compute_holdout_error_diagnostics,
    compute_ljung_box,
)
from src.models.arima import (
    ArimaSpecification,
    candidate_specifications,
    fit_arima,
)


def fake_result(
    standardized: np.ndarray,
    *,
    raw_residuals: np.ndarray | None = None,
    burn: int = 0,
    diffuse: int = 0,
    arroots: np.ndarray | None = None,
    maroots: np.ndarray | None = None,
) -> SimpleNamespace:
    filter_results = SimpleNamespace(
        standardized_forecasts_error=np.asarray(standardized, dtype=np.float64),
        loglikelihood_burn=burn,
        nobs_diffuse=diffuse,
    )
    return SimpleNamespace(
        arroots=(
            np.asarray([], dtype=np.complex128)
            if arroots is None
            else arroots
        ),
        maroots=(
            np.asarray([], dtype=np.complex128)
            if maroots is None
            else maroots
        ),
        resid=(
            np.full(np.asarray(standardized).size, 999.0)
            if raw_residuals is None
            else raw_residuals
        ),
        loglikelihood_burn=burn,
        nobs_diffuse=diffuse,
        filter_results=filter_results,
    )


def test_standardized_post_burn_residuals_drive_acf_and_ljung_box() -> None:
    standardized = np.asarray([[10.0, 20.0, 0.5, -0.25, 0.75, -0.5, 0.1]])
    result = fake_result(
        standardized,
        raw_residuals=np.asarray([1000.0] * standardized.size),
        burn=2,
    )

    diagnostics = compute_fitted_arima_diagnostics(result, order=(1, 1, 1))
    residuals = diagnostics.fitted_residuals
    cleaned = standardized.reshape(-1)[2:]

    assert diagnostics.available
    assert diagnostics.order == (1, 1, 1)
    assert diagnostics.model_df == 2
    assert residuals.source == STANDARDIZED_RESIDUAL_SOURCE
    assert residuals.standardized_residuals == tuple(cleaned)
    assert 1000.0 not in residuals.standardized_residuals
    assert residuals.burn_in_removed == 2
    assert residuals.residual_count == residuals.observations == len(cleaned)
    assert residuals.model_df == 2
    expected_acf = acf(cleaned, nlags=len(cleaned) - 1, fft=True, missing="raise")
    np.testing.assert_allclose(
        [value for _, value in residuals.acf], expected_acf
    )
    assert residuals.ljung_box == compute_ljung_box(cleaned, model_df=2)
    assert residuals.diagnostic_lag == residuals.ljung_box.lag
    json.dumps(diagnostics.as_dict(), allow_nan=False)


def test_ar_and_ma_roots_flags_and_complex_values_remain_serializable() -> None:
    random = np.random.default_rng(915)
    result = fake_result(
        random.normal(0.0, 1.0, (1, 120)),
        arroots=np.asarray([2.0 + 0.5j, -1.5 + 0.0j]),
        maroots=np.asarray([0.8 + 0.0j]),
    )

    diagnostics = compute_fitted_arima_diagnostics(result, order=(2, 1, 1))
    payload = diagnostics.as_dict()

    assert diagnostics.available
    assert diagnostics.stability_flag is True
    assert diagnostics.invertibility_flag is False
    assert len(payload["ar_roots"]) == 2
    assert payload["ar_root_moduli"][0] == np.hypot(2.0, 0.5)
    assert payload["fitted_residuals"]["acf"][0] == {"lag": 0, "value": 1.0}
    json.dumps(payload, allow_nan=False)


@pytest.mark.parametrize("order", ((0, 1, 1), (1, 1, 0), (0, 1, 0)))
def test_model_df_is_p_plus_q_including_zero_orders(order) -> None:
    result = fake_result(np.linspace(-1.0, 1.0, 30).reshape(1, -1))

    diagnostics = compute_fitted_arima_diagnostics(result, order=order)

    assert diagnostics.order == order
    assert diagnostics.model_df == order[0] + order[2]
    assert diagnostics.fitted_residuals.model_df == order[0] + order[2]
    assert diagnostics.fitted_residuals.ljung_box.model_df == order[0] + order[2]


def test_missing_standardized_source_is_explicitly_unavailable() -> None:
    result = SimpleNamespace(
        arroots=np.asarray([], dtype=np.complex128),
        maroots=np.asarray([], dtype=np.complex128),
        resid=np.linspace(-1.0, 1.0, 20),
        filter_results=SimpleNamespace(loglikelihood_burn=1, nobs_diffuse=0),
    )

    diagnostics = compute_fitted_arima_diagnostics(result, order=(0, 1, 0))

    assert not diagnostics.available
    assert not diagnostics.fitted_residuals.available
    assert diagnostics.fitted_residuals.standardization_status == (
        "unavailable_missing_standardized_forecast_error"
    )
    assert "standardized_forecasts_error" in diagnostics.unavailable_reason
    json.dumps(diagnostics.as_dict(), allow_nan=False)


def test_non_finite_standardized_error_after_burn_is_not_discarded() -> None:
    result = fake_result(
        np.asarray([[np.nan, 0.1, np.inf, 0.2, 0.3]]),
        burn=1,
    )

    diagnostics = compute_fitted_arima_diagnostics(result, order=(0, 1, 1))

    assert not diagnostics.available
    assert not diagnostics.fitted_residuals.available
    assert diagnostics.fitted_residuals.burn_in_removed == 1
    assert diagnostics.fitted_residuals.residual_count == 0
    assert diagnostics.fitted_residuals.standardization_status == (
        "unavailable_non_finite_after_burn_in"
    )
    assert "non-finite" in diagnostics.fitted_residuals.unavailable_reason


def test_missing_burn_metadata_uses_explicit_zero_burn_fallback() -> None:
    standardized = np.linspace(-1.0, 1.0, 20).reshape(1, -1)
    result = SimpleNamespace(
        arroots=np.asarray([], dtype=np.complex128),
        maroots=np.asarray([], dtype=np.complex128),
        filter_results=SimpleNamespace(
            standardized_forecasts_error=standardized,
        ),
    )

    diagnostics = compute_fitted_arima_diagnostics(result, order=(0, 1, 0))
    residuals = diagnostics.fitted_residuals

    assert diagnostics.available
    assert residuals.burn_in_removed == 0
    assert residuals.burn_in_sources == ()
    assert residuals.standardization_status == (
        "available_zero_burn_fallback_no_exposed_metadata"
    )
    assert residuals.standardized_residuals == tuple(standardized.reshape(-1))


def test_burn_in_uses_maximum_exposed_initialization_count() -> None:
    standardized = np.arange(12, dtype=np.float64).reshape(1, -1)
    result = fake_result(standardized, burn=2, diffuse=4)

    diagnostics = compute_fitted_arima_diagnostics(result, order=(1, 1, 0))
    residuals = diagnostics.fitted_residuals

    assert diagnostics.available
    assert residuals.burn_in_removed == 4
    assert residuals.standardized_residuals == tuple(range(4, 12))
    assert dict(residuals.burn_in_sources) == {
        "result.loglikelihood_burn": 2,
        "result.nobs_diffuse": 4,
        "filter_results.loglikelihood_burn": 2,
        "filter_results.nobs_diffuse": 4,
    }


def test_fitted_residual_and_holdout_error_diagnostics_remain_separate() -> None:
    random = np.random.default_rng(117)
    standardized = random.normal(size=(1, 100))
    fitted = compute_fitted_arima_diagnostics(
        fake_result(standardized),
        order=(0, 1, 0),
    )
    holdout_values = random.normal(size=35)
    holdout = compute_holdout_error_diagnostics(holdout_values)
    payload = ArimaDiagnostics(fitted, holdout).as_dict()

    assert set(payload) == {"selected_fitted_model", "holdout_forecast_errors"}
    assert "acf" in payload["selected_fitted_model"]["fitted_residuals"]
    assert "acf" not in payload["holdout_forecast_errors"]
    assert payload["selected_fitted_model"]["fitted_residuals"]["observations"] == 100
    assert payload["holdout_forecast_errors"]["observations"] == 35
    assert payload["holdout_forecast_errors"]["source"] == (
        "complete_aligned_holdout_forecast_errors"
    )
    assert holdout == compute_holdout_error_diagnostics(holdout_values)
    json.dumps(payload, allow_nan=False)


def test_diagnostics_do_not_change_forecast_or_candidate_grid() -> None:
    values = 100.0 + np.cumsum(np.sin(np.arange(80) / 4.0) + 0.1)
    specification = ArimaSpecification((1, 1, 1), "n")
    grid_before = candidate_specifications(ArimaConfig())
    fitted = fit_arima(values, specification, config=DEFAULT_MODEL_CONFIG.arima)
    forecast_before = fitted.forecast_one()

    diagnostics = compute_fitted_arima_diagnostics(
        fitted.result,
        order=specification.order,
    )

    assert diagnostics.available
    assert fitted.forecast_one() == forecast_before
    assert candidate_specifications(ArimaConfig()) == grid_before
    assert len(grid_before) == 80
