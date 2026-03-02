"""
Portfolio-level risk aggregation service.

Aggregates individual client risk assessments into portfolio-level
metrics, distributions, and concentration analyses. Implements the
PortfolioAnalyzer interface.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from credit_risk_engine.domain.enums import PaymentStatus
from credit_risk_engine.domain.interfaces import PortfolioAnalyzer
from credit_risk_engine.domain.models import (
    Client,
    ClientRiskAssessment,
    PortfolioRiskSummary,
)

logger = logging.getLogger(__name__)

_DELINQUENT_STATUSES = frozenset(
    {
        PaymentStatus.DAYS_30,
        PaymentStatus.DAYS_60,
        PaymentStatus.DAYS_90,
        PaymentStatus.DAYS_120_PLUS,
        PaymentStatus.DEFAULT,
    }
)


class PortfolioRiskAnalyzer(PortfolioAnalyzer):
    """
    Aggregates client-level risk assessments into portfolio-level summaries.

    Produces:
    - Risk level distribution
    - Segment-level breakdowns
    - Product exposure analysis
    - Concentration metrics
    - Delinquency and default rates
    """

    def summarize_portfolio(
        self,
        assessments: list[ClientRiskAssessment],
        clients: list[Client],
    ) -> PortfolioRiskSummary:
        """
        Generate an aggregated risk summary for the portfolio.

        Args:
            assessments: Individual client risk assessments.
            clients: Client entities for segment breakdowns.

        Returns:
            Portfolio-level risk summary with all aggregated metrics.
        """
        if not assessments:
            return self._empty_summary()

        client_map = {c.client_id: c for c in clients}
        total = len(assessments)

        # Core aggregations
        total_exposure = sum(a.exposure_at_default for a in assessments)
        total_el = sum(a.expected_loss for a in assessments)
        avg_pd = sum(a.probability_of_default for a in assessments) / total
        avg_dti = sum(a.dti_ratio for a in assessments) / total
        avg_score = sum(a.credit_score for a in assessments) / total

        # Risk distribution
        risk_dist = self._compute_risk_distribution(assessments)

        # Segment summary
        segment_summary = self._compute_segment_summary(
            assessments, client_map
        )

        # Delinquency and default rates
        delinquent_count = sum(
            1
            for a in assessments
            if a.worst_payment_status in _DELINQUENT_STATUSES
        )
        default_count = sum(
            1
            for a in assessments
            if a.worst_payment_status == PaymentStatus.DEFAULT
        )
        delinquency_rate = delinquent_count / total
        default_rate = default_count / total

        # Concentration: top 10% exposure share
        concentration = self._compute_concentration(assessments)

        return PortfolioRiskSummary(
            assessment_date=date.today(),
            total_clients=total,
            total_exposure=round(total_exposure, 2),
            total_expected_loss=round(total_el, 2),
            avg_probability_of_default=round(avg_pd, 6),
            avg_dti_ratio=round(avg_dti, 4),
            avg_credit_score=round(avg_score, 1),
            risk_distribution=risk_dist,
            segment_summary=segment_summary,
            product_exposure={},  # Filled at pipeline level if needed
            delinquency_rate=round(delinquency_rate, 4),
            default_rate=round(default_rate, 4),
            concentration_top10_pct=round(concentration, 4),
        )

    @staticmethod
    def _compute_risk_distribution(
        assessments: list[ClientRiskAssessment],
    ) -> dict[str, int]:
        """Count clients per risk level."""
        distribution: dict[str, int] = defaultdict(int)
        for a in assessments:
            distribution[a.risk_level.value] += 1
        return dict(distribution)

    @staticmethod
    def _compute_segment_summary(
        assessments: list[ClientRiskAssessment],
        client_map: dict[str, Client],
    ) -> dict[str, dict[str, float]]:
        """
        Compute risk metrics broken down by client segment.

        Returns per-segment: count, avg_pd, avg_dti, avg_score, total_ead, total_el.
        """
        segment_data: dict[str, list[ClientRiskAssessment]] = defaultdict(list)

        for a in assessments:
            client = client_map.get(a.client_id)
            if client:
                segment_data[client.segment.value].append(a)

        summary: dict[str, dict[str, float]] = {}
        for segment, seg_assessments in segment_data.items():
            n = len(seg_assessments)
            summary[segment] = {
                "count": float(n),
                "avg_pd": round(
                    sum(a.probability_of_default for a in seg_assessments) / n,
                    6,
                ),
                "avg_dti": round(
                    sum(a.dti_ratio for a in seg_assessments) / n, 4
                ),
                "avg_credit_score": round(
                    sum(a.credit_score for a in seg_assessments) / n, 1
                ),
                "total_ead": round(
                    sum(a.exposure_at_default for a in seg_assessments), 2
                ),
                "total_expected_loss": round(
                    sum(a.expected_loss for a in seg_assessments), 2
                ),
            }

        return summary

    @staticmethod
    def _compute_concentration(
        assessments: list[ClientRiskAssessment],
    ) -> float:
        """
        Calculate exposure concentration ratio for top 10% of clients.

        Returns the percentage of total exposure held by the top 10%.
        """
        if not assessments:
            return 0.0

        exposures = sorted(
            (a.exposure_at_default for a in assessments), reverse=True
        )
        total = sum(exposures)
        if total == 0:
            return 0.0

        top_10_count = max(1, len(exposures) // 10)
        top_10_exposure = sum(exposures[:top_10_count])
        return top_10_exposure / total

    @staticmethod
    def _empty_summary() -> PortfolioRiskSummary:
        """Return an empty portfolio summary."""
        return PortfolioRiskSummary(
            assessment_date=date.today(),
            total_clients=0,
            total_exposure=0.0,
            total_expected_loss=0.0,
            avg_probability_of_default=0.0,
            avg_dti_ratio=0.0,
            avg_credit_score=0.0,
        )
