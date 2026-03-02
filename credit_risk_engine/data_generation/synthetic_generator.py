"""
Synthetic banking portfolio data generator.

Generates realistic, correlated synthetic data for clients, income records,
and credit positions. The generator produces data that simulates a real
banking portfolio with proper statistical distributions and inter-variable
correlations (e.g., age-income, income-debt capacity, employment-stability).

Output format: Apache Parquet (columnar, compressed, strongly typed).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from credit_risk_engine.config.settings import SyntheticDataSettings
from credit_risk_engine.domain.enums import (
    ClientSegment,
    CreditProductType,
    EmploymentStatus,
    IncomeSource,
    PaymentStatus,
)

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Province and demographic distributions (Spain-focused)
# ────────────────────────────────────────────────────────────────────────────

_PROVINCES = [
    "Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza",
    "Málaga", "Murcia", "Palma de Mallorca", "Las Palmas",
    "Bilbao", "Alicante", "Córdoba", "Valladolid", "Vigo",
    "Gijón", "Granada", "A Coruña", "Vitoria", "Santa Cruz de Tenerife",
    "Pamplona",
]

_PROVINCE_WEIGHTS_RAW = [
    0.18, 0.15, 0.08, 0.06, 0.05,
    0.05, 0.04, 0.03, 0.03, 0.04,
    0.04, 0.03, 0.02, 0.02, 0.02,
    0.03, 0.03, 0.02, 0.02, 0.02,
]
# Normalize to ensure weights sum to exactly 1.0
_TOTAL = sum(_PROVINCE_WEIGHTS_RAW)
_PROVINCE_WEIGHTS = [w / _TOTAL for w in _PROVINCE_WEIGHTS_RAW]

_EDUCATION_LEVELS = [
    "primary", "secondary", "vocational", "bachelor", "master", "doctorate",
]

_MARITAL_STATUSES = ["single", "married", "divorced", "widowed", "domestic_partner"]

_FIRST_NAMES = [
    "María", "Carmen", "Ana", "Laura", "Lucía", "Elena", "Marta", "Sara",
    "Paula", "Andrea", "Carlos", "José", "Antonio", "David", "Javier",
    "Miguel", "Francisco", "Daniel", "Pablo", "Alejandro", "Manuel",
    "Pedro", "Sergio", "Raúl", "Adrián", "Isabel", "Cristina", "Beatriz",
    "Sofía", "Patricia", "Álvaro", "Fernando", "Luis", "Gonzalo", "Enrique",
]

_LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "López", "González", "Hernández",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Gómez",
    "Díaz", "Reyes", "Moreno", "Jiménez", "Álvarez", "Romero", "Ruiz",
    "Navarro", "Domínguez", "Vázquez", "Ramos", "Gil", "Serrano",
    "Molina", "Blanco", "Suárez", "Castro", "Ortega", "Delgado",
]


class SyntheticPortfolioGenerator:
    """
    Generates a realistic synthetic banking portfolio.

    Produces correlated datasets for clients, income records, and credit
    positions with realistic distributions, edge cases, and proper
    financial relationships.

    Args:
        settings: Configuration for data generation parameters.
    """

    def __init__(self, settings: SyntheticDataSettings) -> None:
        self._settings = settings
        self._rng = np.random.default_rng(settings.random_seed)
        self._today = date.today()

    # ── Public API ───────────────────────────────────────────────────────

    def generate_all(self) -> dict[str, Path]:
        """
        Generate all synthetic datasets and save to Parquet.

        Returns:
            Dictionary mapping dataset names to their file paths.
        """
        output_dir = Path(self._settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Generating synthetic portfolio: %d clients",
            self._settings.num_clients,
        )

        # Phase 1: Generate clients
        clients_df = self._generate_clients()
        clients_path = output_dir / "clients.parquet"
        clients_df.to_parquet(clients_path, engine="pyarrow", index=False)
        logger.info("Generated %d clients → %s", len(clients_df), clients_path)

        # Phase 2: Generate income records (correlated with client attributes)
        income_df = self._generate_income_records(clients_df)
        income_path = output_dir / "income_records.parquet"
        income_df.to_parquet(income_path, engine="pyarrow", index=False)
        logger.info(
            "Generated %d income records → %s", len(income_df), income_path
        )

        # Phase 3: Generate credit positions (correlated with income)
        # Use the latest period's income per client (not sum of all periods)
        # to size debt realistically relative to current monthly income
        latest_period = income_df.groupby("client_id")["period_date"].max()
        latest_income = income_df.merge(
            latest_period.rename("latest_period"),
            on="client_id",
        )
        latest_income = latest_income[
            latest_income["period_date"] == latest_income["latest_period"]
        ]
        client_income_agg = (
            latest_income.groupby("client_id")["net_monthly_amount"]
            .sum()
            .to_dict()
        )
        positions_df = self._generate_credit_positions(
            clients_df, client_income_agg
        )
        positions_path = output_dir / "credit_positions.parquet"
        positions_df.to_parquet(positions_path, engine="pyarrow", index=False)
        logger.info(
            "Generated %d credit positions → %s",
            len(positions_df),
            positions_path,
        )

        return {
            "clients": clients_path,
            "income_records": income_path,
            "credit_positions": positions_path,
        }

    # ── Client Generation ────────────────────────────────────────────────

    def _generate_clients(self) -> pd.DataFrame:
        """Generate the clients dataset with realistic demographics."""
        n = self._settings.num_clients
        records: list[dict[str, Any]] = []

        for _ in range(n):
            age = self._sample_age()
            employment = self._sample_employment(age)
            segment = self._sample_segment(age, employment)
            employment_years = self._sample_employment_years(age, employment)
            relationship_years = self._sample_relationship_years(age)
            education = self._sample_education(age, segment)
            dob = self._today - timedelta(days=int(age * 365.25))
            rel_start = self._today - timedelta(
                days=int(relationship_years * 365.25)
            )

            records.append(
                {
                    "client_id": f"CLI-{uuid.uuid4().hex[:12].upper()}",
                    "first_name": self._rng.choice(_FIRST_NAMES),
                    "last_name": (
                        f"{self._rng.choice(_LAST_NAMES)} "
                        f"{self._rng.choice(_LAST_NAMES)}"
                    ),
                    "date_of_birth": dob.isoformat(),
                    "national_id": self._generate_national_id(),
                    "segment": segment.value,
                    "employment_status": employment.value,
                    "employment_years": round(employment_years, 1),
                    "relationship_start_date": rel_start.isoformat(),
                    "province": self._rng.choice(
                        _PROVINCES, p=_PROVINCE_WEIGHTS
                    ),
                    "has_guarantor": bool(self._rng.random() < 0.15),
                    "num_dependents": int(
                        self._rng.choice(
                            [0, 1, 2, 3, 4],
                            p=[0.35, 0.25, 0.25, 0.10, 0.05],
                        )
                    ),
                    "education_level": education,
                    "marital_status": self._rng.choice(
                        _MARITAL_STATUSES,
                        p=[0.30, 0.40, 0.15, 0.05, 0.10],
                    ),
                }
            )

        return pd.DataFrame(records)

    # ── Income Generation ────────────────────────────────────────────────

    def _generate_income_records(
        self, clients_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Generate income records correlated with client attributes.

        Income levels are correlated with age, education, employment type,
        and segment. Multiple income sources per client are supported.
        """
        records: list[dict[str, Any]] = []

        for _, client in clients_df.iterrows():
            client_id = client["client_id"]
            age = self._calculate_age_from_dob(client["date_of_birth"])
            segment = ClientSegment(client["segment"])
            employment = EmploymentStatus(client["employment_status"])
            education = client["education_level"]

            base_income = self._calculate_base_income(
                age, segment, employment, education
            )

            # Primary income source
            primary_source = self._map_employment_to_income_source(employment)
            num_months = self._rng.integers(6, self._settings.history_months + 1)

            for month_offset in range(num_months):
                period = self._today - timedelta(days=month_offset * 30)
                # Add monthly variability (±5% for stable, ±20% for freelance)
                variability = (
                    0.20 if employment in (
                        EmploymentStatus.FREELANCE,
                        EmploymentStatus.SELF_EMPLOYED,
                    )
                    else 0.05
                )
                monthly_gross = base_income * (
                    1 + self._rng.normal(0, variability)
                )
                monthly_gross = max(monthly_gross, 0)
                tax_rate = self._estimate_tax_rate(monthly_gross * 12)
                monthly_net = monthly_gross * (1 - tax_rate)

                start_date = self._today - timedelta(
                    days=int(
                        float(client["employment_years"]) * 365.25
                    )
                )

                records.append(
                    {
                        "record_id": f"INC-{uuid.uuid4().hex[:12].upper()}",
                        "client_id": client_id,
                        "source": primary_source.value,
                        "monthly_amount": round(monthly_gross, 2),
                        "net_monthly_amount": round(monthly_net, 2),
                        "currency": "EUR",
                        "is_verified": bool(self._rng.random() < 0.75),
                        "start_date": start_date.isoformat(),
                        "end_date": None,
                        "period_date": period.isoformat(),
                        "is_regular": employment not in (
                            EmploymentStatus.FREELANCE,
                            EmploymentStatus.UNEMPLOYED,
                        ),
                    }
                )

            # Secondary income sources (20% of clients)
            if self._rng.random() < 0.20:
                secondary_source = IncomeSource(
                    self._rng.choice(
                        [
                            IncomeSource.RENTAL_INCOME.value,
                            IncomeSource.INVESTMENTS.value,
                            IncomeSource.FREELANCE_INCOME.value,
                            IncomeSource.OTHER.value,
                        ]
                    )
                )
                secondary_amount = base_income * self._rng.uniform(0.10, 0.40)
                for month_offset in range(min(num_months, 12)):
                    period = self._today - timedelta(days=month_offset * 30)
                    gross = secondary_amount * (
                        1 + self._rng.normal(0, 0.15)
                    )
                    gross = max(gross, 0)
                    net = gross * 0.79  # Simplified secondary tax
                    records.append(
                        {
                            "record_id": (
                                f"INC-{uuid.uuid4().hex[:12].upper()}"
                            ),
                            "client_id": client_id,
                            "source": secondary_source.value,
                            "monthly_amount": round(gross, 2),
                            "net_monthly_amount": round(net, 2),
                            "currency": "EUR",
                            "is_verified": bool(self._rng.random() < 0.40),
                            "start_date": (
                                self._today - timedelta(days=365)
                            ).isoformat(),
                            "end_date": None,
                            "period_date": period.isoformat(),
                            "is_regular": False,
                        }
                    )

        return pd.DataFrame(records)

    # ── Credit Position Generation ───────────────────────────────────────

    def _generate_credit_positions(
        self,
        clients_df: pd.DataFrame,
        client_income: dict[str, float],
    ) -> pd.DataFrame:
        """
        Generate credit positions correlated with client income and profile.

        Debt levels are calibrated to produce realistic DTI distributions,
        including stressed scenarios (high DTI, delinquency, default).
        """
        records: list[dict[str, Any]] = []

        for _, client in clients_df.iterrows():
            client_id = client["client_id"]
            segment = ClientSegment(client["segment"])
            age = self._calculate_age_from_dob(client["date_of_birth"])
            monthly_income = client_income.get(client_id, 2000.0)

            num_positions = self._sample_num_positions(segment, age)
            if num_positions == 0:
                continue

            # Determine client stress profile (5% high-stress, 15% moderate)
            stress_roll = self._rng.random()
            if stress_roll < 0.05:
                stress = "high"
            elif stress_roll < 0.20:
                stress = "moderate"
            else:
                stress = "normal"

            products = self._sample_product_mix(num_positions, segment, age)

            for product_type in products:
                position = self._generate_single_position(
                    client_id=client_id,
                    product_type=product_type,
                    monthly_income=monthly_income,
                    age=age,
                    stress=stress,
                )
                records.append(position)

        return pd.DataFrame(records)

    def _generate_single_position(
        self,
        client_id: str,
        product_type: CreditProductType,
        monthly_income: float,
        age: int,
        stress: str,
    ) -> dict[str, Any]:
        """Generate a single credit position with realistic parameters."""
        annual_income = monthly_income * 12

        # Product-specific parameters
        params = self._get_product_parameters(
            product_type, annual_income, age
        )

        original_amount = params["original_amount"]
        interest_rate = params["interest_rate"]
        term_months = params["term_months"]
        is_secured = params["is_secured"]

        # Calculate origination and maturity dates
        months_elapsed = int(self._rng.integers(1, max(term_months // 2, 2)))
        origination_date = self._today - timedelta(days=months_elapsed * 30)
        maturity_date = origination_date + timedelta(days=int(term_months) * 30)

        # Calculate outstanding balance (amortization)
        if product_type in (
            CreditProductType.CREDIT_CARD,
            CreditProductType.CREDIT_LINE,
        ):
            # Revolving: utilization-based
            utilization = self._rng.beta(2, 3)  # Skewed toward lower util
            if stress == "high":
                utilization = min(utilization + 0.4, 0.99)
            elif stress == "moderate":
                utilization = min(utilization + 0.2, 0.95)
            outstanding = original_amount * utilization
            credit_limit = original_amount
        else:
            # Amortizing: linear approximation
            amort_fraction = months_elapsed / term_months
            outstanding = original_amount * (1 - amort_fraction * 0.8)
            credit_limit = original_amount

        # Monthly payment
        monthly_rate = interest_rate / 12
        if monthly_rate > 0 and term_months > 0:
            if product_type in (
                CreditProductType.CREDIT_CARD,
                CreditProductType.CREDIT_LINE,
            ):
                monthly_payment = outstanding * max(monthly_rate * 1.5, 0.02)
            else:
                # Standard amortization formula
                monthly_payment = (
                    original_amount
                    * monthly_rate
                    * (1 + monthly_rate) ** term_months
                ) / ((1 + monthly_rate) ** term_months - 1)
        else:
            monthly_payment = outstanding / max(term_months, 1)

        # Payment status (stress-dependent)
        payment_status, days_past_due = self._sample_payment_status(stress)
        late_12m, late_lifetime = self._sample_late_payments(
            stress, months_elapsed
        )

        # Collateral for secured products
        collateral_value = 0.0
        if is_secured:
            ltv = self._rng.uniform(0.60, 0.90)
            collateral_value = original_amount / ltv

        restructured = stress == "high" and self._rng.random() < 0.25

        return {
            "position_id": f"POS-{uuid.uuid4().hex[:12].upper()}",
            "client_id": client_id,
            "product_type": product_type.value,
            "original_amount": round(original_amount, 2),
            "outstanding_balance": round(max(outstanding, 0), 2),
            "credit_limit": round(credit_limit, 2),
            "monthly_payment": round(max(monthly_payment, 0), 2),
            "interest_rate": round(interest_rate, 4),
            "origination_date": origination_date.isoformat(),
            "maturity_date": maturity_date.isoformat(),
            "payment_status": payment_status.value,
            "days_past_due": days_past_due,
            "num_late_payments_12m": late_12m,
            "num_late_payments_lifetime": late_lifetime,
            "collateral_value": round(collateral_value, 2),
            "is_secured": is_secured,
            "restructured": restructured,
        }

    # ── Sampling Helpers ─────────────────────────────────────────────────

    def _sample_age(self) -> int:
        """Sample client age with realistic banking distribution."""
        # Mixture of distributions for different demographics
        component = self._rng.choice([0, 1, 2], p=[0.25, 0.50, 0.25])
        if component == 0:
            age = int(self._rng.normal(30, 5))   # Young professionals
        elif component == 1:
            age = int(self._rng.normal(45, 8))   # Established adults
        else:
            age = int(self._rng.normal(62, 7))   # Pre/post retirement
        return max(18, min(age, 85))

    def _sample_employment(self, age: int) -> EmploymentStatus:
        """Sample employment status correlated with age."""
        if age >= 65:
            return EmploymentStatus(
                self._rng.choice(
                    [
                        EmploymentStatus.RETIRED.value,
                        EmploymentStatus.SELF_EMPLOYED.value,
                        EmploymentStatus.EMPLOYED_PERMANENT.value,
                    ],
                    p=[0.70, 0.15, 0.15],
                )
            )
        if age < 25:
            return EmploymentStatus(
                self._rng.choice(
                    [
                        EmploymentStatus.EMPLOYED_TEMPORARY.value,
                        EmploymentStatus.STUDENT.value,
                        EmploymentStatus.FREELANCE.value,
                        EmploymentStatus.EMPLOYED_PERMANENT.value,
                        EmploymentStatus.UNEMPLOYED.value,
                    ],
                    p=[0.30, 0.25, 0.15, 0.15, 0.15],
                )
            )
        return EmploymentStatus(
            self._rng.choice(
                [
                    EmploymentStatus.EMPLOYED_PERMANENT.value,
                    EmploymentStatus.SELF_EMPLOYED.value,
                    EmploymentStatus.EMPLOYED_TEMPORARY.value,
                    EmploymentStatus.FREELANCE.value,
                    EmploymentStatus.UNEMPLOYED.value,
                ],
                p=[0.55, 0.20, 0.10, 0.10, 0.05],
            )
        )

    def _sample_segment(
        self, age: int, employment: EmploymentStatus
    ) -> ClientSegment:
        """Sample client segment based on age and employment."""
        if employment == EmploymentStatus.UNEMPLOYED:
            return ClientSegment.RETAIL
        if employment == EmploymentStatus.STUDENT:
            return ClientSegment.RETAIL

        if age > 50 and self._rng.random() < 0.15:
            return ClientSegment.PRIVATE_BANKING

        return ClientSegment(
            self._rng.choice(
                [
                    ClientSegment.RETAIL.value,
                    ClientSegment.PREMIUM.value,
                    ClientSegment.PRIVATE_BANKING.value,
                    ClientSegment.SME.value,
                ],
                p=[0.55, 0.25, 0.05, 0.15],
            )
        )

    def _sample_employment_years(
        self, age: int, employment: EmploymentStatus
    ) -> float:
        """Sample employment years correlated with age and status."""
        if employment in (
            EmploymentStatus.UNEMPLOYED,
            EmploymentStatus.STUDENT,
        ):
            return 0.0
        max_years = max(age - 18, 1)
        if employment == EmploymentStatus.EMPLOYED_PERMANENT:
            years = self._rng.exponential(scale=8.0)
        elif employment == EmploymentStatus.SELF_EMPLOYED:
            years = self._rng.exponential(scale=10.0)
        elif employment == EmploymentStatus.RETIRED:
            years = self._rng.uniform(20, min(max_years, 45))
        else:
            years = self._rng.exponential(scale=3.0)
        return round(min(years, max_years), 1)

    def _sample_relationship_years(self, age: int) -> float:
        """Sample banking relationship length correlated with age."""
        max_rel = max(age - 18, 0.5)
        years = self._rng.exponential(scale=7.0)
        return round(min(years, max_rel), 1)

    def _sample_education(self, age: int, segment: ClientSegment) -> str:
        """Sample education level correlated with segment and age."""
        if segment == ClientSegment.PRIVATE_BANKING:
            return str(
                self._rng.choice(
                    _EDUCATION_LEVELS,
                    p=[0.02, 0.05, 0.08, 0.35, 0.35, 0.15],
                )
            )
        if segment == ClientSegment.PREMIUM:
            return str(
                self._rng.choice(
                    _EDUCATION_LEVELS,
                    p=[0.05, 0.10, 0.15, 0.35, 0.25, 0.10],
                )
            )
        return str(
            self._rng.choice(
                _EDUCATION_LEVELS,
                p=[0.10, 0.25, 0.20, 0.25, 0.15, 0.05],
            )
        )

    def _calculate_base_income(
        self,
        age: int,
        segment: ClientSegment,
        employment: EmploymentStatus,
        education: str,
    ) -> float:
        """
        Calculate base monthly income with realistic correlations.

        Factors: age-experience curve, segment, employment type, education.
        """
        # Base by segment (monthly EUR)
        segment_base = {
            ClientSegment.RETAIL: 1_800,
            ClientSegment.PREMIUM: 4_500,
            ClientSegment.PRIVATE_BANKING: 12_000,
            ClientSegment.SME: 3_500,
            ClientSegment.CORPORATE: 6_000,
        }
        base = segment_base.get(segment, 2_000)

        # Age-experience multiplier (peaks around 50-55)
        if age < 25:
            age_mult = 0.60
        elif age < 35:
            age_mult = 0.85 + (age - 25) * 0.015
        elif age < 55:
            age_mult = 1.0 + (age - 35) * 0.01
        else:
            age_mult = 1.15 - (age - 55) * 0.01

        # Education multiplier
        edu_mult = {
            "primary": 0.75,
            "secondary": 0.90,
            "vocational": 1.00,
            "bachelor": 1.15,
            "master": 1.35,
            "doctorate": 1.50,
        }.get(education, 1.0)

        # Employment stability multiplier
        emp_mult = {
            EmploymentStatus.EMPLOYED_PERMANENT: 1.0,
            EmploymentStatus.EMPLOYED_TEMPORARY: 0.85,
            EmploymentStatus.SELF_EMPLOYED: 1.10,
            EmploymentStatus.FREELANCE: 0.90,
            EmploymentStatus.RETIRED: 0.70,
            EmploymentStatus.UNEMPLOYED: 0.20,
            EmploymentStatus.STUDENT: 0.15,
        }.get(employment, 0.80)

        income = base * age_mult * edu_mult * emp_mult
        # Add individual noise (±15%)
        income *= 1 + self._rng.normal(0, 0.15)
        return max(income, 400)  # Minimum subsistence

    def _estimate_tax_rate(self, annual_income: float) -> float:
        """Estimate effective tax rate based on Spanish IRPF brackets."""
        if annual_income <= 12_450:
            return 0.19
        elif annual_income <= 20_200:
            return 0.22
        elif annual_income <= 35_200:
            return 0.26
        elif annual_income <= 60_000:
            return 0.30
        elif annual_income <= 300_000:
            return 0.35
        else:
            return 0.40

    def _map_employment_to_income_source(
        self, employment: EmploymentStatus
    ) -> IncomeSource:
        """Map employment status to primary income source type."""
        mapping = {
            EmploymentStatus.EMPLOYED_PERMANENT: IncomeSource.SALARY,
            EmploymentStatus.EMPLOYED_TEMPORARY: IncomeSource.SALARY,
            EmploymentStatus.SELF_EMPLOYED: IncomeSource.BUSINESS_INCOME,
            EmploymentStatus.FREELANCE: IncomeSource.FREELANCE_INCOME,
            EmploymentStatus.RETIRED: IncomeSource.PENSION,
            EmploymentStatus.UNEMPLOYED: IncomeSource.GOVERNMENT_BENEFITS,
            EmploymentStatus.STUDENT: IncomeSource.OTHER,
        }
        return mapping.get(employment, IncomeSource.OTHER)

    def _sample_num_positions(
        self, segment: ClientSegment, age: int
    ) -> int:
        """Sample number of credit positions per client."""
        if age < 22:
            return int(self._rng.choice([0, 1], p=[0.60, 0.40]))

        base_probs = {
            ClientSegment.RETAIL: [0.15, 0.35, 0.30, 0.15, 0.05],
            ClientSegment.PREMIUM: [0.05, 0.20, 0.30, 0.25, 0.20],
            ClientSegment.PRIVATE_BANKING: [0.05, 0.15, 0.25, 0.30, 0.25],
            ClientSegment.SME: [0.10, 0.25, 0.30, 0.20, 0.15],
            ClientSegment.CORPORATE: [0.05, 0.15, 0.25, 0.30, 0.25],
        }
        probs = base_probs.get(
            segment, [0.15, 0.35, 0.30, 0.15, 0.05]
        )
        return int(self._rng.choice([0, 1, 2, 3, 4], p=probs))

    def _sample_product_mix(
        self,
        num_positions: int,
        segment: ClientSegment,
        age: int,
    ) -> list[CreditProductType]:
        """Sample a realistic mix of credit products."""
        products: list[CreditProductType] = []

        # Mortgage probability based on age
        if age >= 25 and num_positions >= 1:
            mortgage_prob = min(0.40, 0.10 + (age - 25) * 0.01)
            if self._rng.random() < mortgage_prob:
                products.append(CreditProductType.MORTGAGE)

        remaining = num_positions - len(products)
        if remaining <= 0:
            return products

        other_products = [
            CreditProductType.PERSONAL_LOAN,
            CreditProductType.CREDIT_CARD,
            CreditProductType.CREDIT_LINE,
            CreditProductType.AUTO_LOAN,
        ]
        weights = [0.25, 0.35, 0.20, 0.20]

        for _ in range(remaining):
            product = CreditProductType(
                self._rng.choice(
                    [p.value for p in other_products], p=weights
                )
            )
            products.append(product)

        return products

    def _get_product_parameters(
        self,
        product_type: CreditProductType,
        annual_income: float,
        age: int,
    ) -> dict[str, Any]:
        """Get product-specific financial parameters."""
        if product_type == CreditProductType.MORTGAGE:
            # Mortgage: 3-6x annual income, 15-30 year term
            multiplier = self._rng.uniform(3.0, 6.0)
            return {
                "original_amount": annual_income * multiplier,
                "interest_rate": self._rng.uniform(0.015, 0.04),
                "term_months": int(self._rng.choice([180, 240, 300, 360])),
                "is_secured": True,
            }
        elif product_type == CreditProductType.PERSONAL_LOAN:
            multiplier = self._rng.uniform(0.3, 1.5)
            return {
                "original_amount": annual_income * multiplier,
                "interest_rate": self._rng.uniform(0.05, 0.12),
                "term_months": int(
                    self._rng.choice([12, 24, 36, 48, 60, 72, 84])
                ),
                "is_secured": False,
            }
        elif product_type == CreditProductType.CREDIT_CARD:
            limit_mult = self._rng.uniform(0.1, 0.5)
            return {
                "original_amount": annual_income * limit_mult,
                "interest_rate": self._rng.uniform(0.15, 0.25),
                "term_months": 120,  # Revolving, no fixed term
                "is_secured": False,
            }
        elif product_type == CreditProductType.CREDIT_LINE:
            limit_mult = self._rng.uniform(0.2, 0.8)
            return {
                "original_amount": annual_income * limit_mult,
                "interest_rate": self._rng.uniform(0.08, 0.18),
                "term_months": int(self._rng.choice([12, 24, 36, 60])),
                "is_secured": False,
            }
        else:  # AUTO_LOAN
            return {
                "original_amount": self._rng.uniform(10_000, 50_000),
                "interest_rate": self._rng.uniform(0.04, 0.09),
                "term_months": int(
                    self._rng.choice([36, 48, 60, 72, 84])
                ),
                "is_secured": True,
            }

    def _sample_payment_status(
        self, stress: str
    ) -> tuple[PaymentStatus, int]:
        """Sample payment status based on stress level."""
        if stress == "high":
            status = PaymentStatus(
                self._rng.choice(
                    [
                        PaymentStatus.CURRENT.value,
                        PaymentStatus.DAYS_30.value,
                        PaymentStatus.DAYS_60.value,
                        PaymentStatus.DAYS_90.value,
                        PaymentStatus.DAYS_120_PLUS.value,
                        PaymentStatus.DEFAULT.value,
                        PaymentStatus.RESTRUCTURED.value,
                    ],
                    p=[0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.10],
                )
            )
        elif stress == "moderate":
            status = PaymentStatus(
                self._rng.choice(
                    [
                        PaymentStatus.CURRENT.value,
                        PaymentStatus.DAYS_30.value,
                        PaymentStatus.DAYS_60.value,
                        PaymentStatus.DAYS_90.value,
                    ],
                    p=[0.55, 0.25, 0.12, 0.08],
                )
            )
        else:
            status = PaymentStatus(
                self._rng.choice(
                    [
                        PaymentStatus.CURRENT.value,
                        PaymentStatus.DAYS_30.value,
                        PaymentStatus.DAYS_60.value,
                    ],
                    p=[0.90, 0.07, 0.03],
                )
            )

        dpd_map = {
            PaymentStatus.CURRENT: 0,
            PaymentStatus.DAYS_30: int(self._rng.integers(1, 31)),
            PaymentStatus.DAYS_60: int(self._rng.integers(31, 61)),
            PaymentStatus.DAYS_90: int(self._rng.integers(61, 91)),
            PaymentStatus.DAYS_120_PLUS: int(self._rng.integers(91, 365)),
            PaymentStatus.DEFAULT: int(self._rng.integers(120, 730)),
            PaymentStatus.RESTRUCTURED: 0,
        }
        return status, dpd_map.get(status, 0)

    def _sample_late_payments(
        self, stress: str, months_elapsed: int
    ) -> tuple[int, int]:
        """Sample late payment counts based on stress level."""
        if stress == "high":
            high_upper = max(3, min(months_elapsed, 12) + 1)
            late_12m = int(self._rng.integers(2, high_upper))
            late_life = late_12m + int(self._rng.integers(0, 8))
        elif stress == "moderate":
            late_12m = int(self._rng.integers(0, 4))
            late_life = late_12m + int(self._rng.integers(0, 5))
        else:
            late_12m = int(
                self._rng.choice([0, 0, 0, 0, 1], p=[0.80, 0.05, 0.05, 0.05, 0.05])
            )
            late_life = late_12m + int(
                self._rng.choice([0, 1, 2], p=[0.70, 0.20, 0.10])
            )
        return late_12m, late_life

    # ── Utility Methods ──────────────────────────────────────────────────

    def _generate_national_id(self) -> str:
        """Generate a synthetic anonymized national ID."""
        digits = "".join(str(d) for d in self._rng.integers(0, 10, size=8))
        letter = chr(self._rng.integers(65, 91))
        return f"{digits}{letter}"

    def _calculate_age_from_dob(self, dob_str: str) -> int:
        """Calculate age from a date-of-birth string."""
        dob = date.fromisoformat(dob_str)
        today = self._today
        return (
            today.year
            - dob.year
            - ((today.month, today.day) < (dob.month, dob.day))
        )
