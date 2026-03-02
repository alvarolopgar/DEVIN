"""
Domain enumerations for the Credit Risk Decision Engine.

Defines all categorical types used across the domain model,
ensuring type safety and consistent vocabulary throughout the system.
"""

from enum import Enum, unique


@unique
class RiskLevel(str, Enum):
    """Risk classification levels for credit assessment."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


@unique
class ClientSegment(str, Enum):
    """Banking client segmentation."""

    RETAIL = "retail"
    PREMIUM = "premium"
    PRIVATE_BANKING = "private_banking"
    SME = "sme"
    CORPORATE = "corporate"


@unique
class EmploymentStatus(str, Enum):
    """Client employment status categories."""

    EMPLOYED_PERMANENT = "employed_permanent"
    EMPLOYED_TEMPORARY = "employed_temporary"
    SELF_EMPLOYED = "self_employed"
    FREELANCE = "freelance"
    RETIRED = "retired"
    UNEMPLOYED = "unemployed"
    STUDENT = "student"


@unique
class IncomeSource(str, Enum):
    """Types of income sources."""

    SALARY = "salary"
    BUSINESS_INCOME = "business_income"
    RENTAL_INCOME = "rental_income"
    PENSION = "pension"
    INVESTMENTS = "investments"
    FREELANCE_INCOME = "freelance_income"
    GOVERNMENT_BENEFITS = "government_benefits"
    OTHER = "other"


@unique
class CreditProductType(str, Enum):
    """Types of credit products in the portfolio."""

    MORTGAGE = "mortgage"
    PERSONAL_LOAN = "personal_loan"
    CREDIT_CARD = "credit_card"
    CREDIT_LINE = "credit_line"
    AUTO_LOAN = "auto_loan"


@unique
class PaymentStatus(str, Enum):
    """Payment status for credit positions."""

    CURRENT = "current"
    DAYS_30 = "30_days_past_due"
    DAYS_60 = "60_days_past_due"
    DAYS_90 = "90_days_past_due"
    DAYS_120_PLUS = "120_plus_days_past_due"
    DEFAULT = "default"
    RESTRUCTURED = "restructured"
