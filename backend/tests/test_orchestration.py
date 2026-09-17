"""Clean lifecycle, persisted evaluation, CLI, and reset-confirmation tests."""

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from config.model_config import ModelConfig, ModelId
from scripts import forecast_all, reset_artifacts, train_all, validate_raw
from src.data.calendar import PSETradingCalendar
from src.data.split import build_company_evaluation_plan
from src.data.validator import OhlcvRecord
from src.evaluation.evaluator import ModelPredictionOutput, evaluate_prediction_outputs
from src.inference.next_day import CompanyNextDayForecast, NextDayPrediction
from src.training import orchestration
from src.training.orchestration import (
    EVALUATION_ARTIFACT_SCHEMA_ID,
    FORECAST_ARTIFACT_SCHEMA_ID,
    OrchestrationError,
    forecast_company_from_artifacts,
    load_company_evaluation,
    persist_company_evaluation,
    persist_next_day_forecast,
    train_company_lifecycle,
)


MANILA = ZoneInfo("Asia/Manila")
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def synthetic_records(count: int = 24) -> tuple[OhlcvRecord, ...]:
    start = date(2026, 1, 2)
    return tuple(
        OhlcvRecord(
            trading_date=start + timedelta(days=index),
            open=100.0 + index - 0.2,
            high=100.0 + index + 0.5,
            low=100.0 + index - 0.5,
            close=100.0 + index,
            volume=10_000.0 + index,
        )
        for index in range(count)
    )


def canonical_evaluation(records: tuple[OhlcvRecord, ...]):
    plan = build_company_evaluation_plan(
        "ALI",
        records,
        model_config=ModelConfig(evaluation_proportion=0.4),
    )
    actual = tuple(pair.actual_close for pair in plan.evaluation_pairs)
    return evaluate_prediction_outputs(
        plan,
        tuple(
            ModelPredictionOutput(
                symbol="ALI",
                model=model,
                target_dates=plan.evaluation_target_dates,
                actual_closes=actual,
                predicted_closes=tuple(
                    value + offset for value in actual
                ),
            )
            for model, offset in (
                (ModelId.LAG_REGRESSION, 0.1),
                (ModelId.ARIMA, 0.2),
                (ModelId.LSTM, 0.3),
            )
        ),
    )


def next_day_forecast(records: tuple[OhlcvRecord, ...]) -> CompanyNextDayForecast:
    origin = records[-1]
    target = origin.trading_date + timedelta(days=1)
    predictions = tuple(
        NextDayPrediction(
            symbol="ALI",
            model=model,
            origin_date=origin.trading_date,
            forecast_for=target,
            origin_close=origin.close,
            predicted_delta=offset,
            predicted_close=origin.close + offset,
            inference_at=datetime(2026, 2, 1, 17, 0, tzinfo=MANILA),
        )
        for model, offset in (
            (ModelId.LAG_REGRESSION, 0.1),
            (ModelId.ARIMA, 0.2),
            (ModelId.LSTM, 0.3),
        )
    )
    return CompanyNextDayForecast(
        symbol="ALI",
        origin_date=origin.trading_date,
        forecast_for=target,
        predictions=predictions,
    )


def test_new_evaluation_and_forecast_artifacts_are_versioned_and_validated(
    tmp_path: Path,
) -> None:
    records = synthetic_records()
    evaluation = canonical_evaluation(records)
    root = tmp_path / "artifacts"
    evaluation_path = persist_company_evaluation(
        evaluation,
        records,
        artifacts_root=root,
        created_at=datetime(2026, 2, 1, 16, 0, tzinfo=MANILA),
    )
    forecast_path = persist_next_day_forecast(
        next_day_forecast(records), artifacts_root=root
    )

    metadata = json.loads(
        evaluation_path.with_name("evaluation.metadata.json").read_text(encoding="utf-8")
    )
    forecast_payload = json.loads(forecast_path.read_text(encoding="utf-8"))
    assert metadata["schema_id"] == EVALUATION_ARTIFACT_SCHEMA_ID
    assert metadata["source"] == "chronological_out_of_sample_evaluation"
    assert metadata["data_through"] == records[-1].trading_date.isoformat()
    assert forecast_payload["schema_id"] == FORECAST_ARTIFACT_SCHEMA_ID
    assert len(forecast_payload["predictions"]) == 3
    assert load_company_evaluation("ALI", records, artifacts_root=root) == evaluation

    extended = records + (
        OhlcvRecord(
            trading_date=records[-1].trading_date + timedelta(days=1),
            open=124.0,
            high=125.0,
            low=123.0,
            close=124.5,
            volume=11_000.0,
        ),
    )
    assert load_company_evaluation("ALI", extended, artifacts_root=root) == evaluation

    with evaluation_path.open("ab") as output:
        output.write(b"tampered")
    with pytest.raises(OrchestrationError, match="checksum"):
        load_company_evaluation("ALI", records, artifacts_root=root)


