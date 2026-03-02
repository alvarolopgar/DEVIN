"""
Abstract interfaces (ports) for the Credit Risk Decision Engine.

Defines contracts that infrastructure and service layers must implement,
enabling dependency inversion and testability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from credit_risk_engine.domain.models import (
    Client,
    ClientRiskAssessment,
    CreditPosition,
    IncomeRecord,
    PortfolioRiskSummary,
)


class ClientRepository(ABC):
    """Interface for client data access."""

    @abstractmethod
    def get_all_clients(self) -> list[Client]:
        """Retrieve all clients from the data source."""
        ...

    @abstractmethod
    def get_client_by_id(self, client_id: str) -> Client | None:
        """Retrieve a specific client by ID."""
        ...

    @abstractmethod
    def get_client_count(self) -> int:
        """Return total number of clients."""
        ...


class IncomeRepository(ABC):
    """Interface for income record data access."""

    @abstractmethod
    def get_all_income_records(self) -> list[IncomeRecord]:
        """Retrieve all income records."""
        ...

    @abstractmethod
    def get_income_by_client(self, client_id: str) -> list[IncomeRecord]:
        """Retrieve all income records for a specific client."""
        ...

    @abstractmethod
    def get_active_income_by_client(self, client_id: str) -> list[IncomeRecord]:
        """Retrieve only active income records for a client."""
        ...


class CreditPositionRepository(ABC):
    """Interface for credit position data access."""

    @abstractmethod
    def get_all_positions(self) -> list[CreditPosition]:
        """Retrieve all credit positions."""
        ...

    @abstractmethod
    def get_positions_by_client(self, client_id: str) -> list[CreditPosition]:
        """Retrieve all positions for a specific client."""
        ...

    @abstractmethod
    def get_delinquent_positions(self) -> list[CreditPosition]:
        """Retrieve all positions that are past due or in default."""
        ...


class RiskAnalyzer(ABC):
    """Interface for individual client risk analysis."""

    @abstractmethod
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
            A complete risk assessment for the client.
        """
        ...


class PortfolioAnalyzer(ABC):
    """Interface for portfolio-level risk aggregation."""

    @abstractmethod
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
            Portfolio-level risk summary.
        """
        ...


class ReportGenerator(ABC):
    """Interface for risk report generation."""

    @abstractmethod
    def generate_report(
        self,
        portfolio_summary: PortfolioRiskSummary,
        client_assessments: list[ClientRiskAssessment],
        output_path: str,
    ) -> str:
        """
        Generate a structured risk report.

        Args:
            portfolio_summary: Aggregated portfolio risk data.
            client_assessments: Individual client assessments.
            output_path: Directory where the report will be saved.

        Returns:
            Path to the generated report file.
        """
        ...
