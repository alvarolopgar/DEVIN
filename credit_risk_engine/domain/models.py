"""
Domain models (entities and value objects) for the Credit Risk Decision Engine.

These models represent the core business concepts and are independent
of any infrastructure or persistence concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from credit_risk_engine.domain.enums import (
    ClientSegment,
    CreditProductType,
    EmploymentStatus,
    IncomeSource,
    PaymentStatus,
    RiskLevel,
)


@dataclass
class Client:
    """
    Represents a banking client with demographic and relationship data.

    Attributes:
        client_id: Unique identifier for the client.
        first_name: Client's first name.
        last_name: Client's last name.
        date_of_birth: Client's date of birth.
        national_id: National identification number (hashed/anonymized).
        segment: Banking segment classification.
        employment_status: Current employment situation.
        employment_years: Years in current employment.
        relationship_start_date: Date when the client relationship began.
        province: Client's province/region of residence.
        has_guarantor: Whether the client has a guarantor on file.
        num_dependents: Number of financial dependents.
        education_level: Highest education level attained.
        marital_status: Current marital status.
    """

    client_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    national_id: str
    segment: ClientSegment
    employment_status: EmploymentStatus
    employment_years: float
    relationship_start_date: date
    province: str
    has_guarantor: bool = False
    num_dependents: int = 0
    education_level: str = "secondary"
    marital_status: str = "single"

    @property
    def age(self) -> int:
        """Calculate the client's current age."""
        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    @property
    def relationship_years(self) -> float:
        """Calculate years of relationship with the bank."""
        today = date.today()
        delta = today - self.relationship_start_date
        return round(delta.days / 365.25, 2)


@dataclass
class IncomeRecord:
    """
    Represents a single income record for a client.

    Each client may have multiple income sources, and each source
    has monthly records over time for stability analysis.

    Attributes:
        record_id: Unique identifier for this income record.
        client_id: Reference to the client.
        source: Type of income source.
        monthly_amount: Gross monthly income amount in EUR.
        net_monthly_amount: Net monthly income after taxes in EUR.
        currency: ISO currency code.
        is_verified: Whether the income has been verified by the bank.
        start_date: Date when this income source started.
        end_date: Date when this income source ended (None if ongoing).
        period_date: The month this record corresponds to.
        is_regular: Whether this is a regular/recurring income.
    """

    record_id: str
    client_id: str
    source: IncomeSource
    monthly_amount: float
    net_monthly_amount: float
    currency: str = "EUR"
    is_verified: bool = False
    start_date: date | None = None
    end_date: date | None = None
    period_date: date | None = None
    is_regular: bool = True

    @property
    def is_active(self) -> bool:
        """Check if this income source is currently active."""
        return self.end_date is None


@dataclass
class CreditPosition:
    """
    Represents an active credit position (loan, card, line) for a client.

    Attributes:
        position_id: Unique identifier for this credit position.
        client_id: Reference to the client.
        product_type: Type of credit product.
        original_amount: Original principal amount granted.
        outstanding_balance: Current outstanding balance.
        credit_limit: Approved credit limit (for revolving products).
        monthly_payment: Current monthly payment obligation.
        interest_rate: Annual interest rate (as decimal, e.g., 0.05 for 5%).
        origination_date: Date the credit was originated.
        maturity_date: Expected maturity/payoff date.
        payment_status: Current payment status.
        days_past_due: Number of days past due (0 if current).
        num_late_payments_12m: Number of late payments in last 12 months.
        num_late_payments_lifetime: Total late payments over lifetime.
        collateral_value: Value of collateral (if secured).
        is_secured: Whether the position is collateralized.
        restructured: Whether the position has been restructured.
    """

    position_id: str
    client_id: str
    product_type: CreditProductType
    original_amount: float
    outstanding_balance: float
    credit_limit: float
    monthly_payment: float
    interest_rate: float
    origination_date: date
    maturity_date: date
    payment_status: PaymentStatus = PaymentStatus.CURRENT
    days_past_due: int = 0
    num_late_payments_12m: int = 0
    num_late_payments_lifetime: int = 0
    collateral_value: float = 0.0
    is_secured: bool = False
    restructured: bool = False

    @property
    def utilization_ratio(self) -> float:
        """Calculate credit utilization ratio."""
        if self.credit_limit <= 0:
            return 0.0
        return min(self.outstanding_balance / self.credit_limit, 1.0)

    @property
    def remaining_term_months(self) -> int:
        """Calculate remaining term in months."""
        today = date.today()
        if self.maturity_date <= today:
            return 0
        delta = self.maturity_date - today
        return max(int(delta.days / 30.44), 0)

    @property
    def loan_to_value(self) -> float | None:
        """Calculate LTV ratio for secured positions."""
        if not self.is_secured or self.collateral_value <= 0:
            return None
        return self.outstanding_balance / self.collateral_value