def test_train_company_lifecycle_calls_each_authoritative_stage_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    records = synthetic_records()
    calls: list[str] = []
    plan = SimpleNamespace()
    output_dates = (date(2026, 1, 25),)

    def stage(name: str, result):
        def implementation(*args, **kwargs):
            calls.append(name)
            return result

        return implementation

    def evidence_stage(name: str, expected, result):
        def implementation(value, *, artifact_name, artifacts_root):
            calls.append(name)
            assert value is expected
            assert artifact_name == "ALI"
            assert artifacts_root == tmp_path / "artifacts"
            return result

        return implementation

    model_result = lambda offset: SimpleNamespace(
        symbol="ALI",
        target_dates=output_dates,
        actual_closes=(124.0,),
        predicted_closes=(124.0 + offset,),
    )
    lir = model_result(0.1)
    arima = model_result(0.2)
    lstm = model_result(0.3)
    evaluation = SimpleNamespace(symbol="ALI")
    selections = SimpleNamespace()
    refit = SimpleNamespace()
    forecast = next_day_forecast(records)
    monkeypatch.setattr(orchestration, "build_company_evaluation_plan", stage("plan", plan))
    monkeypatch.setattr(orchestration, "build_regression_dataset", stage("features", object()))
    monkeypatch.setattr(orchestration, "train_lir_for_evaluation", stage("lir", lir))
    monkeypatch.setattr(orchestration, "train_arima_for_evaluation", stage("arima", arima))
    monkeypatch.setattr(orchestration, "train_lstm_for_evaluation", stage("lstm", lstm))
    monkeypatch.setattr(
        orchestration,
        "persist_lir_metadata",
        evidence_stage(
            "persist_lir_evidence",
            lir,
            tmp_path / "evaluations/lir/ALI.json",
        ),
    )
    monkeypatch.setattr(
        orchestration,
        "persist_arima_metadata",
        evidence_stage(
            "persist_arima_evidence",
            arima,
            tmp_path / "evaluations/arima/ALI.json",
        ),
    )
    monkeypatch.setattr(
        orchestration,
        "persist_lstm_artifacts",
        evidence_stage(
            "persist_lstm_evidence",
            lstm,
            orchestration.LstmArtifactPaths(
                metadata=tmp_path / "evaluations/lstm/ALI.json",
                model_state=tmp_path / "evaluations/lstm/ALI.pt",
            ),
        ),
    )
    monkeypatch.setattr(orchestration, "evaluate_prediction_outputs", stage("evaluate", evaluation))
    monkeypatch.setattr(
        orchestration, "selections_from_evaluation_results", stage("select", selections)
    )
    monkeypatch.setattr(
        orchestration, "refit_all_principal_models", stage("production_refit", refit)
    )
    monkeypatch.setattr(
        orchestration, "predict_next_day_from_fresh_refit", stage("forecast", forecast)
    )
    monkeypatch.setattr(
        orchestration,
        "persist_company_evaluation",
        stage("persist_evaluation", tmp_path / "evaluation.joblib"),
    )
    monkeypatch.setattr(
        orchestration,
        "persist_next_day_forecast",
        stage("persist_forecast", tmp_path / "forecast.json"),
    )

    result = train_company_lifecycle(
        "ALI",
        records,
        calendar=PSETradingCalendar(),
        artifacts_root=tmp_path / "artifacts",
    )

    assert result.symbol == "ALI"
    assert result.production_refit is refit
    assert result.evaluation_path == tmp_path / "evaluation.joblib"
    assert result.forecast_path == tmp_path / "forecast.json"
    assert result.frontend_artifacts.evaluation is evaluation
    assert result.frontend_artifacts.next_day_forecast is forecast
    assert result.model_evaluation_artifacts.lir_metadata.name == "ALI.json"
    assert result.model_evaluation_artifacts.arima_metadata.name == "ALI.json"
    assert result.model_evaluation_artifacts.lstm_metadata.name == "ALI.json"
    assert result.model_evaluation_artifacts.lstm_model_state.name == "ALI.pt"
    assert calls == [
        "plan",
        "features",
        "lir",
        "arima",
        "lstm",
        "persist_lir_evidence",
        "persist_arima_evidence",
        "persist_lstm_evidence",
        "evaluate",
        "select",
        "production_refit",
        "forecast",
        "persist_evaluation",
        "persist_forecast",
    ]


