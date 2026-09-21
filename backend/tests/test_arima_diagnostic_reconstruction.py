"""Focused tests for selected-specification ARIMA diagnostic-only refits."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import numpy as np
import pytest

from config.model_config import ArimaConfig
from src.evaluation.arima_diagnostic_reconstruction import (
    ArimaDiagnosticReconstructionError,
    arima_config_as_dict,
    reconstruct_company_arima_diagnostics,
    reconstruct_frozen_arima_config,
)
from src.models.arima import ConvergenceStatus, candidate_specifications


FORMAL_ID = "FORECASTPH_FORMAL_TEST"


def frozen_config() -> dict[str, object]:
    return arima_config_as_dict(ArimaConfig())


def evidence() -> dict[str, object]:
    return {
        "development_target_dates": [
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
        ],
        "holdout_target_dates": ["2026-01-05", "2026-01-06"],
        "model_grids_and_seeds": {"arima": frozen_config()},
        "selected_configurations": {
            "arima": {"order": [1, 1, 0], "trend": "n"}
        },
        "arima_diagnostics": {
            "holdout_forecast_errors": {
                "source": "complete_aligned_holdout_forecast_errors",
                "observations": 2,
                "ljung_box": {"available": False},
            }
        },
    }


def write_frozen_raw(path: Path, closes: list[float] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = closes or [100.0, 101.0, 102.0, 103.0, 999.0, 998.0]
    rows = ["Date,Close"]
    rows.extend(
        f"2026-01-0{index + 1},{value}"
        for index, value in enumerate(values)
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def diagnostic_payload(order: tuple[int, int, int], nobs: int) -> dict[str, object]:
    model_df = order[0] + order[2]
    burn = 1
    residuals = [0.1] * (nobs - burn)
    return {
        "available": True,
        "order": list(order),
        "model_df": model_df,
        "ar_roots": [{"real": 2.0, "imaginary": 0.0}] if order[0] else [],
        "ar_root_moduli": [2.0] if order[0] else [],
        "stability_flag": True,
        "ma_roots": [],
        "ma_root_moduli": [],
        "invertibility_flag": True,
        "fitted_residuals": {
            "available": True,
            "observations": len(residuals),
            "source": "state_space_standardized_forecast_error",
            "standardized_residuals": residuals,
            "burn_in_removed": burn,
            "burn_in_rule": "synthetic exposed burn metadata",
            "burn_in_sources": [{"source": "result.loglikelihood_burn", "count": burn}],
            "residual_count": len(residuals),
            "model_df": model_df,
            "diagnostic_lag": 2,
            "standardization_status": "available_exposed_burn_metadata",
            "acf_available": True,
            "acf": [{"lag": 0, "value": 1.0}, {"lag": 1, "value": 0.0}],
            "acf_unavailable_reason": None,
            "ljung_box": {
                "available": True,
                "observations": len(residuals),
                "lag": 2,
                "model_df": model_df,
                "statistic": 1.0,
                "p_value": 0.5,
                "unavailable_reason": None,
            },
            "unavailable_reason": None,
        },
        "unavailable_reason": None,
    }


class FakeFit:
    def __init__(
        self,
        closes: tuple[float, ...],
        specification,
        *,
        convergence: ConvergenceStatus = ConvergenceStatus.CONFIRMED_CONVERGED,
    ) -> None:
        self.result = object()
        self.specification = specification
        self.convergence = convergence
        self._closes = closes

    def fit_metadata(self) -> dict[str, object]:
        return {
            **self.specification.as_dict(),
            "nobs": len(self._closes),
            "aic": 1.0,
            "bic": 2.0,
            "hqic": 1.5,
            "log_likelihood": -1.0,
            "parameters": {"ar.L1": 0.5, "sigma2": 1.0},
            "convergence_status": self.convergence.value,
            "fit_attempts": [
                {
                    "max_iterations": 200,
                    "status": self.convergence.value,
                    "optimizer_details": {"converged": True},
                    "exception": None,
                    "warnings": [],
                }
            ],
        }


class FakeDiagnostics:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def as_dict(self) -> dict[str, object]:
        return deepcopy(self.payload)


class FakeFilteredResult:
    def __init__(self, values: tuple[float, ...], nobs: int) -> None:
        self.params = np.asarray(values, dtype=np.float64)
        self.param_names = ["ar.L1", "sigma2"]
        self.nobs = nobs
        self.aic = 1.0
        self.bic = 2.0
        self.hqic = 1.5
        self.llf = -1.0


class FakeArimaModel:
    param_names = ["ar.L1", "sigma2"]

    def __init__(self, values, **kwargs) -> None:
        self.values = tuple(values)
        self.kwargs = kwargs
        self.filtered_vectors: list[tuple[float, ...]] = []

    def filter(self, values):
        vector = tuple(float(value) for value in values)
        self.filtered_vectors.append(vector)
        return FakeFilteredResult(vector, len(self.values))


def run_reconstruction(
    tmp_path: Path,
    *,
    source: dict[str, object] | None = None,
    closes: list[float] | None = None,
    convergence: ConvergenceStatus = ConvergenceStatus.CONFIRMED_CONVERGED,
):
    raw = tmp_path / "AAA.csv"
    write_frozen_raw(raw, closes)
    calls: dict[str, object] = {"fit_count": 0, "diagnostics_count": 0}

    def fit_spy(values, specification, *, config):
        calls["fit_count"] += 1
        calls["fit_values"] = tuple(values)
        calls["specification"] = specification
        calls["config"] = config
        fitted = FakeFit(tuple(values), specification, convergence=convergence)
        calls["result"] = fitted.result
        return fitted

    def diagnostics_spy(result, *, order):
        calls["diagnostics_count"] += 1
        calls["diagnostics_result"] = result
        calls["diagnostics_order"] = order
        return FakeDiagnostics(diagnostic_payload(order, len(calls["fit_values"])))

    result = reconstruct_company_arima_diagnostics(
        "AAA",
        source or evidence(),
        raw,
        source_formal_run_id=FORMAL_ID,
        fit_function=fit_spy,
        diagnostics_function=diagnostics_spy,
    )
    return result, calls


def run_frozen_reconstruction(
    tmp_path: Path,
    *,
    parameters: dict[str, object] | None = None,
    closes: list[float] | None = None,
):
    raw = tmp_path / "AAA.csv"
    write_frozen_raw(raw, closes)
    source = evidence()
    source["selected_configurations"]["arima"]["development_fit"] = {
        "order": [1, 1, 0],
        "trend": "n",
        "nobs": 4,
        "parameters": parameters
        if parameters is not None
        else {"sigma2": 1.0, "ar.L1": 0.5},
        "convergence_status": "confirmed_converged",
        "fit_attempts": [],
    }
    calls: dict[str, object] = {"fit_count": 0, "models": []}

    def forbidden_fit(*args, **kwargs):
        calls["fit_count"] += 1
        raise AssertionError("Frozen-parameter path invoked the optimizer")

    def model_factory(values, **kwargs):
        model = FakeArimaModel(values, **kwargs)
        calls["models"].append(model)
        return model

    def diagnostics_spy(result, *, order):
        calls["diagnostics_result"] = result
        return FakeDiagnostics(diagnostic_payload(order, result.nobs))

    result = reconstruct_company_arima_diagnostics(
        "AAA",
        source,
        raw,
        source_formal_run_id=FORMAL_ID,
        fit_function=forbidden_fit,
        diagnostics_function=diagnostics_spy,
        model_factory=model_factory,
    )
    return result, calls


def test_frozen_parameters_are_filtered_in_model_order_without_optimizer(
    tmp_path: Path,
) -> None:
    result, calls = run_frozen_reconstruction(tmp_path)

    assert calls["fit_count"] == 0
    assert len(calls["models"]) == 1
    assert calls["models"][0].filtered_vectors == [(0.5, 1.0)]
    assert result["diagnostic_mode"] == (
        "frozen_parameter_state_space_reconstruction"
    )
    assert result["fit_metadata"]["parameters"] == {
        "ar.L1": 0.5,
        "sigma2": 1.0,
    }
    assert result["fit_provenance"]["expected_parameter_names"] == [
        "ar.L1",
        "sigma2",
    ]
    assert result["fit_provenance"]["frozen_parameter_names"] == [
        "sigma2",
        "ar.L1",
    ]
    assert result["fit_provenance"]["optimization_performed"] is False
    assert result["fit_provenance"]["refit_performed"] is False


@pytest.mark.parametrize(
    "parameters",
    (
        {"ar.L1": 0.5},
        {"ar.L1": 0.5, "sigma2": 1.0, "extra": 2.0},
        {"ar.L1": 0.5, "sigma2": float("nan")},
        {"ar.L1": 0.5, "sigma2": True},
    ),
)
def test_invalid_frozen_parameter_metadata_fails_closed(
    tmp_path: Path,
    parameters: dict[str, object],
) -> None:
    with pytest.raises(ArimaDiagnosticReconstructionError):
        run_frozen_reconstruction(tmp_path, parameters=parameters)


def test_changed_frozen_parameter_changes_filtered_state(tmp_path: Path) -> None:
    first, _ = run_frozen_reconstruction(tmp_path / "first")
    changed, _ = run_frozen_reconstruction(
        tmp_path / "changed",
        parameters={"sigma2": 2.0, "ar.L1": 0.25},
    )

    assert first["fit_metadata"]["parameters"] != changed["fit_metadata"][
        "parameters"
    ]


def test_holdout_values_do_not_enter_frozen_parameter_reconstruction(
    tmp_path: Path,
) -> None:
    first, first_calls = run_frozen_reconstruction(tmp_path / "first")
    changed, changed_calls = run_frozen_reconstruction(
        tmp_path / "changed",
        closes=[100.0, 101.0, 102.0, 103.0, 1.0, 2.0],
    )

    assert first_calls["models"][0].values == changed_calls["models"][0].values
    assert first["fit_metadata"]["parameters"] == changed["fit_metadata"][
        "parameters"
    ]
    assert first["fitted_model_diagnostics"]["model_df"] == 1


def test_exactly_one_selected_fit_and_existing_diagnostics_are_used(tmp_path: Path) -> None:
    result, calls = run_reconstruction(tmp_path)

    assert calls["fit_count"] == 1
    assert calls["diagnostics_count"] == 1
    assert calls["fit_values"] == (100.0, 101.0, 102.0, 103.0)
    assert calls["specification"].order == (1, 1, 0)
    assert calls["specification"].trend == "n"
    assert calls["diagnostics_result"] is calls["result"]
    assert calls["diagnostics_order"] == (1, 1, 0)
    assert result["diagnostic_mode"] == "diagnostic_only_refit"
    assert result["fit_provenance"]["grid_search_performed"] is False
    assert result["fit_provenance"]["model_selection_performed"] is False
    assert result["fit_provenance"]["holdout_used_for_fit"] is False
    assert result["fit_provenance"]["holdout_forecasts_regenerated"] is False
    assert result["fitted_model_diagnostics"]["model_df"] == 1
    assert result["fitted_model_diagnostics"]["fitted_residuals"][
        "standardized_residuals"
    ]
    json.dumps(result, allow_nan=False)


def test_tuning_and_candidate_scoring_are_never_called(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import src.training.train_arima as training

    def forbidden(*args, **kwargs):
        raise AssertionError("Diagnostic reconstruction attempted tuning/scoring")

    monkeypatch.setattr(training, "tune_arima", forbidden)
    monkeypatch.setattr(training, "score_arima_candidate", forbidden)
    result, calls = run_reconstruction(tmp_path)

    assert result["enhanced_standardized_residual_diagnostics_available"] is True
    assert calls["fit_count"] == 1


def test_frozen_arima_config_is_reconstructed_exactly() -> None:
    payload = frozen_config()
    reconstructed = reconstruct_frozen_arima_config(payload)

    assert arima_config_as_dict(reconstructed) == payload
    assert len(candidate_specifications(reconstructed)) == 80


def test_holdout_close_mutation_does_not_change_fit_input(tmp_path: Path) -> None:
    _, first = run_reconstruction(tmp_path / "first")
    _, changed = run_reconstruction(
        tmp_path / "changed",
        closes=[100.0, 101.0, 102.0, 103.0, 1.0, 2.0],
    )

    assert first["fit_values"] == changed["fit_values"]


def test_development_close_mutation_changes_fit_input(tmp_path: Path) -> None:
    _, first = run_reconstruction(tmp_path / "first")
    _, changed = run_reconstruction(
        tmp_path / "changed",
        closes=[100.0, 101.0, 222.0, 103.0, 999.0, 998.0],
    )

    assert first["fit_values"] != changed["fit_values"]


@pytest.mark.parametrize(
    "dates",
    (
        ["2026-01-02", "2026-01-02", "2026-01-04"],
        ["2026-01-03", "2026-01-02", "2026-01-04"],
        ["2026-01-02", "2026-01-03", "2026-01-09"],
    ),
)
def test_malformed_duplicate_nonchronological_or_unmapped_dates_fail_closed(
    tmp_path: Path,
    dates: list[str],
) -> None:
    source = evidence()
    source["development_target_dates"] = dates

    with pytest.raises(ArimaDiagnosticReconstructionError):
        run_reconstruction(tmp_path, source=source)


def test_selected_specification_outside_frozen_config_fails_closed(tmp_path: Path) -> None:
    source = evidence()
    source["selected_configurations"]["arima"]["order"] = [9, 1, 0]

    with pytest.raises(ArimaDiagnosticReconstructionError, match="not legal"):
        run_reconstruction(tmp_path, source=source)


def test_nonconverged_selected_fit_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ArimaDiagnosticReconstructionError, match="convergence"):
        run_reconstruction(
            tmp_path,
            convergence=ConvergenceStatus.CONFIRMED_NON_CONVERGED,
        )


def test_frozen_config_with_missing_or_changed_fields_fails_closed() -> None:
    missing = frozen_config()
    missing.pop("retry_max_iterations")
    with pytest.raises(ArimaDiagnosticReconstructionError):
        reconstruct_frozen_arima_config(missing)

    changed = frozen_config()
    changed["enforce_stationarity"] = 0
    with pytest.raises(ArimaDiagnosticReconstructionError):
        reconstruct_frozen_arima_config(changed)
