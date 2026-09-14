"""Unified dynamic company evaluation for all principal models and naive."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import json
import logging

from config.model_config import DEFAULT_MODEL_CONFIG, ModelConfig, ModelId
from src.data.loader import load_company_history
from src.data.split import CompanyEvaluationPlan, build_company_evaluation_plan
from src.data.validator import OhlcvRecord, require_chronological_records
from src.evaluation.backtest import (
    BacktestAlignmentError,
    BacktestData,
    CanonicalPrediction,
    align_backtest_records,
    canonical_records_from_arrays,
    naive_prediction_records,
)
from src.evaluation.metrics import (
    EvaluationMetrics,
    compute_evaluation_metrics,
    compute_mase_denominator,
)
from src.evaluation.holdout import CanonicalHoldout, aligned_holdout_from_backtest
from src.evaluation.model_selection import (
    CompanyModelSelection,
    ModelRanking,
    rank_evaluated_methods,
    select_company_models,
)
from src.evaluation.statistical_tests import (
    WithinCompanyDMTests,
    run_within_company_dm_tests,
)
from src.features.regression_features import build_regression_dataset
from src.training.train_arima import train_arima_for_evaluation
from src.training.train_lir import train_lir_for_evaluation
from src.training.train_lstm import train_lstm_for_evaluation


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModelPredictionOutput:
    """Minimal dated OOS output adapted from one development-fit evaluation."""

    symbol: str
    model: ModelId
    target_dates: tuple[date, ...]
    actual_closes: tuple[float, ...]
    predicted_closes: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CompanyEvaluation:
    """Aligned records, shared MASE scale, and distinct evaluation conclusions."""

    symbol: str
    plan: CompanyEvaluationPlan
    mase_denominator: float
    backtest: BacktestData
    metrics_by_model: tuple[tuple[ModelId, EvaluationMetrics], ...]
    principal_ranking: ModelRanking

    def metrics_for(self, model: ModelId) -> EvaluationMetrics:
        try:
            return dict(self.metrics_by_model)[model]
        except KeyError as exc:
            raise BacktestAlignmentError(f"No metrics for model {model.value}") from exc

    @property
    def evaluated_ranking(self) -> ModelRanking:
        """Rank all evaluated methods, including Naive, by company RMSE."""

        return rank_evaluated_methods(dict(self.metrics_by_model))

    @property
    def aligned_holdout(self) -> CanonicalHoldout:
        """Expose one complete date-keyed row per OOS target date."""

        return aligned_holdout_from_backtest(self.backtest)

    @property
    def dm_tests(self) -> WithinCompanyDMTests:
        """Compute reporting-only DM evidence from the complete aligned holdout."""

        return run_within_company_dm_tests(self.aligned_holdout)

    @property
    def best_principal_beats_naive(self) -> bool:
        """Use a strict RMSE comparison; an exact tie is not a win."""

        return (
            self.metrics_for(self.principal_ranking.best_model).rmse
            < self.metrics_for(ModelId.NAIVE).rmse
        )

    @property
    def all_principals_worse_than_naive(self) -> bool:
        """Return true only when Naive has strictly lower RMSE than all principals."""

        naive_rmse = self.metrics_for(ModelId.NAIVE).rmse
        return all(
            self.metrics_for(model).rmse > naive_rmse
            for model in (
                ModelId.LAG_REGRESSION,
                ModelId.ARIMA,
                ModelId.LSTM,
            )
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "split": {
                "evaluation_proportion": self.plan.evaluation_proportion,
                "development_pairs": len(self.plan.development_pairs),
                "evaluation_pairs": len(self.plan.evaluation_pairs),
                "evaluation_start": self.plan.evaluation_target_dates[0].isoformat(),
                "evaluation_end": self.plan.evaluation_target_dates[-1].isoformat(),
            },
            "mase_denominator": self.mase_denominator,
            "metrics": {
                model.value: metrics.as_dict()
                for model, metrics in self.metrics_by_model
            },
            "best_principal_model": self.principal_ranking.best_model.value,
            "best_evaluated_method": self.evaluated_ranking.best_model.value,
            "best_principal_beats_naive": self.best_principal_beats_naive,
            "all_principals_worse_than_naive": self.all_principals_worse_than_naive,
            "principal_ranking": self.principal_ranking.as_dict(),
            "evaluated_ranking": self.evaluated_ranking.as_dict(),
            "backtest": self.backtest.as_dict(),
            "aligned_holdout": self.aligned_holdout.as_dict(),
            "statistical_tests": {
                "diebold_mariano": self.dm_tests.as_dict(),
            },
        }

    def to_json(self) -> str:
        """Serialize full native precision without NaN or display rounding."""

        return json.dumps(
            self.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def development_close_series(plan: CompanyEvaluationPlan) -> tuple[float, ...]:
    """Reconstruct unique development Close levels from the common pair plan."""

    return (plan.development_pairs[0].origin_close,) + tuple(
        pair.actual_close for pair in plan.development_pairs
    )


def evaluate_prediction_outputs(
    plan: CompanyEvaluationPlan,
    outputs: Sequence[ModelPredictionOutput],
) -> CompanyEvaluation:
    """Align principal OOS outputs, add naive, and compute shared-scale metrics."""

    supplied: dict[ModelId, ModelPredictionOutput] = {}
    for output in outputs:
        if output.model is ModelId.NAIVE:
            raise BacktestAlignmentError("Naive predictions are generated canonically")
        if output.model in supplied:
            raise BacktestAlignmentError(f"Duplicate output for model {output.model.value}")
        if output.symbol != plan.symbol:
            raise BacktestAlignmentError("Model output symbol differs from evaluation plan")
        supplied[output.model] = output
    required_principal = {
        ModelId.LAG_REGRESSION,
        ModelId.ARIMA,
        ModelId.LSTM,
    }
    if set(supplied) != required_principal:
        missing = sorted(model.value for model in required_principal - set(supplied))
        extra = sorted(model.value for model in set(supplied) - required_principal)
        raise BacktestAlignmentError(
            f"Principal model-set mismatch; missing={missing} extra={extra}"
        )

    records: dict[ModelId, tuple[CanonicalPrediction, ...]] = {}
    for model in (ModelId.LAG_REGRESSION, ModelId.ARIMA, ModelId.LSTM):
        output = supplied[model]
        records[model] = canonical_records_from_arrays(
            plan,
            model=model,
            target_dates=output.target_dates,
            actual_closes=output.actual_closes,
            predicted_closes=output.predicted_closes,
        )
    records[ModelId.NAIVE] = naive_prediction_records(plan)
    backtest = align_backtest_records(plan, records)
    mase_denominator = compute_mase_denominator(development_close_series(plan))
    metrics = tuple(
        (
            model,
            compute_evaluation_metrics(
                backtest.actual_closes,
                backtest.predicted_closes(model),
                mase_denominator=mase_denominator,
            ),
        )
        for model in (
            ModelId.LAG_REGRESSION,
            ModelId.ARIMA,
            ModelId.LSTM,
            ModelId.NAIVE,
        )
    )
    selection: CompanyModelSelection = select_company_models(
        dict(metrics),
        symbol=plan.symbol,
    )
    if selection.all_principals_worse_than_naive:
        LOGGER.warning(
            "All principal models underperform Naive by evaluation RMSE symbol=%s",
            plan.symbol,
        )
    LOGGER.info(
        "Completed unified evaluation symbol=%s dates=%d mase_scale=%.10g "
        "best_principal=%s best_evaluated=%s beats_naive=%s",
        plan.symbol,
        len(plan.evaluation_pairs),
        mase_denominator,
        selection.best_principal_model.value,
        selection.best_evaluated_method.value,
        selection.best_principal_beats_naive,
    )
    return CompanyEvaluation(
        symbol=plan.symbol,
        plan=plan,
        mase_denominator=mase_denominator,
        backtest=backtest,
        metrics_by_model=metrics,
        principal_ranking=selection.principal_ranking,
    )


def evaluate_company(
    symbol: str,
    records: Sequence[OhlcvRecord] | None = None,
    *,
    model_config: ModelConfig = DEFAULT_MODEL_CONFIG,
) -> CompanyEvaluation:
    """Build a current-data split, fit development models, and evaluate OOS only."""

    source_records = (
        load_company_history(symbol) if records is None else tuple(records)
    )
    require_chronological_records(source_records)
    plan = build_company_evaluation_plan(
        symbol,
        source_records,
        model_config=model_config,
    )
    LOGGER.info(
        "Starting unified company evaluation symbol=%s development=%d evaluation=%d",
        plan.symbol,
        len(plan.development_pairs),
        len(plan.evaluation_pairs),
    )
    regression_dataset = build_regression_dataset(
        source_records,
        model_config.lag_regression.features,
    )
    lir = train_lir_for_evaluation(
        regression_dataset,
        plan,
        config=model_config.lag_regression,
    )
    arima = train_arima_for_evaluation(
        source_records,
        plan,
        config=model_config.arima,
    )
    lstm = train_lstm_for_evaluation(
        source_records,
        plan,
        config=model_config.lstm,
    )
    return evaluate_prediction_outputs(
        plan,
        (
            ModelPredictionOutput(
                symbol=lir.symbol,
                model=ModelId.LAG_REGRESSION,
                target_dates=lir.target_dates,
                actual_closes=lir.actual_closes,
                predicted_closes=lir.predicted_closes,
            ),
            ModelPredictionOutput(
                symbol=arima.symbol,
                model=ModelId.ARIMA,
                target_dates=arima.target_dates,
                actual_closes=arima.actual_closes,
                predicted_closes=arima.predicted_closes,
            ),
            ModelPredictionOutput(
                symbol=lstm.symbol,
                model=ModelId.LSTM,
                target_dates=lstm.target_dates,
                actual_closes=lstm.actual_closes,
                predicted_closes=lstm.predicted_closes,
            ),
        ),
    )
