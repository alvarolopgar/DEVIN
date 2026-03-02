"""
Credit position analysis service.

Analyzes a client's credit positions to assess debt burden,
utilization patterns, payment behavior, and exposure metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from credit_risk_engine.domain.enums import (
    PaymentStatus,
)
from credit_risk_engine.domain.models import CreditPosition

logger = logging.getLogger(__name__)

# Payment statuses considered delinquent
_DELINQUENT_STATUSES = frozenset(
    {
        PaymentStatus.DAYS_30,
        PaymentStatus.DAYS_60,
        PaymentStatus.DAYS_90,
        PaymentStatus.DAYS_120_PLUS,
        PaymentStatus.DEFAULT,
    }
)


@dataclass(frozen=True)
class CreditPositionAnalysisResult:
    """Aggregated result of credit position analysis for a client."""

    total_monthly_debt: float
    total_outstanding_balance: float
    total_credit_limit: float
    weighted_avg_interest_rate: float
    avg_utilization: float
    max_utilization: float
    num_active_positions: int
    num_delinquent_positions: int
    num_secured_positions: int
    has_restructured_debt: bool
    worst_payment_status: PaymentStatus
    max_days_past_due: int
    total_late_payments_12m: int
    total_late_payments_lifetime: int
    product_type_count: dict[str, int]
    total_collateral_value: float
    weighted_avg_remaining_term: float
    payment_behavior_score: float  # 0.0 to 1.0
    credit_mix_score: float  # 0.0 to 1.0


class CreditPositionAnalyzer:
    """
    Analyzes credit positions to assess debt burden and payment behavior.

    Evaluates:
    - Total debt obligations and monthly payments
    - Credit utilization ratios
    - Payment history and delinquency patterns
    - Product diversification
    - Collateral coverage
    """

    # Payment status severity ordering for worst-status determination
    _STATUS_SEVERITY: dict[PaymentStatus, int] = {
        PaymentStatus.CURRENT: 0,
        PaymentStatus.RESTRUCTURED: 1,
        PaymentStatus.DAYS_30: 2,
        PaymentStatus.DAYS_60: 3,
        PaymentStatus.DAYS_90: 4,
        PaymentStatus.DAYS_120_PLUS: 5,
        PaymentStatus.DEFAULT: 6,
    }

    def analyze(
        self, positions: list[CreditPosition]
    ) -> CreditPositionAnalysisResult:
        """
        Perform comprehensive analysis of a client's credit positions.

        Args:
            positions: All credit positions for the client.

        Returns:
            Structured analysis result with all computed metrics.
        """
        if not positions:
            return self._empty_result()

        total_monthly_debt = sum(p.monthly_payment for p in positions)
        total_outstanding = sum(p.outstanding_balance for p in positions)
        total_limit = sum(p.credit_limit for p in positions)

        # Weighted average interest rate (by outstanding balance)
        wavg_rate = self._weighted_avg_rate(positions)

        # Utilization metrics
        utilizations = [p.utilization_ratio for p in positions]
        avg_utilization = (
            sum(utilizations) / len(utilizations) if utilizations else 0.0
        )
        max_utilization = max(utilizations) if utilizations else 0.0

        # Delinquency metrics
        delinquent = [
            p for p in positions if p.payment_status in _DELINQUENT_STATUSES
        ]
        worst_status = self._determine_worst_status(positions)
        max_dpd = max((p.days_past_due for p in positions), default=0)
        total_late_12m = sum(p.num_late_payments_12m for p in positions)
        total_late_life = sum(p.num_late_payments_lifetime for p in positions)

        # Secured positions
        secured = [p for p in positions if p.is_secured]
        total_collateral = sum(p.collateral_value for p in secured)

        # Restructured debt
        has_restructured = any(p.restructured for p in positions)

        # Product mix
        product_counts: dict[str, int] = {}
        for p in positions:
            key = p.product_type.value
            product_counts[key] = product_counts.get(key, 0) + 1

        # Weighted average remaining term
        wavg_term = self._weighted_avg_remaining_term(positions)

        # Behavioral scores
        payment_behavior_score = self._calculate_payment_behavior_score(
            positions=positions,
            total_late_12m=total_late_12m,
            worst_status=worst_status,
        )
        credit_mix_score = self._calculate_credit_mix_score(product_counts)

        return CreditPositionAnalysisResult(
            total_monthly_debt=round(total_monthly_debt, 2),
            total_outstanding_balance=round(total_outstanding, 2),
            total_credit_limit=round(total_limit, 2),
            weighted_avg_interest_rate=round(wavg_rate, 6),
            avg_utilization=round(avg_utilization, 4),
            max_utilization=round(max_utilization, 4),
            num_active_positions=len(positions),
            num_delinquent_positions=len(delinquent),
            num_secured_positions=len(secured),
            has_restructured_debt=has_restructured,
            worst_payment_status=worst_status,
            max_days_past_due=max_dpd,
            total_late_payments_12m=total_late_12m,
            total_late_payments_lifetime=total_late_life,
            product_type_count=product_counts,
            total_collateral_value=round(total_collateral, 2),
            weighted_avg_remaining_term=round(wavg_term, 1),
            payment_behavior_score=round(payment_behavior_score, 4),
            credit_mix_score=round(credit_mix_score, 4),
        )

    @staticmethod
    def _weighted_avg_rate(positions: list[CreditPosition]) -> float:
        """Calculate balance-weighted average interest rate."""
        total_balance = sum(p.outstanding_balance for p in positions)
        if total_balance == 0:
            return 0.0
        weighted_sum = sum(
            p.interest_rate * p.outstanding_balance for p in positions
        )
        return weighted_sum / total_balance

    @staticmethod
    def _weighted_avg_remaining_term(
        positions: list[CreditPosition],
    ) -> float:
        """Calculate balance-weighted average remaining term in months."""
        total_balance = sum(p.outstanding_balance for p in positions)
        if total_balance == 0:
            return 0.0
        weighted_sum = sum(
            p.remaining_term_months * p.outstanding_balance
            for p in positions
        )
        return weighted_sum / total_balance

    def _determine_worst_status(
        self, positions: list[CreditPosition]
    ) -> PaymentStatus:
        """Find the worst payment status across all positions."""
        if not positions:
            return PaymentStatus.CURRENT
        return max(
            (p.payment_status for p in positions),
            key=lambda s: self._STATUS_SEVERITY.get(s, 0),
        )

    def _calculate_payment_behavior_score(
        self,
        positions: list[CreditPosition],
        total_late_12m: int,
        worst_status: PaymentStatus,
    ) -> float:
        """
        Calculate payment behavior score (0.0 = worst, 1.0 = perfect).

        Factors:
        - Late payments in last 12 months (major factor)
        - Worst current payment status
        - Restructured debt penalty
        """
        if not positions:
            return 1.0

        # Late payment penalty: each late payment in 12m reduces score
        late_penalty = min(total_late_12m * 0.08, 0.60)

        # Status penalty
        severity = self._STATUS_SEVERITY.get(worst_status, 0)
        status_penalty = severity * 0.08

        # Restructured penalty
        restructured_penalty = (
            0.15 if any(p.restructured for p in positions) else 0.0
        )

        score = 1.0 - late_penalty - status_penalty - restructured_penalty
        return max(0.0, min(score, 1.0))

    @staticmethod
    def _calculate_credit_mix_score(
        product_counts: dict[str, int],
    ) -> float:
        """
        Calculate credit mix score (diversity of credit products).

        A healthy mix of different product types is positive.
        Score: 0.0 (single type) to 1.0 (diverse mix).
        """
        num_types = len(product_counts)
        if num_types == 0:
            return 0.0

        # Optimal mix has 2-4 different product types
        if num_types == 1:
            return 0.3
        elif num_types == 2:
            return 0.6
        elif num_types == 3:
            return 0.85
        elif num_types == 4:
            return 1.0
        else:
            return 0.9  # Very diverse, slightly penalized for complexity

    @staticmethod
    def _empty_result() -> CreditPositionAnalysisResult:
        """Return empty analysis for clients with no credit positions."""
        return CreditPositionAnalysisResult(
            total_monthly_debt=0.0,
            total_outstanding_balance=0.0,
            total_credit_limit=0.0,
            weighted_avg_interest_rate=0.0,
            avg_utilization=0.0,
            max_utilization=0.0,
            num_active_positions=0,
            num_delinquent_positions=0,
            num_secured_positions=0,
            has_restructured_debt=False,
            worst_payment_status=PaymentStatus.CURRENT,
            max_days_past_due=0,
            total_late_payments_12m=0,
            total_late_payments_lifetime=0,
            product_type_count={},
            total_collateral_value=0.0,
            weighted_avg_remaining_term=0.0,
            payment_behavior_score=1.0,
            credit_mix_score=0.0,
        )
