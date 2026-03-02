"""
Risk assessment pipeline orchestrator.

Coordinates the end-to-end flow from data ingestion through analysis
to report generation. Designed as the main integration point for
microservice deployment.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from credit_risk_engine.config.settings import EngineSettings
from credit_risk_engine.domain.interfaces import (
    ClientRepository,
    CreditPositionRepository,
    IncomeRepository,
)
from credit_risk_engine.domain.models import (
    ClientRiskAssessment,
    PortfolioRiskSummary,
)
from credit_risk_engine.reporting.report_generator import JsonReportGenerator
from credit_risk_engine.services.credit_position_analyzer import (
    CreditPositionAnalyzer,
)
from credit_risk_engine.services.default_predictor import DefaultPredictor
from credit_risk_engine.services.income_analyzer import IncomeAnalyzer
from credit_risk_engine.services.loss_calculator import LossCalculator
from credit_risk_engine.services.portfolio_analyzer import PortfolioRiskAnalyzer
from credit_risk_engine.services.risk_assessor import ClientRiskAssessor
from credit_risk_engine.services.scoring_engine import CreditScoringEngine

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a complete pipeline execution."""

    portfolio_summary: PortfolioRiskSummary
    client_assessments: list[ClientRiskAssessment]
    report_path: str | None
    execution_time_seconds: float
    clients_processed: int
    errors: list[str]


class RiskAssessmentPipeline:
    """
    End-to-end risk assessment pipeline.

    Orchestrates:
    1. Data ingestion from repositories
    2. Individual client risk assessment
    3. Portfolio-level aggregation
    4. Report generation

    Designed for dependency injection - all repositories and services
    are provided at construction time, enabling easy testing and
    alternative implementations.

    Args:
        settings: Engine configuration.
        client_repo: Client data repository.
        income_repo: Income data repository.
        position_repo: Credit position data repository.
    """

    def __init__(
        self,
        settings: EngineSettings,
        client_repo: ClientRepository,
        income_repo: IncomeRepository,
        position_repo: CreditPositionRepository,
    ) -> None:
        self._settings = settings
        self._client_repo = client_repo
        self._income_repo = income_repo
        self._position_repo = position_repo

        # Initialize services (wired via DI)
        self._income_analyzer = IncomeAnalyzer()
        self._position_analyzer = CreditPositionAnalyzer()
        self._scoring_engine = CreditScoringEngine(
            weights=settings.scoring_weights,
            score_excellent=settings.risk_thresholds.score_excellent,
            score_good=settings.risk_thresholds.score_good,
            score_fair=settings.risk_thresholds.score_fair,
            score_poor=settings.risk_thresholds.score_poor,
        )
        self._default_predictor = DefaultPredictor()
        self._loss_calculator = LossCalculator(settings.lgd_parameters)

        self._risk_assessor = ClientRiskAssessor(
            settings=settings,
            income_analyzer=self._income_analyzer,
            position_analyzer=self._position_analyzer,
            scoring_engine=self._scoring_engine,
            default_predictor=self._default_predictor,
            loss_calculator=self._loss_calculator,
        )

        self._portfolio_analyzer = PortfolioRiskAnalyzer()
        self._report_generator = JsonReportGenerator(settings.report)

    def execute(self, generate_report: bool = True) -> PipelineResult:
        """
        Execute the complete risk assessment pipeline.

        Args:
            generate_report: Whether to generate the output report.

        Returns:
            PipelineResult with all outputs and execution metadata.
        """
        start_time = time.time()
        errors: list[str] = []

        # ── Step 1: Data Ingestion ──────────────────────────────────────
        logger.info("Step 1/4: Loading data from repositories...")
        clients = self._client_repo.get_all_clients()
        logger.info("  Loaded %d clients", len(clients))

        # Build income and position indexes for efficient lookup
        all_income = self._income_repo.get_all_income_records()
        income_by_client: dict[str, list] = {}
        for record in all_income:
            income_by_client.setdefault(record.client_id, []).append(record)
        logger.info("  Loaded %d income records", len(all_income))

        all_positions = self._position_repo.get_all_positions()
        positions_by_client: dict[str, list] = {}
        for position in all_positions:
            positions_by_client.setdefault(
                position.client_id, []
            ).append(position)
        logger.info("  Loaded %d credit positions", len(all_positions))

        # ── Step 2: Individual Client Assessment ────────────────────────
        logger.info("Step 2/4: Assessing %d clients...", len(clients))
        assessments: list[ClientRiskAssessment] = []
        processed = 0

        for client in clients:
            try:
                client_income = income_by_client.get(client.client_id, [])
                client_positions = positions_by_client.get(
                    client.client_id, []
                )

                assessment = self._risk_assessor.assess_client(
                    client=client,
                    income_records=client_income,
                    credit_positions=client_positions,
                )
                assessments.append(assessment)
                processed += 1

                if processed % 1000 == 0:
                    logger.info("  Processed %d / %d clients", processed, len(clients))

            except Exception as exc:
                error_msg = (
                    f"Error assessing client {client.client_id}: {exc}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        logger.info(
            "  Completed: %d assessed, %d errors",
            len(assessments),
            len(errors),
        )

        # ── Step 3: Portfolio Aggregation ───────────────────────────────
        logger.info("Step 3/4: Aggregating portfolio metrics...")
        portfolio_summary = self._portfolio_analyzer.summarize_portfolio(
            assessments=assessments,
            clients=clients,
        )
        logger.info(
            "  Portfolio: %d clients, %.2f EUR total exposure, %.2f EUR EL",
            portfolio_summary.total_clients,
            portfolio_summary.total_exposure,
            portfolio_summary.total_expected_loss,
        )

        # ── Step 4: Report Generation ───────────────────────────────────
        report_path: str | None = None
        if generate_report:
            logger.info("Step 4/4: Generating risk report...")
            report_path = self._report_generator.generate_report(
                portfolio_summary=portfolio_summary,
                client_assessments=assessments,
                output_path=self._settings.report.output_dir,
            )
            logger.info("  Report saved to: %s", report_path)
        else:
            logger.info("Step 4/4: Report generation skipped.")

        elapsed = time.time() - start_time
        logger.info(
            "Pipeline completed in %.2f seconds (%d clients)",
            elapsed,
            processed,
        )

        return PipelineResult(
            portfolio_summary=portfolio_summary,
            client_assessments=assessments,
            report_path=report_path,
            execution_time_seconds=round(elapsed, 2),
            clients_processed=processed,
            errors=errors,
        )