def test_model_evidence_persistence_failure_stops_before_production_refit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    records = synthetic_records()
    trained = SimpleNamespace(symbol="ALI")
    production_called = False

    monkeypatch.setattr(orchestration, "build_company_evaluation_plan", lambda *args, **kwargs: object())
    monkeypatch.setattr(orchestration, "build_regression_dataset", lambda *args, **kwargs: object())
    monkeypatch.setattr(orchestration, "train_lir_for_evaluation", lambda *args, **kwargs: trained)
    monkeypatch.setattr(orchestration, "train_arima_for_evaluation", lambda *args, **kwargs: trained)
    monkeypatch.setattr(orchestration, "train_lstm_for_evaluation", lambda *args, **kwargs: trained)

    def fail_persistence(*args, **kwargs):
        raise OSError("evaluation artifact storage unavailable")

    def production_refit(*args, **kwargs):
        nonlocal production_called
        production_called = True

    monkeypatch.setattr(orchestration, "persist_lir_metadata", fail_persistence)
    monkeypatch.setattr(orchestration, "refit_all_principal_models", production_refit)

    with pytest.raises(OSError, match="storage unavailable"):
        train_company_lifecycle(
            "ALI",
            records,
            calendar=PSETradingCalendar(),
            artifacts_root=tmp_path / "artifacts",
        )

    assert not production_called


def test_forecast_lifecycle_loads_and_predicts_without_training(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = synthetic_records()
    evaluation = canonical_evaluation(records)
    forecast = next_day_forecast(records)
    calls: list[str] = []
    monkeypatch.setattr(
        orchestration,
        "load_company_evaluation",
        lambda *args, **kwargs: calls.append("load_evaluation") or evaluation,
    )
    monkeypatch.setattr(
        orchestration,
        "predict_next_day_from_artifacts",
        lambda *args, **kwargs: calls.append("load_models_and_predict") or forecast,
    )
    monkeypatch.setattr(
        orchestration,
        "persist_next_day_forecast",
        lambda *args, **kwargs: calls.append("persist_forecast") or Path("forecast.json"),
    )

    result = forecast_company_from_artifacts(
        "ALI", records, calendar=PSETradingCalendar()
    )

    assert result.evaluation is evaluation
    assert result.next_day_forecast is forecast
    assert calls == ["load_evaluation", "load_models_and_predict", "persist_forecast"]


class FakeRunManager:
    instances: list["FakeRunManager"] = []

    def __init__(self) -> None:
        self.failed = None
        self.completed = None
        self.started = None
        self.instances.append(self)

    def start_run(self, **kwargs):
        self.started = kwargs
        return SimpleNamespace(run_id="run-test")

    def fail_run(self, run_id, errors):
        self.failed = (run_id, tuple(errors))

    def complete_run(self, run_id, *, completed_at):
        self.completed = (run_id, completed_at)


def test_train_cli_fresh_single_symbol_resets_and_completes_without_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = synthetic_records()
    reset_calls: list[bool] = []
    lifecycle_calls: list[str] = []
    FakeRunManager.instances.clear()
    monkeypatch.setattr(train_all, "ArtifactManager", FakeRunManager)
    monkeypatch.setattr(
        train_all,
        "reset_generated_artifacts",
        lambda: reset_calls.append(True),
    )
    monkeypatch.setattr(train_all, "load_company_history", lambda symbol: records)
    monkeypatch.setattr(
        train_all,
        "train_company_lifecycle",
        lambda symbol, history, *, calendar: lifecycle_calls.append(symbol)
        or SimpleNamespace(frontend_artifacts=object()),
    )

    status = train_all.main(["--symbol", "ALI", "--fresh", "--no-export"])

    manager = FakeRunManager.instances[-1]
    assert status == 0
    assert reset_calls == [True]
    assert lifecycle_calls == ["ALI"]
    assert manager.started["symbols_processed"] == ("ALI",)
    assert manager.completed[0] == "run-test"
    assert manager.failed is None


def test_train_and_forecast_cli_return_nonzero_on_company_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = synthetic_records()
    FakeRunManager.instances.clear()
    monkeypatch.setattr(train_all, "ArtifactManager", FakeRunManager)
    monkeypatch.setattr(train_all, "load_company_history", lambda symbol: records)
    monkeypatch.setattr(
        train_all,
        "train_company_lifecycle",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("model failed")),
    )
    assert train_all.main(["--symbol", "ALI", "--no-export"]) == 1
    assert FakeRunManager.instances[-1].failed[0] == "run-test"

    monkeypatch.setattr(forecast_all, "load_company_history", lambda symbol: records)
    monkeypatch.setattr(
        forecast_all,
        "forecast_company_from_artifacts",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("load failed")),
    )
    assert forecast_all.main(["--symbol", "ALI", "--no-export"]) == 1


