"""
Client risk assessment orchestrator.

Coordinates the individual analysis services (income, credit position,
scoring, default prediction, loss calculation) to produce a complete
risk assessment for each client. Implements the RiskAnalyzer interface.
"""

from __future__ import annotations

import logging
from datetime import date

from credit_risk_engine.config.settings import EngineSettings
from credit_risk_engine.domain.enums import RiskLevel
from credit_risk_engine.domain.interfaces import RiskAnalyzer
from credit_risk_engine.domain.models import (
    Client,
    ClientRiskAssessment,
    CreditPosition,
    IncomeRecord,
)
from credit_risk_engine.services.credit_position_analyzer import (
    CreditPositionAnalysisResult,
    CreditPositionAnalyzer,
)
from credit_risk_engine.services.default_predictor import DefaultPredictor
from credit_risk_engine.services.income_analyzer import (
    IncomeAnalysisResult,
    IncomeAnalyzer,
)
from credit_risk_engine.services.loss_calculator import LossCalculator
from credit_risk_engine.services.scoring_engine import CreditScoringEngine

logger = logging.getLogger(__name__)


class ClientRiskAssessor(RiskAnalyzer):
    """
    Orchestrates all analysis services to produce a complete risk assessment.

    This is the main entry point for individual client risk evaluation.
    It coordinates:
    1. Income analysis (stability, capacity)
    2. Credit position analysis (debt burden, behavior)
    3. DTI calculation
    4. Credit scoring
    5. Default probability prediction
    6. Loss estimation
    7. Risk classification and recommendation generation

    Args:
        settings: Engine configuration.
        income_analyzer: Income analysis service.
        position_analyzer: Credit position analysis service.
        scoring_engine: Credit scoring engine.
        default_predictor: Default prediction service.
        loss_calculator: Loss calculation service.
    """

    def __init__(
        self,
        settings: EngineSettings,
        income_analyzer: IncomeAnalyzer,
        position_analyzer: CreditPositionAnalyzer,
        scoring_engine: CreditScoringEngine,
        default_predictor: DefaultPredictor,
        loss_calculator: LossCalculator,
    ) -> None:
        self._settings = settings
        self._income_analyzer = income_analyzer
        self._position_analyzer = position_analyzer
        self._scoring_engine = scoring_engine
        self._default_predictor = default_predictor
        self._loss_calculator = loss_calculator

    def assess_client(
        self,
        client: Client,
        income_records: list[IncomeRecord],
        credit_positions: list[CreditPosition],
    ) -> ClientRiskAssessment:
        """
        Perform a complete risk assessment for a single client.

        Args:
            client: The client entity.
            income_records: All income records for the client.
            credit_positions: All credit positions for the client.

        Returns:
            Complete risk assessment with all metrics and recommendations.
        """
        # Step 1: Analyze income
        income_result = self._income_analyzer.analyze(income_records)

        # Step 2: Analyze credit positions
        position_result = self._position_analyzer.analyze(credit_positions)

        # Step 3: Calculate DTI ratio
        dti_ratio = self._calculate_dti(
            total_monthly_debt=position_result.total_monthly_debt,
            total_monthly_income=income_result.total_monthly_net,
        )

        # Step 4: Credit scoring
        scoring_result = self._scoring_engine.score(
            client=client,
            income_analysis=income_result,
            position_analysis=position_result,
            dti_ratio=dti_ratio,
        )

        # Step 5: Default prediction
        default_result = self._default_predictor.predict(
            client=client,
            income_analysis=income_result,
            position_analysis=position_result,
            dti_ratio=dti_ratio,
        )

        # Step 6: Loss estimation
        loss_result = self._loss_calculator.calculate_client_loss(
            positions=credit_positions,
            probability_of_default=default_result.probability_of_default,
        )

        # Step 7: Generate risk factors and recommendation
        risk_factors = self._compile_risk_factors(
            dti_ratio=dti_ratio,
            income_result=income_result,
            position_result=position_result,
            default_result_drivers=default_result.risk_drivers,
        )

        recommendation = self._generate_recommendation(
            risk_level=scoring_result.risk_level,
            dti_ratio=dti_ratio,
            pd=default_result.probability_of_default,
            risk_factors=risk_factors,
        )

        return ClientRiskAssessment(
            client_id=client.client_id,
            assessment_date=date.today(),
            credit_score=scoring_result.composite_score,
            risk_level=scoring_result.risk_level,
            probability_of_default=default_result.probability_of_default,
            loss_given_default=loss_result.weighted_lgd,
            exposure_at_default=loss_result.total_ead,
            expected_loss=loss_result.total_expected_loss,
            dti_ratio=round(dti_ratio, 4),
            total_monthly_debt=position_result.total_monthly_debt,
            total_monthly_income=income_result.total_monthly_net,
            total_outstanding_balance=position_result.total_outstanding_balance,
            income_stability_score=income_result.income_stability_score,
            credit_utilization_avg=position_result.avg_utilization,
            num_active_positions=position_result.num_active_positions,
            num_delinquent_positions=position_result.num_delinquent_positions,
            worst_payment_status=position_result.worst_payment_status,
            has_restructured_debt=position_result.has_restructured_debt,
            recommendation=recommendation,
            risk_factors=risk_factors,
        )

    @staticmethod
    def _calculate_dti(
        total_monthly_debt: float,
        total_monthly_income: float,
    ) -> float:
        """
        Calculate Debt-to-Income ratio.

        DTI = Total Monthly Debt Payments / Total Monthly Net Income.
        Capped at 2.0 to prevent extreme outliers.
        """
        if total_monthly_income <= 0:
            return 2.0 if total_monthly_debt > 0 else 0.0
        return min(total_monthly_debt / total_monthly_income, 2.0)

    @staticmethod
    def _compile_risk_factors(
        dti_ratio: float,
        income_result: IncomeAnalysisResult,
        position_result: CreditPositionAnalysisResult,
        default_result_drivers: list[str],
    ) -> list[str]:
        """Compile a comprehensive list of risk factors for the client."""
        factors: list[str] = []

        # Add default predictor's risk drivers
        factors.extend(default_result_drivers)

        # Additional context-specific risk factors
        if dti_ratio > 0.50:
            factors.append(
                f"Critical DTI ratio: {dti_ratio:.1%} exceeds 50% threshold"
            )
        elif dti_ratio > 0.35:
            factors.append(
                f"Elevated DTI ratio: {dti_ratio:.1%} above 35% threshold"
            )

        return factors

    @staticmethod
    def _generate_recommendation(
        risk_level: RiskLevel,
        dti_ratio: float,
        pd: float,
        risk_factors: list[str],
    ) -> str:
        """
        Generate a textual risk recommendation based on assessment results.

        Provides actionable guidance for credit risk management.
        """
        if risk_level == RiskLevel.VERY_LOW:
            return (
                "APPROVED - Excellent risk profile. Client demonstrates strong "
                "creditworthiness with stable income and solid payment history. "
                "Eligible for premium credit products and favorable terms."
            )

        if risk_level == RiskLevel.LOW:
            return (
                "APPROVED - Good risk profile. Client shows adequate capacity "
                "and acceptable risk metrics. Standard terms recommended."
            )

        if risk_level == RiskLevel.MEDIUM:
            base = (
                "CONDITIONAL APPROVAL - Moderate risk detected. "
                "Enhanced monitoring recommended. "
            )
            if dti_ratio > 0.35:
                base += "Consider DTI reduction before additional credit. "
            if pd > 0.08:
                base += "Quarterly review of payment behavior required. "
            return base.strip()

        if risk_level == RiskLevel.HIGH:
            base = (
                "REVIEW REQUIRED - Elevated risk profile. "
                "Manual underwriting assessment recommended. "
            )
            if risk_factors:
                base += f"Key concerns: {'; '.join(risk_factors[:3])}. "
            return base.strip()

        if risk_level in (RiskLevel.VERY_HIGH, RiskLevel.CRITICAL):
            return (
                "DECLINE / RESTRUCTURE - Critical risk level. "
                "New credit exposure not recommended. Consider proactive "
                "restructuring of existing obligations. Immediate risk "
                "management intervention required."
            )

        return "MANUAL REVIEW - Unable to determine recommendation automatically."
