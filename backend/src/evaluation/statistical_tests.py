"""Evaluation-only forecast-comparison tests on complete aligned holdouts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
import logging
import math
import warnings

import numpy as np
from scipy.stats import binomtest, friedmanchisquare, skew, t as student_t, wilcoxon

from config.model_config import ModelId
from src.evaluation.backtest import REQUIRED_EVALUATION_MODELS
from src.evaluation.holdout import CanonicalHoldout
from src.evaluation.metrics import EvaluationMetrics


LOGGER = logging.getLogger(__name__)
MODEL_PAIRS: tuple[tuple[ModelId, ModelId], ...] = (
    (ModelId.LAG_REGRESSION, ModelId.ARIMA),
    (ModelId.LAG_REGRESSION, ModelId.LSTM),
    (ModelId.LAG_REGRESSION, ModelId.NAIVE),
    (ModelId.ARIMA, ModelId.LSTM),
    (ModelId.ARIMA, ModelId.NAIVE),
    (ModelId.LSTM, ModelId.NAIVE),
)
HAC_LAG_POLICY = "floor(4*(n/100)^(2/9)), capped at n-1"


class StatisticalTestError(ValueError):
    """Raised when comparison inputs are incomplete or invalid."""


class LossType(StrEnum):
    SQUARED_ERROR = "squared_error"
    ABSOLUTE_ERROR = "absolute_error"


@dataclass(frozen=True, slots=True)
class DMTestResult:
    model_1: ModelId
    model_2: ModelId
    loss_type: LossType
    sample_size: int
    dm_statistic: float | None
    raw_p_value: float
    holm_adjusted_p_value: float
    reject: bool
    hac_lag: int
    forecast_horizon: int
    hln_correction_factor: float
    mean_loss_differential: float
    long_run_variance: float
    available: bool
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "model_pair": [self.model_1.value, self.model_2.value],
            "model_1": self.model_1.value,
            "model_2": self.model_2.value,
            "loss_type": self.loss_type.value,
            "sample_size": self.sample_size,
            "dm_statistic": self.dm_statistic,
            "raw_p_value": self.raw_p_value,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "reject": self.reject,
            "hac_lag": self.hac_lag,
            "forecast_horizon": self.forecast_horizon,
            "hln_correction_factor": self.hln_correction_factor,
            "mean_loss_differential": self.mean_loss_differential,
            "long_run_variance": self.long_run_variance,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class WithinCompanyDMTests:
    company: str
    alpha: float
    squared_error: tuple[DMTestResult, ...]
    absolute_error: tuple[DMTestResult, ...]

    @property
    def all_tests(self) -> tuple[DMTestResult, ...]:
        return self.squared_error + self.absolute_error

    def as_dict(self) -> dict[str, object]:
        return {
            "company": self.company,
            "alpha": self.alpha,
            "scope": "complete_aligned_evaluation",
            "hac_lag_policy": HAC_LAG_POLICY,
            "hln_small_sample_correction": True,
            "p_value_sidedness": "two_sided",
            "holm_families": {
                LossType.SQUARED_ERROR.value: [
                    result.as_dict() for result in self.squared_error
                ],
                LossType.ABSOLUTE_ERROR.value: [
                    result.as_dict() for result in self.absolute_error
                ],
            },
        }


@dataclass(frozen=True, slots=True)
class WilcoxonTestResult:
    model_1: ModelId
    model_2: ModelId
    sample_size: int
    statistic: float
    raw_p_value: float
    holm_adjusted_p_value: float
    reject: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "model_pair": [self.model_1.value, self.model_2.value],
            "model_1": self.model_1.value,
            "model_2": self.model_2.value,
            "sample_size": self.sample_size,
            "statistic": self.statistic,
            "raw_p_value": self.raw_p_value,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "reject": self.reject,
        }


@dataclass(frozen=True, slots=True)
class ConditionalWilcoxonEvidence:
    """Explicitly distinguish an executed post-hoc test from a gated test."""

    performed: bool
    sample_size: int | None
    statistic: float | None
    raw_p_value: float | None
    holm_adjusted_p_value: float | None
    reject: bool | None
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "performed": self.performed,
            "reason": self.reason,
            "statistic": self.statistic,
            "raw_p_value": self.raw_p_value,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "reject": self.reject,
            "sample_size": self.sample_size,
            "zero_method": "wilcox" if self.performed else None,
            "alternative": "two-sided" if self.performed else None,
        }


@dataclass(frozen=True, slots=True)
class SignTestEvidence:
    """Two-sided paired sign test, reported only as robustness evidence."""

    performed: bool
    sample_size: int
    positive_count: int
    negative_count: int
    zero_count: int
    statistic_proportion: float | None
    raw_p_value: float | None
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "performed": self.performed,
            "reason": self.reason,
            "sample_size": self.sample_size,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "zero_count": self.zero_count,
            "statistic_proportion": self.statistic_proportion,
            "raw_p_value": self.raw_p_value,
            "alternative": "two-sided",
            "null_probability": 0.5,
            "role": "supplementary_robustness_only",
        }


@dataclass(frozen=True, slots=True)
class PairedMaseEvidence:
    """Full-precision company-paired MASE differences for one method pair."""

    model_1: ModelId
    model_2: ModelId
    company_order: tuple[str, ...]
    model_1_mase: tuple[float, ...]
    model_2_mase: tuple[float, ...]
    paired_differences: tuple[float, ...]
    mean_difference: float
    median_difference: float
    standard_deviation: float
    skewness: float | None
    skewness_status: str
    positive_count: int
    negative_count: int
    zero_count: int
    wilcoxon: ConditionalWilcoxonEvidence
    sign_test: SignTestEvidence

    @property
    def observation_count(self) -> int:
        return len(self.company_order)

    def as_dict(self) -> dict[str, object]:
        return {
            "model_1": self.model_1.value,
            "model_2": self.model_2.value,
            "difference_direction": "model_1_mase_minus_model_2_mase",
            "company_order": list(self.company_order),
            "model_1_mase": list(self.model_1_mase),
            "model_2_mase": list(self.model_2_mase),
            "paired_differences": list(self.paired_differences),
            "observation_count": self.observation_count,
            "mean_difference": self.mean_difference,
            "median_difference": self.median_difference,
            "standard_deviation": self.standard_deviation,
            "standard_deviation_convention": "sample_ddof_1",
            "skewness": self.skewness,
            "skewness_status": self.skewness_status,
            "skewness_convention": "scipy_stats_skew_bias_false",
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "zero_count": self.zero_count,
            "wilcoxon": self.wilcoxon.as_dict(),
            "sign_test": self.sign_test.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class AcrossCompanyComparison:
    company_count: int
    metric: str
    alpha: float
    friedman_statistic: float
    friedman_p_value: float
    friedman_reject: bool
    posthoc_performed: bool
    pairwise_wilcoxon: tuple[WilcoxonTestResult, ...]
    paired_mase_evidence: tuple[PairedMaseEvidence, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "company_count": self.company_count,
            "metric": self.metric,
            "models": [model.value for model in REQUIRED_EVALUATION_MODELS],
            "alpha": self.alpha,
            "friedman": {
                "statistic": self.friedman_statistic,
                "raw_p_value": self.friedman_p_value,
                "reject": self.friedman_reject,
            },
            "posthoc_performed": self.posthoc_performed,
            "posthoc_correction": "holm" if self.posthoc_performed else None,
            "pairwise_wilcoxon": [
                result.as_dict() for result in self.pairwise_wilcoxon
            ],
        }

    def paired_evidence_as_dict(self) -> dict[str, object]:
        """Serialize supplementary evidence without changing the legacy result schema."""

        return {
            "schema_id": "forecastph.supplementary-paired-mase-evidence",
            "schema_version": 1,
            "metric": "mase",
            "company_count": self.company_count,
            "alpha": self.alpha,
            "friedman": {
                "statistic": self.friedman_statistic,
                "raw_p_value": self.friedman_p_value,
                "reject": self.friedman_reject,
            },
            "wilcoxon_gate": "performed_only_when_friedman_rejects",
            "wilcoxon_holm_family_size": len(MODEL_PAIRS),
            "sign_test_holm_corrected": False,
            "pairs": [item.as_dict() for item in self.paired_mase_evidence],
        }


def automatic_hac_lag(sample_size: int) -> int:
    """Return the documented Newey-West automatic lag for a sample size."""

    if sample_size < 1:
        raise StatisticalTestError("HAC sample size must be positive")
    proposed = math.floor(4.0 * (sample_size / 100.0) ** (2.0 / 9.0))
    return min(max(proposed, 0), sample_size - 1)


def newey_west_long_run_variance(
    values: Sequence[float],
    *,
    max_lag: int | None = None,
) -> tuple[float, int]:
    """Estimate long-run variance using Bartlett-weighted autocovariances."""

    vector = np.asarray(values, dtype=np.float64).reshape(-1)
    if vector.size < 1 or not np.isfinite(vector).all():
        raise StatisticalTestError("HAC values must be non-empty and finite")
    lag = automatic_hac_lag(int(vector.size)) if max_lag is None else max_lag
    if isinstance(lag, bool) or not isinstance(lag, int) or not 0 <= lag < vector.size:
        raise StatisticalTestError("HAC lag must be an integer from 0 through n-1")
    centered = vector - float(np.mean(vector))
    sample_size = int(vector.size)
    long_run_variance = float(np.dot(centered, centered) / sample_size)
    for offset in range(1, lag + 1):
        autocovariance = float(
            np.dot(centered[offset:], centered[:-offset]) / sample_size
        )
        bartlett_weight = 1.0 - offset / (lag + 1.0)
        long_run_variance += 2.0 * bartlett_weight * autocovariance
    return long_run_variance, lag


def _loss(errors: Sequence[float], loss_type: LossType) -> np.ndarray:
    vector = np.asarray(errors, dtype=np.float64).reshape(-1)
    if not np.isfinite(vector).all():
        raise StatisticalTestError("DM errors must all be finite")
    if loss_type is LossType.SQUARED_ERROR:
        return np.square(vector)
    return np.abs(vector)


def diebold_mariano_test(
    holdout: CanonicalHoldout,
    model_1: ModelId,
    model_2: ModelId,
    *,
    loss_type: LossType,
    alpha: float = 0.05,
    forecast_horizon: int = 1,
    hac_lag: int | None = None,
) -> DMTestResult:
    """Run a two-sided HLN-corrected DM test on aligned forecast losses."""

    if model_1 is model_2:
        raise StatisticalTestError("DM requires two distinct methods")
    if not 0.0 < alpha < 1.0:
        raise StatisticalTestError("DM alpha must be between zero and one")
    sample_size = len(holdout.rows)
    if not 1 <= forecast_horizon <= sample_size:
        raise StatisticalTestError("DM forecast horizon is invalid")
    differential = _loss(holdout.errors(model_1), loss_type) - _loss(
        holdout.errors(model_2), loss_type
    )
    mean_differential = float(np.mean(differential))
    long_run_variance, selected_lag = newey_west_long_run_variance(
        differential,
        max_lag=hac_lag,
    )
    hln_term = (
        sample_size
        + 1
        - 2 * forecast_horizon
        + forecast_horizon * (forecast_horizon - 1) / sample_size
    ) / sample_size
    hln_factor = math.sqrt(max(hln_term, 0.0))
    variance_tolerance = (
        np.finfo(np.float64).eps
        * max(1.0, float(np.mean(np.square(differential))))
        * 100.0
    )
    if sample_size < 3 or long_run_variance <= variance_tolerance:
        return DMTestResult(
            model_1=model_1,
            model_2=model_2,
            loss_type=loss_type,
            sample_size=sample_size,
            dm_statistic=None,
            raw_p_value=1.0,
            holm_adjusted_p_value=1.0,
            reject=False,
            hac_lag=selected_lag,
            forecast_horizon=forecast_horizon,
            hln_correction_factor=hln_factor,
            mean_loss_differential=mean_differential,
            long_run_variance=long_run_variance,
            available=False,
            unavailable_reason=(
                "fewer than three observations"
                if sample_size < 3
                else "zero or degenerate HAC long-run variance"
            ),
        )
    uncorrected = mean_differential / math.sqrt(long_run_variance / sample_size)
    statistic = float(uncorrected * hln_factor)
    raw_p_value = float(
        2.0 * student_t.sf(abs(statistic), df=sample_size - 1)
    )
    return DMTestResult(
        model_1=model_1,
        model_2=model_2,
        loss_type=loss_type,
        sample_size=sample_size,
        dm_statistic=statistic,
        raw_p_value=raw_p_value,
        holm_adjusted_p_value=raw_p_value,
        reject=raw_p_value <= alpha,
        hac_lag=selected_lag,
        forecast_horizon=forecast_horizon,
        hln_correction_factor=hln_factor,
        mean_loss_differential=mean_differential,
        long_run_variance=long_run_variance,
        available=True,
    )


def _holm_adjust_dm(
    results: Sequence[DMTestResult],
    *,
    alpha: float,
) -> tuple[DMTestResult, ...]:
    ordered_indices = sorted(
        range(len(results)), key=lambda index: (results[index].raw_p_value, index)
    )
    adjusted = [1.0] * len(results)
    running_max = 0.0
    family_size = len(results)
    for position, index in enumerate(ordered_indices):
        candidate = min(1.0, (family_size - position) * results[index].raw_p_value)
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return tuple(
        replace(
            result,
            holm_adjusted_p_value=adjusted[index],
            reject=result.available and adjusted[index] <= alpha,
        )
        for index, result in enumerate(results)
    )


def run_within_company_dm_tests(
    holdout: CanonicalHoldout,
    *,
    alpha: float = 0.05,
    forecast_horizon: int = 1,
) -> WithinCompanyDMTests:
    """Run and separately Holm-correct both six-comparison DM families."""

    families: dict[LossType, tuple[DMTestResult, ...]] = {}
    for loss_type in LossType:
        raw = tuple(
            diebold_mariano_test(
                holdout,
                model_1,
                model_2,
                loss_type=loss_type,
                alpha=alpha,
                forecast_horizon=forecast_horizon,
            )
            for model_1, model_2 in MODEL_PAIRS
        )
        families[loss_type] = _holm_adjust_dm(raw, alpha=alpha)
    LOGGER.info(
        "Completed within-company DM tests company=%s observations=%d tests=12",
        holdout.company,
        len(holdout.rows),
    )
    return WithinCompanyDMTests(
        company=holdout.company,
        alpha=alpha,
        squared_error=families[LossType.SQUARED_ERROR],
        absolute_error=families[LossType.ABSOLUTE_ERROR],
    )


def _holm_adjust_wilcoxon(
    results: Sequence[WilcoxonTestResult],
    *,
    alpha: float,
) -> tuple[WilcoxonTestResult, ...]:
    ordered_indices = sorted(
        range(len(results)), key=lambda index: (results[index].raw_p_value, index)
    )
    adjusted = [1.0] * len(results)
    running_max = 0.0
    family_size = len(results)
    for position, index in enumerate(ordered_indices):
        candidate = min(1.0, (family_size - position) * results[index].raw_p_value)
        running_max = max(running_max, candidate)
        adjusted[index] = running_max
    return tuple(
        replace(
            result,
            holm_adjusted_p_value=adjusted[index],
            reject=adjusted[index] <= alpha,
        )
        for index, result in enumerate(results)
    )


def _sign_test_evidence(differences: np.ndarray) -> SignTestEvidence:
    positive_count = int(np.count_nonzero(differences > 0.0))
    negative_count = int(np.count_nonzero(differences < 0.0))
    zero_count = int(np.count_nonzero(differences == 0.0))
    sample_size = positive_count + negative_count
    if sample_size == 0:
        return SignTestEvidence(
            performed=False,
            sample_size=0,
            positive_count=positive_count,
            negative_count=negative_count,
            zero_count=zero_count,
            statistic_proportion=None,
            raw_p_value=None,
            reason="no_nonzero_paired_differences",
        )
    result = binomtest(
        k=positive_count,
        n=sample_size,
        p=0.5,
        alternative="two-sided",
    )
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if not math.isfinite(statistic) or not math.isfinite(p_value):
        raise StatisticalTestError("Sign test produced a non-finite result")
    return SignTestEvidence(
        performed=True,
        sample_size=sample_size,
        positive_count=positive_count,
        negative_count=negative_count,
        zero_count=zero_count,
        statistic_proportion=statistic,
        raw_p_value=p_value,
    )


def _paired_mase_evidence(
    *,
    companies: tuple[str, ...],
    values: Mapping[ModelId, np.ndarray],
    wilcoxon_by_pair: Mapping[tuple[ModelId, ModelId], WilcoxonTestResult],
    friedman_reject: bool,
) -> tuple[PairedMaseEvidence, ...]:
    evidence: list[PairedMaseEvidence] = []
    for model_1, model_2 in MODEL_PAIRS:
        left = values[model_1]
        right = values[model_2]
        differences = left - right
        if differences.size != len(companies) or not np.isfinite(differences).all():
            raise StatisticalTestError("Paired MASE differences are incomplete or non-finite")
        standard_deviation = float(np.std(differences, ddof=1))
        if not math.isfinite(standard_deviation):
            raise StatisticalTestError("Paired MASE standard deviation is non-finite")
        if standard_deviation == 0.0:
            skewness_value = None
            skewness_status = "undefined_constant_differences"
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                computed_skewness = float(skew(differences, bias=False))
            if math.isfinite(computed_skewness):
                skewness_value = computed_skewness
                skewness_status = "available"
            else:
                skewness_value = None
                skewness_status = "undefined_numerical_result"

        if friedman_reject:
            result = wilcoxon_by_pair[(model_1, model_2)]
            wilcoxon_evidence = ConditionalWilcoxonEvidence(
                performed=True,
                sample_size=result.sample_size,
                statistic=result.statistic,
                raw_p_value=result.raw_p_value,
                holm_adjusted_p_value=result.holm_adjusted_p_value,
                reject=result.reject,
            )
        else:
            wilcoxon_evidence = ConditionalWilcoxonEvidence(
                performed=False,
                sample_size=None,
                statistic=None,
                raw_p_value=None,
                holm_adjusted_p_value=None,
                reject=None,
                reason="friedman_not_significant",
            )
        sign_test = _sign_test_evidence(differences)
        evidence.append(
            PairedMaseEvidence(
                model_1=model_1,
                model_2=model_2,
                company_order=companies,
                model_1_mase=tuple(float(value) for value in left),
                model_2_mase=tuple(float(value) for value in right),
                paired_differences=tuple(float(value) for value in differences),
                mean_difference=float(np.mean(differences)),
                median_difference=float(np.median(differences)),
                standard_deviation=standard_deviation,
                skewness=skewness_value,
                skewness_status=skewness_status,
                positive_count=sign_test.positive_count,
                negative_count=sign_test.negative_count,
                zero_count=sign_test.zero_count,
                wilcoxon=wilcoxon_evidence,
                sign_test=sign_test,
            )
        )
    return tuple(evidence)


def compare_methods_across_companies(
    metrics_by_company: Mapping[str, Mapping[ModelId, EvaluationMetrics]],
    *,
    alpha: float = 0.05,
) -> AcrossCompanyComparison:
    """Use company-paired MASE values for Friedman and conditional Wilcoxon tests."""

    if len(metrics_by_company) < 2:
        raise StatisticalTestError("Across-company comparison requires two companies")
    if not 0.0 < alpha < 1.0:
        raise StatisticalTestError("Across-company alpha must be between zero and one")
    companies = tuple(sorted(metrics_by_company))
    values: dict[ModelId, np.ndarray] = {}
    for model in REQUIRED_EVALUATION_MODELS:
        try:
            vector = np.asarray(
                [metrics_by_company[symbol][model].mase for symbol in companies],
                dtype=np.float64,
            )
        except KeyError as exc:
            raise StatisticalTestError(
                f"Missing MASE input for {model.value}"
            ) from exc
        if not np.isfinite(vector).all():
            raise StatisticalTestError(f"Non-finite MASE input for {model.value}")
        values[model] = vector

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        friedman = friedmanchisquare(
            *(values[model] for model in REQUIRED_EVALUATION_MODELS)
        )
    friedman_statistic = float(friedman.statistic)
    friedman_p_value = float(friedman.pvalue)
    if not math.isfinite(friedman_statistic) or not math.isfinite(friedman_p_value):
        friedman_statistic = 0.0
        friedman_p_value = 1.0
    friedman_reject = friedman_p_value <= alpha
    pairwise: tuple[WilcoxonTestResult, ...] = ()
    if friedman_reject:
        raw_results: list[WilcoxonTestResult] = []
        for model_1, model_2 in MODEL_PAIRS:
            left = values[model_1]
            right = values[model_2]
            if np.array_equal(left, right):
                statistic, raw_p_value = 0.0, 1.0
            else:
                result = wilcoxon(
                    left,
                    right,
                    zero_method="wilcox",
                    alternative="two-sided",
                    method="auto",
                )
                statistic = float(result.statistic)
                raw_p_value = float(result.pvalue)
            raw_results.append(
                WilcoxonTestResult(
                    model_1=model_1,
                    model_2=model_2,
                    sample_size=len(companies),
                    statistic=statistic,
                    raw_p_value=raw_p_value,
                    holm_adjusted_p_value=raw_p_value,
                    reject=raw_p_value <= alpha,
                )
            )
        pairwise = _holm_adjust_wilcoxon(raw_results, alpha=alpha)
    wilcoxon_by_pair = {
        (result.model_1, result.model_2): result for result in pairwise
    }
    paired_evidence = _paired_mase_evidence(
        companies=companies,
        values=values,
        wilcoxon_by_pair=wilcoxon_by_pair,
        friedman_reject=friedman_reject,
    )
    LOGGER.info(
        "Completed across-company MASE comparison companies=%d friedman_p=%.8g posthoc=%s",
        len(companies),
        friedman_p_value,
        friedman_reject,
    )
    return AcrossCompanyComparison(
        company_count=len(companies),
        metric="mase",
        alpha=alpha,
        friedman_statistic=friedman_statistic,
        friedman_p_value=friedman_p_value,
        friedman_reject=friedman_reject,
        posthoc_performed=friedman_reject,
        pairwise_wilcoxon=pairwise,
        paired_mase_evidence=paired_evidence,
    )
