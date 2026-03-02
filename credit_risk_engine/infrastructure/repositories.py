"""
Parquet-based repository implementations.

Concrete implementations of the domain repository interfaces,
reading data from Apache Parquet files. These can be swapped
for database-backed implementations without changing the domain
or service layers.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from credit_risk_engine.domain.enums import (
    ClientSegment,
    CreditProductType,
    EmploymentStatus,
    IncomeSource,
    PaymentStatus,
)
from credit_risk_engine.domain.interfaces import (
    ClientRepository,
    CreditPositionRepository,
    IncomeRepository,
)
from credit_risk_engine.domain.models import Client, CreditPosition, IncomeRecord

logger = logging.getLogger(__name__)


def _safe_date(value: object) -> date:
    """Convert various date representations to a date object."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _safe_optional_date(value: object) -> date | None:
    """Convert to optional date, handling None/NaT."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp) and pd.isna(value):
        return None
    return _safe_date(value)


class ParquetClientRepository(ClientRepository):
    """
    Client repository backed by Parquet files.

    Args:
        data_path: Path to the clients Parquet file.
    """

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        self._df: pd.DataFrame | None = None

    def _ensure_loaded(self) -> pd.DataFrame:
        """Lazy-load the Parquet file on first access."""
        if self._df is None:
            logger.info("Loading clients from %s", self._data_path)
            self._df = pd.read_parquet(self._data_path, engine="pyarrow")
            logger.info("Loaded %d client records", len(self._df))
        return self._df

    def get_all_clients(self) -> list[Client]:
        """Retrieve all clients from the Parquet file."""
        df = self._ensure_loaded()
        clients: list[Client] = []
        for _, row in df.iterrows():
            clients.append(self._row_to_client(row))
        return clients

    def get_client_by_id(self, client_id: str) -> Client | None:
        """Retrieve a specific client by ID."""
        df = self._ensure_loaded()
        filtered = df[df["client_id"] == client_id]
        if filtered.empty:
            return None
        return self._row_to_client(filtered.iloc[0])

    def get_client_count(self) -> int:
        """Return total number of clients."""
        df = self._ensure_loaded()
        return len(df)

    @staticmethod
    def _row_to_client(row: pd.Series) -> Client:
        """Convert a DataFrame row to a Client domain entity."""
        return Client(
            client_id=str(row["client_id"]),
            first_name=str(row["first_name"]),
            last_name=str(row["last_name"]),
            date_of_birth=_safe_date(row["date_of_birth"]),
            national_id=str(row["national_id"]),
            segment=ClientSegment(row["segment"]),
            employment_status=EmploymentStatus(row["employment_status"]),
            employment_years=float(row["employment_years"]),
            relationship_start_date=_safe_date(row["relationship_start_date"]),
            province=str(row["province"]),
            has_guarantor=bool(row["has_guarantor"]),
            num_dependents=int(row["num_dependents"]),
            education_level=str(row["education_level"]),
            marital_status=str(row["marital_status"]),
        )


class ParquetIncomeRepository(IncomeRepository):
    """
    Income repository backed by Parquet files.

    Args:
        data_path: Path to the income records Parquet file.
    """

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        self._df: pd.DataFrame | None = None

    def _ensure_loaded(self) -> pd.DataFrame:
        """Lazy-load the Parquet file on first access."""
        if self._df is None:
            logger.info("Loading income records from %s", self._data_path)
            self._df = pd.read_parquet(self._data_path, engine="pyarrow")
            logger.info("Loaded %d income records", len(self._df))
        return self._df

    def get_all_income_records(self) -> list[IncomeRecord]:
        """Retrieve all income records."""
        df = self._ensure_loaded()
        return [self._row_to_income(row) for _, row in df.iterrows()]

    def get_income_by_client(self, client_id: str) -> list[IncomeRecord]:
        """Retrieve all income records for a specific client."""
        df = self._ensure_loaded()
        filtered = df[df["client_id"] == client_id]
        return [self._row_to_income(row) for _, row in filtered.iterrows()]

    def get_active_income_by_client(
        self, client_id: str
    ) -> list[IncomeRecord]:
        """Retrieve only active income records for a client."""
        df = self._ensure_loaded()
        filtered = df[
            (df["client_id"] == client_id) & (df["end_date"].isna())
        ]
        return [self._row_to_income(row) for _, row in filtered.iterrows()]

    @staticmethod
    def _row_to_income(row: pd.Series) -> IncomeRecord:
        """Convert a DataFrame row to an IncomeRecord domain entity."""
        return IncomeRecord(
            record_id=str(row["record_id"]),
            client_id=str(row["client_id"]),
            source=IncomeSource(row["source"]),
            monthly_amount=float(row["monthly_amount"]),
            net_monthly_amount=float(row["net_monthly_amount"]),
            currency=str(row.get("currency", "EUR")),
            is_verified=bool(row["is_verified"]),
            start_date=_safe_optional_date(row.get("start_date")),
            end_date=_safe_optional_date(row.get("end_date")),
            period_date=_safe_optional_date(row.get("period_date")),
            is_regular=bool(row["is_regular"]),
        )


class ParquetCreditPositionRepository(CreditPositionRepository):
    """
    Credit position repository backed by Parquet files.

    Args:
        data_path: Path to the credit positions Parquet file.
    """

    def __init__(self, data_path: Path) -> None:
        self._data_path = data_path
        self._df: pd.DataFrame | None = None

    def _ensure_loaded(self) -> pd.DataFrame:
        """Lazy-load the Parquet file on first access."""
        if self._df is None:
            logger.info("Loading credit positions from %s", self._data_path)
            self._df = pd.read_parquet(self._data_path, engine="pyarrow")
            logger.info("Loaded %d credit position records", len(self._df))
        return self._df

    def get_all_positions(self) -> list[CreditPosition]:
        """Retrieve all credit positions."""
        df = self._ensure_loaded()
        return [self._row_to_position(row) for _, row in df.iterrows()]

    def get_positions_by_client(
        self, client_id: str
    ) -> list[CreditPosition]:
        """Retrieve all positions for a specific client."""
        df = self._ensure_loaded()
        filtered = df[df["client_id"] == client_id]
        return [
            self._row_to_position(row) for _, row in filtered.iterrows()
        ]

    def get_delinquent_positions(self) -> list[CreditPosition]:
        """Retrieve all positions that are past due or in default."""
        df = self._ensure_loaded()
        delinquent_statuses = [
            PaymentStatus.DAYS_30.value,
            PaymentStatus.DAYS_60.value,
            PaymentStatus.DAYS_90.value,
            PaymentStatus.DAYS_120_PLUS.value,
            PaymentStatus.DEFAULT.value,
        ]
        filtered = df[df["payment_status"].isin(delinquent_statuses)]
        return [
            self._row_to_position(row) for _, row in filtered.iterrows()
        ]

    @staticmethod
    def _row_to_position(row: pd.Series) -> CreditPosition:
        """Convert a DataFrame row to a CreditPosition domain entity."""
        return CreditPosition(
            position_id=str(row["position_id"]),
            client_id=str(row["client_id"]),
            product_type=CreditProductType(row["product_type"]),
            original_amount=float(row["original_amount"]),
            outstanding_balance=float(row["outstanding_balance"]),
            credit_limit=float(row["credit_limit"]),
            monthly_payment=float(row["monthly_payment"]),
            interest_rate=float(row["interest_rate"]),
            origination_date=_safe_date(row["origination_date"]),
            maturity_date=_safe_date(row["maturity_date"]),
            payment_status=PaymentStatus(row["payment_status"]),
            days_past_due=int(row["days_past_due"]),
            num_late_payments_12m=int(row["num_late_payments_12m"]),
            num_late_payments_lifetime=int(row["num_late_payments_lifetime"]),
            collateral_value=float(row["collateral_value"]),
            is_secured=bool(row["is_secured"]),
            restructured=bool(row["restructured"]),
        )