@dataclass
class ClientRiskAssessment:
    """
    Complete risk assessment result for a single client.

    Consolidates all analytical outputs into a single assessment entity.

    Attributes:
        client_id: Reference to the assessed client.
        assessment_date: Date of the assessment.
        credit_score: Composite credit score (0-1000).
        risk_level: Classified risk level.
        probability_of_default: Estimated PD.
        loss_given_default: Estimated LGD (weighted by exposure).
        exposure_at_default: Total EAD across all positions.
        expected_loss: PD x LGD x EAD.
        dti_ratio: Debt-to-income ratio.
        total_monthly_debt: Total monthly debt obligations.
        total_monthly_income: Total verified monthly income.
        total_outstanding_balance: Sum of all outstanding balances.
        income_stability_score: Score measuring income consistency (0-1).
        credit_utilization_avg: Average credit utilization across positions.
        num_active_positions: Number of active credit positions.
        num_delinquent_positions: Number of positions past due.
        worst_payment_status: Worst payment status across positions.
        has_restructured_debt: Whether any position is restructured.
        recommendation: Textual risk recommendation.
        risk_factors: List of identified risk factors.
    """

    client_id: str
    assessment_date: date
    credit_score: int
    risk_level: RiskLevel
    probability_of_default: float
    loss_given_default: float
    exposure_at_default: float
    expected_loss: float
    dti_ratio: float
    total_monthly_debt: float
    total_monthly_income: float
    total_outstanding_balance: float
    income_stability_score: float
    credit_utilization_avg: float
    num_active_positions: int
    num_delinquent_positions: int
    worst_payment_status: PaymentStatus
    has_restructured_debt: bool
    recommendation: str = ""
    risk_factors: list[str] = field(default_factory=list)


@dataclass
class PortfolioRiskSummary:
    """
    Aggregated risk summary for the entire portfolio.

    Attributes:
        assessment_date: Date of the portfolio assessment.
        total_clients: Total number of clients assessed.
        total_exposure: Total portfolio exposure (EAD).
        total_expected_loss: Sum of expected losses.
        avg_probability_of_default: Portfolio-weighted average PD.
        avg_dti_ratio: Average DTI across the portfolio.
        avg_credit_score: Average credit score.
        risk_distribution: Count of clients per risk level.
        segment_summary: Risk metrics broken down by client segment.
        product_exposure: Exposure broken down by product type.
        delinquency_rate: Percentage of clients with delinquent positions.
        default_rate: Percentage of clients in default.
        concentration_top10_pct: Exposure concentration in top 10% of clients.
    """

    assessment_date: date
    total_clients: int
    total_exposure: float
    total_expected_loss: float
    avg_probability_of_default: float
    avg_dti_ratio: float
    avg_credit_score: float
    risk_distribution: dict[str, int] = field(default_factory=dict)
    segment_summary: dict[str, dict[str, float]] = field(default_factory=dict)
    product_exposure: dict[str, float] = field(default_factory=dict)
    delinquency_rate: float = 0.0
    default_rate: float = 0.0
    concentration_top10_pct: float = 0.0
