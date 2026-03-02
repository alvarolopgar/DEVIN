"""
Engine configuration management.

Centralizes all configurable parameters for the Credit Risk Decision Engine.
Supports environment variable overrides for deployment flexibility.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class SyntheticDataSettings:
    """Configuration for synthetic data generation."""

    num_clients: int = 10_000
    avg_income_records_per_client: int = 3
    avg_credit_positions_per_client: int = 2
    history_months: int = 24
    random_seed: int = 42
    output_dir: str = "data/synthetic"


@dataclass(frozen=True)
class ScoringWeights:
    """Weights for the multi-factor credit scoring model."""

    payment_history: float = 0.35
    credit_utilization: float = 0.25
    credit_history_length: float = 0.15
    credit_mix: float = 0.10
    income_stability: float = 0.10
    dti_ratio: float = 0.05

    def validate(self) -> None:
        """Ensure weights sum to 1.0 within floating-point tolerance."""
        total = (
            self.payment_history
            + self.credit_utilization
            + self.credit_history_length
            + self.credit_mix
            + self.income_stability
            + self.dti_ratio
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total:.6f}"
            )


@dataclass(frozen=True)
class RiskThresholds:
    """Thresholds for risk classification."""

    # DTI thresholds
    dti_low: float = 0.30
    dti_medium: float = 0.40
    dti_high: float = 0.50

    # PD thresholds (Probability of Default)
    pd_very_low: float = 0.02
    pd_low: float = 0.05
    pd_medium: float = 0.10
    pd_high: float = 0.20

    # Credit score thresholds (0-1000 scale)
    score_excellent: int = 800
    score_good: int = 700
    score_fair: int = 600
    score_poor: int = 500


@dataclass(frozen=True)
class LGDParameters:
    """Loss Given Default parameters by product type."""

    mortgage_secured: float = 0.25
    personal_loan: float = 0.60
    credit_card: float = 0.80
    credit_line: float = 0.70
    auto_loan: float = 0.40
    default: float = 0.65


@dataclass(frozen=True)
class ReportSettings:
    """Configuration for report generation."""

    output_dir: str = "reports"
    top_risk_clients_count: int = 50
    include_portfolio_summary: bool = True
    include_risk_distribution: bool = True
    include_top_risk_clients: bool = True
    include_segment_analysis: bool = True
    decimal_precision: int = 4


@dataclass(frozen=True)
class EngineSettings:
    """Root configuration for the Credit Risk Decision Engine."""

    _ENV_PREFIX: ClassVar[str] = "CREDIT_RISK_"

    synthetic_data: SyntheticDataSettings = field(
        default_factory=SyntheticDataSettings
    )
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    risk_thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    lgd_parameters: LGDParameters = field(default_factory=LGDParameters)
    report: ReportSettings = field(default_factory=ReportSettings)
    log_level: str = "INFO"
    data_dir: str = "data/synthetic"

    def __post_init__(self) -> None:
        """Validate configuration on initialization."""
        self.scoring_weights.validate()

    @classmethod
    def from_environment(cls) -> EngineSettings:
        """
        Create settings with environment variable overrides.

        Environment variables follow the pattern:
        CREDIT_RISK_<SECTION>_<PARAM> (e.g., CREDIT_RISK_LOG_LEVEL)
        """
        log_level = os.environ.get(
            f"{cls._ENV_PREFIX}LOG_LEVEL", "INFO"
        )
        data_dir = os.environ.get(
            f"{cls._ENV_PREFIX}DATA_DIR", "data/synthetic"
        )
        seed_str = os.environ.get(
            f"{cls._ENV_PREFIX}RANDOM_SEED", "42"
        )
        num_clients_str = os.environ.get(
            f"{cls._ENV_PREFIX}NUM_CLIENTS", "10000"
        )

        synthetic = SyntheticDataSettings(
            random_seed=int(seed_str),
            num_clients=int(num_clients_str),
            output_dir=data_dir,
        )

        return cls(
            log_level=log_level,
            data_dir=data_dir,
            synthetic_data=synthetic,
        )


_settings_instance: EngineSettings | None = None


def get_settings() -> EngineSettings:
    """
    Get or create the singleton settings instance.

    Returns:
        The engine settings, initialized from environment on first call.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = EngineSettings.from_environment()
    return _settings_instance
