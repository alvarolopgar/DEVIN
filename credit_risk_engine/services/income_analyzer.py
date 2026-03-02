"""
Income analysis service.

Evaluates income stability, calculates aggregate monthly income,
and produces an income stability score used in credit scoring
and default prediction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from credit_risk_engine.domain.enums import IncomeSource
from credit_risk_engine.domain.models import IncomeRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncomeAnalysisResult:
    """Result of income analysis for a single client."""

    total_monthly_gross: float
    total_monthly_net: float
    verified_monthly_net: float
    num_income_sources: int
    num_active_sources: int
    primary_source: IncomeSource | None
    income_stability_score: float  # 0.0 to 1.0
    coefficient_of_variation: float
    income_trend: float  # Positive = growing, negative = declining
    has_regular_income: bool
    verified_income_ratio: float  # Proportion of income that is verified


class IncomeAnalyzer:
    """
    Analyzes client income for stability, capacity, and reliability.

    Evaluates multiple dimensions of income:
    - Total capacity (gross and net)
    - Stability over time (coefficient of variation)
    - Trend direction (growing vs. declining)
    - Verification status
    - Source diversification
    """

    def analyze(self, income_records: list[IncomeRecord]) -> IncomeAnalysisResult:
        """
        Perform comprehensive income analysis for a client.

        Args:
            income_records: All income records for the client.

        Returns:
            Structured income analysis result.
        """
        if not income_records:
            return self._empty_result()

        # Separate active vs. all records
        active_records = [r for r in income_records if r.is_active]

        # Calculate current monthly totals from the most recent period
        latest_gross, latest_net = self._calculate_latest_monthly(
            income_records
        )

        # Verified income
        verified_net = sum(
            r.net_monthly_amount
            for r in active_records
            if r.is_verified
        )

        # Source analysis
        active_sources = set(r.source for r in active_records)
        all_sources = set(r.source for r in income_records)
        primary_source = self._determine_primary_source(income_records)

        # Stability analysis
        monthly_totals = self._aggregate_monthly_totals(income_records)
        cv = self._coefficient_of_variation(monthly_totals)
        stability_score = self._calculate_stability_score(
            cv=cv,
            num_sources=len(active_sources),
            has_regular=any(r.is_regular for r in active_records),
            verified_ratio=(
                verified_net / latest_net if latest_net > 0 else 0.0
            ),
        )

        # Trend analysis
        trend = self._calculate_income_trend(monthly_totals)

        # Regularity
        has_regular = any(r.is_regular for r in active_records)

        verified_ratio = (
            verified_net / latest_net if latest_net > 0 else 0.0
        )

        return IncomeAnalysisResult(
            total_monthly_gross=round(latest_gross, 2),
            total_monthly_net=round(latest_net, 2),
            verified_monthly_net=round(verified_net, 2),
            num_income_sources=len(all_sources),
            num_active_sources=len(active_sources),
            primary_source=primary_source,
            income_stability_score=round(stability_score, 4),
            coefficient_of_variation=round(cv, 4),
            income_trend=round(trend, 4),
            has_regular_income=has_regular,
            verified_income_ratio=round(min(verified_ratio, 1.0), 4),
        )

    def _calculate_latest_monthly(
        self, records: list[IncomeRecord]
    ) -> tuple[float, float]:
        """
        Calculate the latest monthly gross and net income.

        Uses the most recent period's data, aggregated across all sources.
        """
        if not records:
            return 0.0, 0.0

        # Group by period and take the latest
        records_with_period = [r for r in records if r.period_date is not None]
        if not records_with_period:
            # Fall back to active records' amounts
            gross = sum(r.monthly_amount for r in records if r.is_active)
            net = sum(r.net_monthly_amount for r in records if r.is_active)
            return gross, net

        # Find the latest period
        latest_period = max(r.period_date for r in records_with_period)
        latest_records = [
            r for r in records_with_period if r.period_date == latest_period
        ]

        gross = sum(r.monthly_amount for r in latest_records)
        net = sum(r.net_monthly_amount for r in latest_records)
        return gross, net

    def _determine_primary_source(
        self, records: list[IncomeRecord]
    ) -> IncomeSource | None:
        """Determine the primary income source by total amount."""
        if not records:
            return None

        source_totals: dict[IncomeSource, float] = {}
        for r in records:
            source_totals[r.source] = (
                source_totals.get(r.source, 0.0) + r.monthly_amount
            )

        return max(source_totals, key=source_totals.get)  # type: ignore[arg-type]

    def _aggregate_monthly_totals(
        self, records: list[IncomeRecord]
    ) -> list[float]:
        """Aggregate income into monthly totals for time-series analysis."""
        monthly: dict[str, float] = {}
        for r in records:
            if r.period_date is not None:
                key = r.period_date.isoformat()[:7]  # YYYY-MM
                monthly[key] = monthly.get(key, 0.0) + r.net_monthly_amount

        if not monthly:
            return [sum(r.net_monthly_amount for r in records)]

        # Sort by period and return amounts
        sorted_periods = sorted(monthly.keys())
        return [monthly[p] for p in sorted_periods]

    @staticmethod
    def _coefficient_of_variation(values: list[float]) -> float:
        """Calculate coefficient of variation (std/mean)."""
        if not values or len(values) < 2:
            return 0.0
        arr = np.array(values)
        mean = np.mean(arr)
        if mean == 0:
            return 0.0
        return float(np.std(arr, ddof=1) / mean)

    @staticmethod
    def _calculate_income_trend(monthly_totals: list[float]) -> float:
        """
        Calculate income trend using simple linear regression slope.

        Returns normalized slope (positive = growing income).
        """
        if len(monthly_totals) < 3:
            return 0.0

        arr = np.array(monthly_totals)
        x = np.arange(len(arr), dtype=float)
        mean_x = np.mean(x)
        mean_y = np.mean(arr)

        # OLS slope
        numerator = np.sum((x - mean_x) * (arr - mean_y))
        denominator = np.sum((x - mean_x) ** 2)

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        # Normalize by mean income for comparability
        if mean_y == 0:
            return 0.0
        return float(slope / mean_y)

    @staticmethod
    def _calculate_stability_score(
        cv: float,
        num_sources: int,
        has_regular: bool,
        verified_ratio: float,
    ) -> float:
        """
        Calculate composite income stability score (0.0 to 1.0).

        Components:
        - Variability penalty (lower CV = higher score)
        - Diversification bonus (multiple sources)
        - Regularity bonus
        - Verification bonus
        """
        # CV component: CV of 0 → 1.0, CV of 0.5+ → 0.0
        cv_score = max(0.0, 1.0 - cv * 2.0)

        # Diversification: bonus for multiple sources (up to 3)
        div_score = min(num_sources / 3.0, 1.0)

        # Regular income bonus
        regular_score = 1.0 if has_regular else 0.3

        # Verification bonus
        verified_score = verified_ratio

        # Weighted composite
        score = (
            cv_score * 0.40
            + div_score * 0.15
            + regular_score * 0.20
            + verified_score * 0.25
        )
        return max(0.0, min(score, 1.0))

    @staticmethod
    def _empty_result() -> IncomeAnalysisResult:
        """Return an empty income analysis result for clients with no income."""
        return IncomeAnalysisResult(
            total_monthly_gross=0.0,
            total_monthly_net=0.0,
            verified_monthly_net=0.0,
            num_income_sources=0,
            num_active_sources=0,
            primary_source=None,
            income_stability_score=0.0,
            coefficient_of_variation=0.0,
            income_trend=0.0,
            has_regular_income=False,
            verified_income_ratio=0.0,
        )
