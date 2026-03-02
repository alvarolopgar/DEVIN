"""
Credit scoring engine.

Implements a multi-factor credit scoring model that produces a composite
score (0-1000) based on payment history, credit utilization, credit
history length, credit mix, income stability, and debt-to-income ratio.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from credit_risk_engine.config.settings import ScoringWeights
from credit_risk_engine.domain.enums import RiskLevel
from credit_risk_engine.domain.models import Client
from credit_risk_engine.services.credit_position_analyzer import (
    CreditPositionAnalysisResult,
)
from credit_risk_engine.services.income_analyzer import IncomeAnalysisResult

logger = logging.getLogger(__name__)

_SCORE_MIN = 300
_SCORE_MAX = 1000
_SCORE_RANGE = _SCORE_MAX - _SCORE_MIN


@dataclass(frozen=True)
class ScoringResult:
    """Result of the credit scoring process."""

    composite_score: int  # 300-1000
    risk_level: RiskLevel
    component_scores: dict[str, float]  # Individual factor scores (0-1)
    score_breakdown: dict[str, int]  # Weighted contribution to final score


class CreditScoringEngine:
    """
    Multi-factor credit scoring engine.

    Produces a composite credit score (300-1000) by evaluating six
    weighted dimensions. The model is calibrated to produce realistic
    score distributions similar to standard credit bureau models.

    Args:
        weights: Scoring weights for each factor.
        score_excellent: Threshold for excellent credit.
        score_good: Threshold for good credit.
        score_fair: Threshold for fair credit.
        score_poor: Threshold for poor credit.
    """

    def __init__(
        self,
        weights: ScoringWeights,
        score_excellent: int = 800,
        score_good: int = 700,
        score_fair: int = 600,
        score_poor: int = 500,
    ) -> None:
        self._weights = weights
        self._thresholds = {
            "excellent": score_excellent,
            "good": score_good,
            "fair": score_fair,
            "poor": score_poor,
        }

    def score(
        self,
        client: Client,
        income_analysis: IncomeAnalysisResult,
        position_analysis: CreditPositionAnalysisResult,
        dti_ratio: float,
    ) -> ScoringResult:
        """
        Calculate the composite credit score for a client.

        Args:
            client: Client entity with demographic data.
            income_analysis: Results of income analysis.
            position_analysis: Results of credit position analysis.
            dti_ratio: Calculated debt-to-income ratio.

        Returns:
            Scoring result with composite score, risk level, and breakdown.
        """
        # Calculate individual component scores (0.0 to 1.0)
        components: dict[str, float] = {
            "payment_history": self._score_payment_history(position_analysis),
            "credit_utilization": self._score_utilization(position_analysis),
            "credit_history_length": self._score_history_length(client),
            "credit_mix": position_analysis.credit_mix_score,
            "income_stability": income_analysis.income_stability_score,
            "dti_ratio": self._score_dti(dti_ratio),
        }

        # Calculate weighted composite (0.0 to 1.0)
        weighted_total = (
            components["payment_history"] * self._weights.payment_history
            + components["credit_utilization"]
            * self._weights.credit_utilization
            + components["credit_history_length"]
            * self._weights.credit_history_length
            + components["credit_mix"] * self._weights.credit_mix
            + components["income_stability"] * self._weights.income_stability
            + components["dti_ratio"] * self._weights.dti_ratio
        )

        # Map to 300-1000 scale
        composite_score = int(_SCORE_MIN + weighted_total * _SCORE_RANGE)
        composite_score = max(_SCORE_MIN, min(_SCORE_MAX, composite_score))

        # Calculate individual weighted contributions
        breakdown: dict[str, int] = {}
        for factor, component_score in components.items():
            weight = getattr(self._weights, factor)
            breakdown[factor] = int(component_score * weight * _SCORE_RANGE)

        risk_level = self._classify_risk(composite_score)

        return ScoringResult(
            composite_score=composite_score,
            risk_level=risk_level,
            component_scores=components,
            score_breakdown=breakdown,
        )

    def _score_payment_history(
        self, analysis: CreditPositionAnalysisResult
    ) -> float:
        """
        Score payment history (0.0 to 1.0).

        Based on payment behavior score, with additional penalties
        for severe delinquency and defaults.
        """
        base_score = analysis.payment_behavior_score

        # Additional penalty for high DPD
        if analysis.max_days_past_due > 90:
            base_score *= 0.50
        elif analysis.max_days_past_due > 60:
            base_score *= 0.70
        elif analysis.max_days_past_due > 30:
            base_score *= 0.85

        return max(0.0, min(base_score, 1.0))

    @staticmethod
    def _score_utilization(
        analysis: CreditPositionAnalysisResult,
    ) -> float:
        """
        Score credit utilization (0.0 to 1.0).

        Optimal utilization is 10-30%. Higher utilization indicates
        higher risk; very low utilization (no usage) is neutral.
        """
        util = analysis.avg_utilization

        if analysis.num_active_positions == 0:
            return 0.7  # No credit positions: neutral

        # Sigmoid-based scoring for utilization
        if util <= 0.10:
            return 0.90  # Very low: good but slightly penalized
        elif util <= 0.30:
            return 1.0   # Optimal range
        elif util <= 0.50:
            return 0.85 - (util - 0.30) * 1.5
        elif util <= 0.75:
            return 0.55 - (util - 0.50) * 1.2
        else:
            return max(0.10, 0.25 - (util - 0.75) * 1.0)

    @staticmethod
    def _score_history_length(client: Client) -> float:
        """
        Score credit history length (0.0 to 1.0).

        Uses relationship years as a proxy. Longer history = higher score.
        Follows a logarithmic curve (diminishing returns after ~10 years).
        """
        years = client.relationship_years
        if years <= 0:
            return 0.1
        # Logarithmic scaling: ~0.5 at 2 years, ~0.8 at 7 years, ~1.0 at 15+
        score = min(1.0, 0.3 + 0.3 * math.log1p(years))
        return max(0.0, score)

    @staticmethod
    def _score_dti(dti_ratio: float) -> float:
        """
        Score debt-to-income ratio (0.0 to 1.0).

        DTI < 20%: excellent
        DTI 20-35%: good
        DTI 35-50%: concerning
        DTI > 50%: high risk
        """
        if dti_ratio <= 0.0:
            return 1.0  # No debt
        elif dti_ratio <= 0.20:
            return 1.0 - dti_ratio * 0.5
        elif dti_ratio <= 0.35:
            return 0.90 - (dti_ratio - 0.20) * 2.0
        elif dti_ratio <= 0.50:
            return 0.60 - (dti_ratio - 0.35) * 2.5
        elif dti_ratio <= 0.75:
            return 0.225 - (dti_ratio - 0.50) * 0.7
        else:
            return max(0.0, 0.05 - (dti_ratio - 0.75) * 0.2)

    def _classify_risk(self, score: int) -> RiskLevel:
        """Classify risk level based on composite credit score."""
        if score >= self._thresholds["excellent"]:
            return RiskLevel.VERY_LOW
        elif score >= self._thresholds["good"]:
            return RiskLevel.LOW
        elif score >= self._thresholds["fair"]:
            return RiskLevel.MEDIUM
        elif score >= self._thresholds["poor"]:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH
