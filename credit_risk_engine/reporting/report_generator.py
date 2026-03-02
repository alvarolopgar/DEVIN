"""
Structured risk report generator.

Produces comprehensive JSON reports containing portfolio-level summaries,
risk distributions, top-risk client details, and segment analyses.
Implements the ReportGenerator interface.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from credit_risk_engine.config.settings import ReportSettings
from credit_risk_engine.domain.interfaces import ReportGenerator
from credit_risk_engine.domain.models import (
    ClientRiskAssessment,
    PortfolioRiskSummary,
)

logger = logging.getLogger(__name__)


class JsonReportGenerator(ReportGenerator):
    """
    Generates structured JSON risk reports.

    The report includes:
    - Executive summary with key portfolio metrics
    - Risk distribution analysis
    - Top risk clients with detailed assessments
    - Segment-level analysis
    - Methodology notes

    Args:
        settings: Report configuration parameters.
    """

    def __init__(self, settings: ReportSettings) -> None:
        self._settings = settings

    def generate_report(
        self,
        portfolio_summary: PortfolioRiskSummary,
        client_assessments: list[ClientRiskAssessment],
        output_path: str,
    ) -> str:
        """
        Generate a complete structured risk report.

        Args:
            portfolio_summary: Aggregated portfolio risk data.
            client_assessments: Individual client assessments.
            output_path: Directory where the report will be saved.

        Returns:
            Path to the generated report file.
        """
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        report: dict[str, Any] = {
            "metadata": self._build_metadata(portfolio_summary),
        }

        if self._settings.include_portfolio_summary:
            report["executive_summary"] = self._build_executive_summary(
                portfolio_summary
            )

        if self._settings.include_risk_distribution:
            report["risk_distribution"] = self._build_risk_distribution(
                portfolio_summary, client_assessments
            )

        if self._settings.include_top_risk_clients:
            report["top_risk_clients"] = self._build_top_risk_clients(
                client_assessments
            )

        if self._settings.include_segment_analysis:
            report["segment_analysis"] = self._build_segment_analysis(
                portfolio_summary
            )

        report["methodology"] = self._build_methodology_notes()

        # Write report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"credit_risk_report_{timestamp}.json"
        report_path = output_dir / filename

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info("Risk report generated: %s", report_path)
        return str(report_path)

    def _build_metadata(
        self, summary: PortfolioRiskSummary
    ) -> dict[str, Any]:
        """Build report metadata section."""
        return {
            "report_type": "Credit Risk Portfolio Assessment",
            "generated_at": datetime.now().isoformat(),
            "assessment_date": summary.assessment_date.isoformat(),
            "engine_version": "1.0.0",
            "total_clients_assessed": summary.total_clients,
            "report_parameters": {
                "top_risk_clients_count": self._settings.top_risk_clients_count,
                "decimal_precision": self._settings.decimal_precision,
            },
        }

    def _build_executive_summary(
        self, summary: PortfolioRiskSummary
    ) -> dict[str, Any]:
        """Build executive summary section with key portfolio metrics."""
        prec = self._settings.decimal_precision
        return {
            "portfolio_overview": {
                "total_clients": summary.total_clients,
                "total_exposure_eur": round(summary.total_exposure, 2),
                "total_expected_loss_eur": round(
                    summary.total_expected_loss, 2
                ),
                "expected_loss_rate": (
                    round(
                        summary.total_expected_loss / summary.total_exposure,
                        prec,
                    )
                    if summary.total_exposure > 0
                    else 0.0
                ),
            },
            "key_risk_indicators": {
                "avg_probability_of_default": round(
                    summary.avg_probability_of_default, prec
                ),
                "avg_dti_ratio": round(summary.avg_dti_ratio, prec),
                "avg_credit_score": round(summary.avg_credit_score, 1),
                "delinquency_rate": round(summary.delinquency_rate, prec),
                "default_rate": round(summary.default_rate, prec),
                "concentration_top_10_pct": round(
                    summary.concentration_top10_pct, prec
                ),
            },
            "risk_assessment": self._generate_portfolio_assessment(summary),
        }

    @staticmethod
    def _generate_portfolio_assessment(
        summary: PortfolioRiskSummary,
    ) -> str:
        """Generate a textual assessment of the portfolio's health."""
        issues: list[str] = []

        if summary.avg_probability_of_default > 0.10:
            issues.append(
                "Average PD exceeds 10% - significant default risk"
            )
        if summary.avg_dti_ratio > 0.40:
            issues.append(
                "Average DTI exceeds 40% - portfolio over-leveraged"
            )
        if summary.delinquency_rate > 0.15:
            issues.append(
                "Delinquency rate exceeds 15% - collection review needed"
            )
        if summary.concentration_top10_pct > 0.50:
            issues.append(
                "High concentration risk - top 10% holds >50% of exposure"
            )

        if not issues:
            return (
                "Portfolio exhibits healthy risk metrics within acceptable "
                "thresholds. Continued monitoring recommended."
            )

        return (
            f"Portfolio requires attention. "
            f"Identified concerns: {'; '.join(issues)}."
        )

    def _build_risk_distribution(
        self,
        summary: PortfolioRiskSummary,
        assessments: list[ClientRiskAssessment],
    ) -> dict[str, Any]:
        """Build risk distribution analysis section."""
        total = summary.total_clients
        distribution: dict[str, Any] = {}

        for level, count in sorted(summary.risk_distribution.items()):
            level_assessments = [
                a for a in assessments if a.risk_level.value == level
            ]
            level_exposure = sum(
                a.exposure_at_default for a in level_assessments
            )
            level_el = sum(a.expected_loss for a in level_assessments)

            distribution[level] = {
                "client_count": count,
                "client_percentage": (
                    round(count / total * 100, 2) if total > 0 else 0.0
                ),
                "total_exposure_eur": round(level_exposure, 2),
                "exposure_percentage": (
                    round(level_exposure / summary.total_exposure * 100, 2)
                    if summary.total_exposure > 0
                    else 0.0
                ),
                "total_expected_loss_eur": round(level_el, 2),
                "avg_pd": (
                    round(
                        sum(
                            a.probability_of_default
                            for a in level_assessments
                        )
                        / len(level_assessments),
                        self._settings.decimal_precision,
                    )
                    if level_assessments
                    else 0.0
                ),
            }

        return distribution

    def _build_top_risk_clients(
        self, assessments: list[ClientRiskAssessment]
    ) -> list[dict[str, Any]]:
        """Build top risk clients section, sorted by expected loss."""
        # Sort by expected loss descending, then by PD
        sorted_assessments = sorted(
            assessments,
            key=lambda a: (a.expected_loss, a.probability_of_default),
            reverse=True,
        )

        top_clients: list[dict[str, Any]] = []
        for a in sorted_assessments[: self._settings.top_risk_clients_count]:
            prec = self._settings.decimal_precision
            top_clients.append(
                {
                    "client_id": a.client_id,
                    "credit_score": a.credit_score,
                    "risk_level": a.risk_level.value,
                    "probability_of_default": round(
                        a.probability_of_default, prec
                    ),
                    "expected_loss_eur": round(a.expected_loss, 2),
                    "exposure_at_default_eur": round(
                        a.exposure_at_default, 2
                    ),
                    "dti_ratio": round(a.dti_ratio, prec),
                    "total_monthly_debt_eur": round(a.total_monthly_debt, 2),
                    "total_monthly_income_eur": round(
                        a.total_monthly_income, 2
                    ),
                    "num_active_positions": a.num_active_positions,
                    "num_delinquent_positions": a.num_delinquent_positions,
                    "worst_payment_status": a.worst_payment_status.value,
                    "risk_factors": a.risk_factors,
                    "recommendation": a.recommendation,
                }
            )

        return top_clients

    @staticmethod
    def _build_segment_analysis(
        summary: PortfolioRiskSummary,
    ) -> dict[str, Any]:
        """Build segment-level risk analysis section."""
        return summary.segment_summary

    @staticmethod
    def _build_methodology_notes() -> dict[str, str]:
        """Document the methodology used in the assessment."""
        return {
            "scoring_model": (
                "Multi-factor credit scoring model (300-1000 scale) "
                "incorporating payment history (35%), credit utilization (25%), "
                "credit history length (15%), credit mix (10%), "
                "income stability (10%), and DTI ratio (5%)."
            ),
            "pd_model": (
                "Logistic regression-based Probability of Default model "
                "with expert-calibrated coefficients. Features include DTI, "
                "payment behavior, income stability, employment risk, "
                "credit utilization, and delinquency history."
            ),
            "lgd_model": (
                "Product-specific Loss Given Default estimation with "
                "adjustments for collateral coverage (LTV), restructuring "
                "history, and delinquency severity. Aligned with Basel II/III "
                "Foundation IRB approach."
            ),
            "ead_model": (
                "Exposure at Default calculated as outstanding balance "
                "for amortizing products, and drawn + CCF × undrawn "
                "for revolving products."
            ),
            "expected_loss": (
                "Expected Loss = PD × LGD × EAD, computed at position "
                "level and aggregated to client and portfolio levels."
            ),
            "regulatory_alignment": (
                "Methodology aligned with Basel II/III Internal Ratings-Based "
                "(IRB) approach, EBA Guidelines on PD/LGD estimation, "
                "and IFRS 9 Expected Credit Loss framework."
            ),
        }