def test_forecast_cli_classifies_operational_failure_and_never_exports(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    records = synthetic_records()
    exports: list[object] = []
    monkeypatch.setattr(forecast_all, "load_company_history", lambda symbol: records)
    monkeypatch.setattr(
        forecast_all,
        "forecast_company_from_artifacts",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OrchestrationError("artifact boundary mismatch")
        ),
    )
    monkeypatch.setattr(
        forecast_all,
        "export_frontend_forecasts",
        lambda bundle: exports.append(bundle),
    )

    with caplog.at_level("ERROR"):
        status = forecast_all.main(["--all"])

    assert status == 1
    assert exports == []
    matching = [
        record
        for record in caplog.records
        if "Operational persisted-model forecast rejected" in record.getMessage()
    ]
    assert matching
    assert all(record.exc_info is None for record in matching)


def test_forecast_cli_logs_unexpected_failure_with_traceback_and_never_exports(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    records = synthetic_records()
    exports: list[object] = []
    monkeypatch.setattr(forecast_all, "load_company_history", lambda symbol: records)
    monkeypatch.setattr(
        forecast_all,
        "forecast_company_from_artifacts",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("unexpected defect")
        ),
    )
    monkeypatch.setattr(
        forecast_all,
        "export_frontend_forecasts",
        lambda bundle: exports.append(bundle),
    )

    with caplog.at_level("ERROR"):
        status = forecast_all.main(["--all"])

    assert status == 1
    assert exports == []
    matching = [
        record
        for record in caplog.records
        if "Unexpected persisted-model forecasting failure" in record.getMessage()
    ]
    assert len(matching) == 1
    assert matching[0].exc_info is not None


def test_validate_raw_and_reset_cli_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = synthetic_records()
    monkeypatch.setattr(validate_raw, "load_company_history", lambda symbol: records)
    assert validate_raw.main(["--symbol", "ALI"]) == 0

    reset_calls: list[bool] = []
    directories = SimpleNamespace(
        all_generated_directories=lambda: tuple(
            Path(name) for name in ("models", "evaluations", "forecasts", "logs")
        )
    )
    monkeypatch.setattr(
        reset_artifacts,
        "reset_generated_artifacts",
        lambda: reset_calls.append(True) or directories,
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert reset_artifacts.main([]) == 2
    assert reset_calls == []
    assert reset_artifacts.main(["--yes"]) == 0
    assert reset_calls == [True]


@pytest.mark.parametrize(
    "script_name",
    ("validate_raw.py", "train_all.py", "forecast_all.py", "reset_artifacts.py"),
)
def test_phase_11_scripts_support_direct_execution(script_name: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / script_name), "--help"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_validate_raw_defaults_to_all_symbols_for_both_entry_styles() -> None:
    direct = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "validate_raw.py")],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    module = subprocess.run(
        [sys.executable, "-m", "scripts.validate_raw"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert direct.returncode == 0, direct.stderr
    assert module.returncode == 0, module.stderr
    assert "Raw validation summary symbols=15" in direct.stderr
    assert "failures=0" in direct.stderr
    assert "Raw validation summary symbols=15" in module.stderr
    assert "failures=0" in module.stderr


def test_single_symbol_export_is_rejected_to_protect_full_frontend_contract() -> None:
    with pytest.raises(SystemExit) as train_exit:
        train_all.main(["--symbol", "ALI"])
    with pytest.raises(SystemExit) as forecast_exit:
        forecast_all.main(["--symbol", "ALI"])
    assert train_exit.value.code == 2
    assert forecast_exit.value.code == 2
