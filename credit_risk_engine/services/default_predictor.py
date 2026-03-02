"""
Default probability prediction service.

Implements a logistic regression-based model for estimating
Probability of Default (PD). Uses financial features derived
from income analysis and credit position analysis.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from credit_risk_engine.domain.enums import (
    EmploymentStatus,
    PaymentStatus,
)
from credit_risk_engine.domain.models import Client
from credit_risk_engine.services.credit_position_analyzer import (
    CreditPositionAnalysisResult,
)
from credit_risk_engine.services.income_analyzer import IncomeAnalysisResult

logger = logging.getLogger(__name__)

# Payment status severity mapping for feature engineering
_STATUS_SEVERITY_MAP: dict[PaymentStatus, float] = {
    PaymentStatus.CURRENT: 0.0,
    PaymentStatus.RESTRUCTURED: 0.3,
    PaymentStatus.DAYS_30: 0.2,
    PaymentStatus.DAYS_60: 0.4,
    PaymentStatus.DAYS_90: 0.6,
    PaymentStatus.DAYS_120_PLUS: 0.8,
    PaymentStatus.DEFAULT: 1.0,
}


@dataclass(frozen=True)
class DefaultPredictionResult:
    """Result of default probability prediction."""

    probability_of_default: float  # 0.0 to 1.0
    log_odds: float
    feature_contributions: dict[str, float]
    risk_drivers: list[str]  # Ordered list of key risk drivers


class DefaultPredictor:
    """
    Predicts probability of default using a logistic model.

    The model uses expert-calibrated coefficients based on standard
    credit risk modeling practices (Basel II/III IRB approach).
    Features include DTI ratio, payment behavior, income stability,
    employment status, credit utilization, and delinquency history.

    The logistic function: PD = 1 / (1 + exp(-z))
    where z = intercept + sum(coefficient_i * feature_i)
    """

    # Expert-calibrated logistic regression coefficients
    _INTERCEPT: float = -3.5

    _COEFFICIENTS: dict[str, float] = {
        "dti_ratio": 2.8,               # Higher DTI → higher PD
        "worst_status_severity": 3.2,    # Delinquency → strong PD signal
        "late_payments_12m": 0.35,       # Each late payment increases PD
        "income_stability_inv": 1.5,     # Lower stability → higher PD
        "utilization_excess": 2.0,       # High utilization → higher PD
        "employment_risk": 1.8,          # Unemployment/temp → higher PD
        "restructured_flag": 1.2,        # Restructured debt → higher PD
        "age_risk": 0.4,                 # Very young/old → slightly higher
        "income_trend_neg": 1.0,         # Declining income → higher PD
        "num_positions_excess": 0.15,    # Many positions → slightly higher
    }

    def predict(
        self,
        client: Client,
        income_analysis: IncomeAnalysisResult,
        position_analysis: CreditPositionAnalysisResult,
        dti_ratio: float,
    ) -> DefaultPredictionResult:
        """
        Predict probability of default for a client.

        Args:
            client: Client entity.
            income_analysis: Income analysis results.
            position_analysis: Credit position analysis results.
            dti_ratio: Calculated debt-to-income ratio.

        Returns:
            Default prediction with PD, feature contributions, and risk drivers.
        """
        features = self._engineer_features(
            client, income_analysis, position_analysis, dti_ratio
        )

        # Calculate log-odds (z-score)
        contributions: dict[str, float] = {}
        z = self._INTERCEPT
        for feature_name, feature_value in features.items():
            coeff = self._COEFFICIENTS.get(feature_name, 0.0)
            contribution = coeff * feature_value
            contributions[feature_name] = round(contribution, 4)
            z += contribution

        # Apply logistic function
        pd = self._logistic(z)

        # Identify risk drivers (features with highest positive contribution)
        risk_drivers = self._identify_risk_drivers(contributions)

        return DefaultPredictionResult(
            probability_of_default=round(pd, 6),
            log_odds=round(z, 4),
            feature_contributions=contributions,
            risk_drivers=risk_drivers,
        )

    def _engineer_features(
        self,
        client: Client,
        income_analysis: IncomeAnalysisResult,
        position_analysis: CreditPositionAnalysisResult,
        dti_ratio: float,
    ) -> dict[str, float]:
        """
        Engineer features from raw analysis results.

        Transforms raw metrics into model-ready features with proper
        scaling and non-linear transformations.
        """
        features: dict[str, float] = {}

        # DTI ratio (capped at 1.5 for model stability)
        features["dti_ratio"] = min(dti_ratio, 1.5)

        # Worst payment status severity (0.0 to 1.0)
        features["worst_status_severity"] = _STATUS_SEVERITY_MAP.get(
            position_analysis.worst_payment_status, 0.0
        )

        # Late payments in last 12 months (log-transformed)
        late_12m = position_analysis.total_late_payments_12m
        features["late_payments_12m"] = math.log1p(late_12m)

        # Income stability inverse (lower stability → higher feature value)
        features["income_stability_inv"] = (
            1.0 - income_analysis.income_stability_score
        )

        # Credit utilization excess (above 50% threshold)
        features["utilization_excess"] = max(
            0.0, position_analysis.avg_utilization - 0.50
        ) * 2.0

        # Employment risk factor
        employment_risk_map: dict[EmploymentStatus, float] = {
            EmploymentStatus.EMPLOYED_PERMANENT: 0.0,
            EmploymentStatus.SELF_EMPLOYED: 0.15,
            EmploymentStatus.EMPLOYED_TEMPORARY: 0.30,
            EmploymentStatus.FREELANCE: 0.25,
            EmploymentStatus.RETIRED: 0.10,
            EmploymentStatus.UNEMPLOYED: 0.80,
            EmploymentStatus.STUDENT: 0.60,
        }
        features["employment_risk"] = employment_risk_map.get(
            client.employment_status, 0.30
        )

        # Restructured debt flag
        features["restructured_flag"] = (
            1.0 if position_analysis.has_restructured_debt else 0.0
        )

        # Age risk (U-shaped: very young and very old have higher risk)
        age = client.age
        if age < 25:
            features["age_risk"] = (25 - age) / 25.0
        elif age > 70:
            features["age_risk"] = (age - 70) / 30.0
        else:
            features["age_risk"] = 0.0

        # Declining income trend
        features["income_trend_neg"] = max(
            0.0, -income_analysis.income_trend
        )

        # Number of positions excess (above 3)
        features["num_positions_excess"] = max(
            0.0,
            float(position_analysis.num_active_positions - 3),
        )

        return features

    @staticmethod
    def _logistic(z: float) -> float:
        """Apply the logistic function with numerical stability."""
        if z > 500:
            return 1.0
        if z < -500:
            return 0.0
        return 1.0 / (1.0 + math.exp(-z))

    @staticmethod
    def _identify_risk_drivers(
        contributions: dict[str, float],
    ) -> list[str]:
        """
        Identify top risk drivers from feature contributions.

        Returns features that contribute positively to default probability,
        ordered by contribution magnitude.
        """
        # Feature name to human-readable mapping
        labels: dict[str, str] = {
            "dti_ratio": "High debt-to-income ratio",
            "worst_status_severity": "Payment delinquency",
            "late_payments_12m": "Recent late payments",
            "income_stability_inv": "Unstable income",
            "utilization_excess": "High credit utilization",
            "employment_risk": "Employment instability",
            "restructured_flag": "Restructured debt",
            "age_risk": "Age-related risk",
            "income_trend_neg": "Declining income trend",
            "num_positions_excess": "Excessive credit positions",
        }

        # Sort by contribution magnitude (descending) and filter positive
        drivers = [
            labels.get(name, name)
            for name, value in sorted(
                contributions.items(), key=lambda x: x[1], reverse=True
            )
            if value > 0.05  # Only significant contributions
        ]
        return drivers[:5]  # Top 5 risk drivers
