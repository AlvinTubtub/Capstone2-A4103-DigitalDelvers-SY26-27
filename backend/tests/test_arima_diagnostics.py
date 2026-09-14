"""Selected-fit and holdout-error ARIMA diagnostics tests."""

import json
from types import SimpleNamespace

import numpy as np

from src.evaluation.arima_diagnostics import (
    ArimaDiagnostics,
    compute_fitted_arima_diagnostics,
    compute_holdout_error_diagnostics,
)


def test_ar_and_ma_roots_flags_and_residual_acf_are_serializable() -> None:
    random = np.random.default_rng(915)
    result = SimpleNamespace(
        arroots=np.asarray([2.0 + 0.5j, -1.5 + 0.0j]),
        maroots=np.asarray([0.8 + 0.0j]),
        resid=random.normal(0.0, 1.0, 120),
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


def test_fitted_residual_and_holdout_error_diagnostics_remain_separate() -> None:
    random = np.random.default_rng(117)
    fitted = compute_fitted_arima_diagnostics(
        SimpleNamespace(
            arroots=np.asarray([], dtype=np.complex128),
            maroots=np.asarray([], dtype=np.complex128),
            resid=random.normal(size=100),
        ),
        order=(0, 1, 0),
    )
    holdout = compute_holdout_error_diagnostics(random.normal(size=35))
    payload = ArimaDiagnostics(fitted, holdout).as_dict()

    assert set(payload) == {"selected_fitted_model", "holdout_forecast_errors"}
    assert "acf" in payload["selected_fitted_model"]["fitted_residuals"]
    assert "acf" not in payload["holdout_forecast_errors"]
    assert payload["selected_fitted_model"]["fitted_residuals"]["observations"] == 100
    assert payload["holdout_forecast_errors"]["observations"] == 35
    assert payload["holdout_forecast_errors"]["source"] == (
        "complete_aligned_holdout_forecast_errors"
    )
    json.dumps(payload, allow_nan=False)
