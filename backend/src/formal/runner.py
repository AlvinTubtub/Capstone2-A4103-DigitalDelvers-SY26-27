"""Formal preflight and opt-in evaluation execution isolated from production."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
import logging
from pathlib import Path

from config.companies import COMPANIES, Company
from config.model_config import DEFAULT_MODEL_CONFIG, ModelConfig, ModelId
from config.settings import BACKEND_ROOT, SETTINGS
from src.data.split import build_company_evaluation_plan
from src.evaluation.evaluator import ModelPredictionOutput, evaluate_prediction_outputs
from src.evaluation.statistical_tests import compare_methods_across_companies
from src.features.regression_features import build_regression_dataset
from src.formal.archive import FormalRunArchive
from src.formal.provenance import load_corporate_action_registry, sha256_file
from src.formal.schema import FormalCompanyEvidence, FormalReadinessReport, FormalRunState
from src.formal.validation import (
    DEFAULT_CORPORATE_ACTIONS_PATH,
    DEFAULT_FORMAL_RUNS_ROOT,
    DEFAULT_PROVENANCE_PATH,
    assess_formal_readiness,
    read_raw_file,
)
from src.training.train_arima import train_arima_for_evaluation
from src.training.train_lir import train_lir_for_evaluation
from src.training.train_lstm import train_lstm_for_evaluation


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FormalRunRequest:
    run_id: str
    cutoff_date: date
    check_only: bool
    raw_data_dir: Path = SETTINGS.raw_data_dir
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT
    provenance_path: Path = DEFAULT_PROVENANCE_PATH
    corporate_actions_path: Path = DEFAULT_CORPORATE_ACTIONS_PATH
    repository_root: Path = BACKEND_ROOT.parent
    artifacts_root: Path = SETTINGS.artifacts_dir
    companies: tuple[Company, ...] = COMPANIES
    model_config: ModelConfig = DEFAULT_MODEL_CONFIG


@dataclass(frozen=True, slots=True)
class FormalExecutionResult:
    company_evidence: tuple[FormalCompanyEvidence, ...]
    across_company_statistics: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class FormalRunOutcome:
    readiness: FormalReadinessReport
    state: FormalRunState | None
    archive_path: Path | None
    integrity_manifest: Path | None

    def as_dict(self) -> dict[str, object]:
        return {
            "readiness": self.readiness.as_dict(),
            "state": self.state.value if self.state is not None else None,
            "archive_path": str(self.archive_path) if self.archive_path else None,
            "integrity_manifest": (
                str(self.integrity_manifest) if self.integrity_manifest else None
            ),
        }


ReadinessChecker = Callable[[FormalRunRequest], FormalReadinessReport]
ExperimentExecutor = Callable[[FormalRunRequest, FormalRunArchive], FormalExecutionResult]


def _default_readiness_checker(request: FormalRunRequest) -> FormalReadinessReport:
    return assess_formal_readiness(
        request.run_id,
        request.cutoff_date,
        companies=request.companies,
        raw_data_dir=request.raw_data_dir,
        formal_runs_root=request.formal_runs_root,
        provenance_path=request.provenance_path,
        corporate_actions_path=request.corporate_actions_path,
        repository_root=request.repository_root,
        model_config=request.model_config,
        artifacts_root=request.artifacts_root,
    )


def _dates_in_range(values: Sequence[date], start: date, end: date) -> list[str]:
    return [value.isoformat() for value in values if start <= value <= end]


def _cv_manifests(lir, arima, lstm, regression_dataset, records) -> dict[str, object]:
    lir_dates = tuple(sample.target_date for sample in regression_dataset.samples)
    lir_by_fold: dict[int, object] = {}
    for score in lir.tuning.fold_scores:
        if score.fold_index not in lir_by_fold:
            lir_by_fold[score.fold_index] = {
                "fold_index": score.fold_index,
                "training_target_dates": _dates_in_range(
                    lir_dates, score.train_start, score.train_end
                ),
                "validation_target_dates": _dates_in_range(
                    lir_dates, score.validation_start, score.validation_end
                ),
            }
    record_dates = tuple(record.trading_date for record in records)
    arima_by_fold = [
        {
            "fold_index": score.fold_index,
            "training_target_dates": _dates_in_range(
                record_dates, score.train_start, score.train_end
            ),
            "validation_target_dates": _dates_in_range(
                record_dates, score.validation_start, score.validation_end
            ),
        }
        for score in arima.tuning.selected_candidate.fold_scores
    ]
    selected_lstm = lstm.tuning.selected_candidate
    lstm_by_fold_seed = [
        {
            "fold_index": score.fold_index,
            "seed": score.seed,
            "outer_training_target_dates": [
                value.isoformat() for value in score.outer_training_target_dates
            ],
            "stopping_target_dates": [
                value.isoformat() for value in score.stopping_target_dates
            ],
            "validation_target_dates": [
                value.isoformat() for value in score.validation_target_dates
            ],
        }
        for score in selected_lstm.fold_seed_scores
    ]
    return {
        "lag_reg": [lir_by_fold[index] for index in sorted(lir_by_fold)],
        "arima": arima_by_fold,
        "lstm": lstm_by_fold_seed,
    }


def execute_formal_evaluation(
    request: FormalRunRequest,
    archive: FormalRunArchive,
) -> FormalExecutionResult:
    """Run evaluation only; never refit production models or export frontend data."""

    evidence: list[FormalCompanyEvidence] = []
    metrics_by_company = {}
    for company in request.companies:
        records, _ = read_raw_file(Path(request.raw_data_dir) / company.raw_filename)
        frozen_records = tuple(
            record for record in records if record.trading_date <= request.cutoff_date
        )
        plan = build_company_evaluation_plan(
            company.symbol,
            frozen_records,
            model_config=request.model_config,
        )
        dataset = build_regression_dataset(
            frozen_records,
            request.model_config.lag_regression.features,
        )
        archive.append_event("company_training_started", {"symbol": company.symbol})
        lir = train_lir_for_evaluation(
            dataset,
            plan,
            config=request.model_config.lag_regression,
        )
        arima = train_arima_for_evaluation(
            frozen_records,
            plan,
            config=request.model_config.arima,
        )
        lstm = train_lstm_for_evaluation(
            frozen_records,
            plan,
            config=request.model_config.lstm,
        )
        evaluation = evaluate_prediction_outputs(
            plan,
            (
                ModelPredictionOutput(
                    lir.symbol,
                    ModelId.LAG_REGRESSION,
                    lir.target_dates,
                    lir.actual_closes,
                    lir.predicted_closes,
                ),
                ModelPredictionOutput(
                    arima.symbol,
                    ModelId.ARIMA,
                    arima.target_dates,
                    arima.actual_closes,
                    arima.predicted_closes,
                ),
                ModelPredictionOutput(
                    lstm.symbol,
                    ModelId.LSTM,
                    lstm.target_dates,
                    lstm.actual_closes,
                    lstm.predicted_closes,
                ),
            ),
        )
        boundary = {
            **lir.tuning.alpha_grid_position.as_dict(),
            "chosen_alpha": lir.tuning.chosen_alpha,
            "resolution": None,
        }
        company_evidence = FormalCompanyEvidence(
            symbol=company.symbol,
            development_target_dates=plan.development_target_dates,
            holdout_target_dates=plan.evaluation_target_dates,
            cv_fold_target_date_manifests=_cv_manifests(
                lir, arima, lstm, dataset, frozen_records
            ),
            model_grids_and_seeds={
                "lag_reg": asdict(request.model_config.lag_regression),
                "arima": asdict(request.model_config.arima),
                "lstm": asdict(request.model_config.lstm),
            },
            tuning_and_fold_scores={
                "lag_reg": lir.tuning.as_dict(),
                "arima": arima.tuning.as_dict(),
                "lstm": lstm.tuning.as_dict(),
            },
            selected_configurations={
                "lag_reg": {
                    "alpha": lir.tuning.chosen_alpha,
                    "development_fit": lir.fitted.as_dict(),
                },
                "arima": {
                    **arima.tuning.selected_specification.as_dict(),
                    "adf_diagnostic": arima.adf_diagnostic.as_dict(),
                    "development_fit": arima.development_fit_metadata,
                },
                "lstm": lstm.tuning.selected_specification.as_dict(),
            },
            lasso_boundary_metadata=boundary,
            arima_diagnostics=arima.diagnostics.as_dict(),
            lstm_seed_epoch_metadata={
                "tuning_seeds": list(request.model_config.lstm.tuning_seeds),
                "final_seed": request.model_config.lstm.final_seed,
                "selected_epoch_count": lstm.fitted.epoch_count,
                "stage_a": lstm.epoch_selection.as_dict(),
                "stage_b": lstm.fitted.metadata(),
            },
            canonical_holdout_records=tuple(
                row.as_dict() for row in evaluation.aligned_holdout.rows
            ),
            metrics={
                model.value: evaluation.metrics_for(model).as_dict()
                for model in ModelId
            },
            statistical_tests={"diebold_mariano": evaluation.dm_tests.as_dict()},
        )
        evidence.append(company_evidence)
        metrics_by_company[company.symbol] = dict(evaluation.metrics_by_model)
        archive.append_event("company_training_completed", {"symbol": company.symbol})
    across = compare_methods_across_companies(metrics_by_company).as_dict()
    return FormalExecutionResult(tuple(evidence), across)


def _prepare_archive(
    request: FormalRunRequest,
    readiness: FormalReadinessReport,
) -> FormalRunArchive:
    archive = FormalRunArchive.create(
        request.run_id,
        request.cutoff_date,
        git_state=readiness.git_state,
        environment=readiness.environment,
        root=request.formal_runs_root,
        expected_symbols=tuple(company.symbol for company in request.companies),
    )
    archive.write_json(
        "configuration/model_config.json",
        {
            "schema_version": 1,
            "model_config": asdict(request.model_config),
        },
    )
    archive.write_json(
        "provenance/readiness.json",
        readiness.as_dict(),
    )
    archive.write_json(
        "provenance/raw_files.json",
        {"schema_version": 1, "raw_files": list(readiness.raw_provenance)},
    )
    archive.write_json(
        "provenance/session_completeness.json",
        {
            "schema_version": 1,
            "companies": [
                item.as_dict() for item in readiness.session_completeness
            ],
        },
    )
    actions = load_corporate_action_registry(request.corporate_actions_path)
    archive.write_json(
        "provenance/corporate_actions.json",
        {
            "schema_version": 1,
            "actions": [action.as_dict() for action in actions],
        },
    )
    provenance_by_symbol = {
        item["symbol"]: item for item in readiness.raw_provenance
    }
    for company in request.companies:
        source = Path(request.raw_data_dir) / company.raw_filename
        snapshot = archive.snapshot_raw_csv(company.symbol, source)
        if sha256_file(snapshot) != provenance_by_symbol[company.symbol]["sha256"]:
            raise RuntimeError(f"Raw CSV changed during freeze for {company.symbol}")
    return archive


def run_formal_experiment(
    request: FormalRunRequest,
    *,
    readiness_checker: ReadinessChecker = _default_readiness_checker,
    executor: ExperimentExecutor = execute_formal_evaluation,
) -> FormalRunOutcome:
    """Check readiness, then optionally execute into an isolated immutable archive."""

    readiness = readiness_checker(request)
    if request.check_only or not readiness.ready:
        return FormalRunOutcome(readiness, None, None, None)
    archive = _prepare_archive(request, readiness)
    try:
        result = executor(request, archive)
        evidence_by_symbol = {
            item.symbol: item for item in result.company_evidence
        }
        expected = {company.symbol for company in request.companies}
        if set(evidence_by_symbol) != expected:
            raise RuntimeError("Formal executor returned an incomplete company set")
        for symbol in sorted(evidence_by_symbol):
            archive.write_json(
                f"companies/{symbol}/evidence.json",
                evidence_by_symbol[symbol].as_dict(),
            )
        archive.write_json(
            "statistics/across_company.json",
            dict(result.across_company_statistics),
        )
        manifest = archive.finalize()
        LOGGER.info("Formal run finalized run_id=%s path=%s", request.run_id, archive.path)
        return FormalRunOutcome(readiness, FormalRunState.FINALIZED, archive.path, manifest)
    except Exception as exc:
        if archive.state is FormalRunState.IN_PROGRESS:
            archive.mark_failed([f"{type(exc).__name__}: {exc}"])
        LOGGER.exception("Formal run failed run_id=%s", request.run_id)
        return FormalRunOutcome(readiness, FormalRunState.FAILED, archive.path, None)
