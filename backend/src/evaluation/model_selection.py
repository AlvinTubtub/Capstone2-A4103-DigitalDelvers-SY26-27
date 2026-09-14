"""Deterministic company-level selection and scale-independent aggregation."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
import statistics
import warnings

from config.model_config import ModelId
from src.evaluation.metrics import EvaluationMetrics


PRINCIPAL_MODELS: tuple[ModelId, ...] = (
    ModelId.LAG_REGRESSION,
    ModelId.ARIMA,
    ModelId.LSTM,
)
EVALUATED_METHODS: tuple[ModelId, ...] = (*PRINCIPAL_MODELS, ModelId.NAIVE)
RMSE_TIE_POLICY = (
    "Exact RMSE ties are ordered deterministically as lag_reg, arima, lstm, naive. "
    "This order selects one reporting winner while preserving the tied metric values."
)
CROSS_COMPANY_TIE_POLICY = (
    "Cross-company ordering uses lowest median within-company RMSE rank, then lowest "
    "median MASE, then highest evaluated-method win count, then canonical model order."
)


class ModelSelectionError(ValueError):
    """Raised when evaluation metrics are incomplete or invalid."""


class PrincipalsUnderperformNaiveWarning(UserWarning):
    """Warn that Naive has lower RMSE than every principal model."""


@dataclass(frozen=True, slots=True)
class RankedModel:
    rank: int
    model: ModelId
    criterion: str
    value: float

    def as_dict(self) -> dict[str, int | str | float]:
        return {
            "rank": self.rank,
            "model": self.model.value,
            "criterion": self.criterion,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class ModelRanking:
    """A deterministic RMSE ranking for a declared model universe."""

    criterion: str
    ranked_models: tuple[RankedModel, ...]

    @property
    def best_model(self) -> ModelId:
        return self.ranked_models[0].model

    def as_dict(self) -> dict[str, object]:
        return {
            "criterion": self.criterion,
            "tie_policy": RMSE_TIE_POLICY,
            "best_model": self.best_model.value,
            "ranked_models": [model.as_dict() for model in self.ranked_models],
        }


@dataclass(frozen=True, slots=True)
class CompanyModelSelection:
    """Separate deployable-model and all-evaluated-method conclusions."""

    principal_ranking: ModelRanking
    evaluated_ranking: ModelRanking
    best_principal_beats_naive: bool
    all_principals_worse_than_naive: bool

    @property
    def best_principal_model(self) -> ModelId:
        return self.principal_ranking.best_model

    @property
    def best_evaluated_method(self) -> ModelId:
        return self.evaluated_ranking.best_model

    def as_dict(self) -> dict[str, object]:
        return {
            "best_principal_model": self.best_principal_model.value,
            "best_evaluated_method": self.best_evaluated_method.value,
            "best_principal_beats_naive": self.best_principal_beats_naive,
            "all_principals_worse_than_naive": self.all_principals_worse_than_naive,
            "tie_policy": RMSE_TIE_POLICY,
            "principal_ranking": self.principal_ranking.as_dict(),
            "evaluated_ranking": self.evaluated_ranking.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class CrossCompanyMethodSummary:
    """Scale-independent summaries for one method across companies."""

    model: ModelId
    median_mase: float
    median_rmse_rank: float
    principal_win_count: int
    evaluated_win_count: int
    beats_naive_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model.value,
            "median_mase": self.median_mase,
            "median_rmse_rank": self.median_rmse_rank,
            "principal_win_count": self.principal_win_count,
            "evaluated_win_count": self.evaluated_win_count,
            "beats_naive_count": self.beats_naive_count,
        }


@dataclass(frozen=True, slots=True)
class CrossCompanySummary:
    """Cross-company reporting that never pools raw peso errors for selection."""

    company_count: int
    methods: tuple[CrossCompanyMethodSummary, ...]
    ranked_methods: tuple[ModelId, ...]

    @property
    def best_method(self) -> ModelId:
        return self.ranked_methods[0]

    @property
    def worst_method(self) -> ModelId:
        return self.ranked_methods[-1]

    def for_model(self, model: ModelId) -> CrossCompanyMethodSummary:
        try:
            return next(summary for summary in self.methods if summary.model is model)
        except StopIteration as exc:
            raise ModelSelectionError(f"No cross-company summary for {model.value}") from exc

    def as_dict(self) -> dict[str, object]:
        return {
            "company_count": self.company_count,
            "selection_basis": (
                "median_within_company_rmse_rank_then_median_mase_then_"
                "evaluated_win_count"
            ),
            "tie_policy": CROSS_COMPANY_TIE_POLICY,
            "best_method": self.best_method.value,
            "worst_method": self.worst_method.value,
            "methods": {
                summary.model.value: summary.as_dict() for summary in self.methods
            },
        }


def _rank_models(
    metrics_by_model: Mapping[ModelId, EvaluationMetrics],
    models: tuple[ModelId, ...],
) -> ModelRanking:
    missing = [model.value for model in models if model not in metrics_by_model]
    if missing:
        raise ModelSelectionError(f"Missing model metrics: {missing}")
    values: dict[ModelId, float] = {}
    for model in models:
        value = float(metrics_by_model[model].rmse)
        if not math.isfinite(value):
            raise ModelSelectionError(f"Non-finite rmse for {model.value}")
        values[model] = value
    canonical_order = {model: index for index, model in enumerate(EVALUATED_METHODS)}
    ordered = sorted(models, key=lambda model: (values[model], canonical_order[model]))
    return ModelRanking(
        criterion="rmse",
        ranked_models=tuple(
            RankedModel(index, model, "rmse", values[model])
            for index, model in enumerate(ordered, start=1)
        ),
    )


def rank_principal_models(
    metrics_by_model: Mapping[ModelId, EvaluationMetrics],
    *,
    criterion: str = "rmse",
) -> ModelRanking:
    """Rank deployable principal models; winner selection is RMSE-only."""

    if criterion != "rmse":
        raise ModelSelectionError("Model winner selection criterion must be rmse")
    return _rank_models(metrics_by_model, PRINCIPAL_MODELS)


def rank_evaluated_methods(
    metrics_by_model: Mapping[ModelId, EvaluationMetrics],
    *,
    criterion: str = "rmse",
) -> ModelRanking:
    """Rank principal models and Naive together for evaluation reporting."""

    if criterion != "rmse":
        raise ModelSelectionError("Evaluated-method winner criterion must be rmse")
    return _rank_models(metrics_by_model, EVALUATED_METHODS)


def select_company_models(
    metrics_by_model: Mapping[ModelId, EvaluationMetrics],
    *,
    symbol: str | None = None,
) -> CompanyModelSelection:
    """Create separate principal and all-method conclusions using evaluation RMSE."""

    principal = rank_principal_models(metrics_by_model)
    evaluated = rank_evaluated_methods(metrics_by_model)
    naive_rmse = float(metrics_by_model[ModelId.NAIVE].rmse)
    principal_rmses = tuple(
        float(metrics_by_model[model].rmse) for model in PRINCIPAL_MODELS
    )
    best_principal_beats_naive = min(principal_rmses) < naive_rmse
    all_principals_worse = all(value > naive_rmse for value in principal_rmses)
    if all_principals_worse:
        scope = f" for {symbol}" if symbol else ""
        warnings.warn(
            "All three principal models have higher evaluation RMSE than the Naive "
            f"benchmark{scope}",
            PrincipalsUnderperformNaiveWarning,
            stacklevel=2,
        )
    return CompanyModelSelection(
        principal_ranking=principal,
        evaluated_ranking=evaluated,
        best_principal_beats_naive=best_principal_beats_naive,
        all_principals_worse_than_naive=all_principals_worse,
    )


def _average_rmse_ranks(
    metrics_by_model: Mapping[ModelId, EvaluationMetrics],
) -> dict[ModelId, float]:
    """Assign average ranks to exact RMSE ties without biasing aggregate ranks."""

    ranking = rank_evaluated_methods(metrics_by_model)
    ordered = tuple(item.model for item in ranking.ranked_models)
    values = {model: float(metrics_by_model[model].rmse) for model in ordered}
    ranks: dict[ModelId, float] = {}
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        for model in ordered[start:end]:
            ranks[model] = average_rank
        start = end
    return ranks


def summarize_cross_company_metrics(
    metrics_by_company: Mapping[str, Mapping[ModelId, EvaluationMetrics]],
) -> CrossCompanySummary:
    """Aggregate MASE, within-company RMSE ranks, wins, and Naive comparisons."""

    if not metrics_by_company:
        raise ModelSelectionError("Cross-company metrics cannot be empty")
    canonical_order = {model: index for index, model in enumerate(EVALUATED_METHODS)}
    mase_values = {model: [] for model in EVALUATED_METHODS}
    rank_values = {model: [] for model in EVALUATED_METHODS}
    principal_wins = {model: 0 for model in EVALUATED_METHODS}
    evaluated_wins = {model: 0 for model in EVALUATED_METHODS}
    beats_naive = {model: 0 for model in EVALUATED_METHODS}

    for symbol in sorted(metrics_by_company):
        metrics = metrics_by_company[symbol]
        principal = rank_principal_models(metrics).best_model
        evaluated = rank_evaluated_methods(metrics).best_model
        principal_wins[principal] += 1
        evaluated_wins[evaluated] += 1
        ranks = _average_rmse_ranks(metrics)
        naive_rmse = float(metrics[ModelId.NAIVE].rmse)
        for model in EVALUATED_METHODS:
            mase = float(metrics[model].mase)
            if not math.isfinite(mase):
                raise ModelSelectionError(f"Non-finite mase for {symbol}/{model.value}")
            mase_values[model].append(mase)
            rank_values[model].append(ranks[model])
            if model is not ModelId.NAIVE and float(metrics[model].rmse) < naive_rmse:
                beats_naive[model] += 1

    methods = tuple(
        CrossCompanyMethodSummary(
            model=model,
            median_mase=float(statistics.median(mase_values[model])),
            median_rmse_rank=float(statistics.median(rank_values[model])),
            principal_win_count=principal_wins[model],
            evaluated_win_count=evaluated_wins[model],
            beats_naive_count=beats_naive[model],
        )
        for model in EVALUATED_METHODS
    )
    by_model = {summary.model: summary for summary in methods}
    ranked_methods = tuple(
        sorted(
            EVALUATED_METHODS,
            key=lambda model: (
                by_model[model].median_rmse_rank,
                by_model[model].median_mase,
                -by_model[model].evaluated_win_count,
                canonical_order[model],
            ),
        )
    )
    return CrossCompanySummary(
        company_count=len(metrics_by_company),
        methods=methods,
        ranked_methods=ranked_methods,
    )
