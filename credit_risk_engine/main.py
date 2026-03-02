"""
Credit Risk Decision Engine - Main Entry Point.

Provides the CLI interface for running the complete risk assessment pipeline:
1. Generate synthetic data (optional, for testing)
2. Ingest data from Parquet files
3. Execute risk assessment for all clients
4. Generate structured risk report

Usage:
    # Generate synthetic data and run full pipeline
    python -m credit_risk_engine.main --generate-data

    # Run pipeline with existing data
    python -m credit_risk_engine.main --data-dir data/synthetic

    # Custom output directory
    python -m credit_risk_engine.main --generate-data --report-dir reports/custom
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from credit_risk_engine.config.settings import (
    EngineSettings,
    ReportSettings,
    SyntheticDataSettings,
)
from credit_risk_engine.data_generation.synthetic_generator import (
    SyntheticPortfolioGenerator,
)
from credit_risk_engine.infrastructure.repositories import (
    ParquetClientRepository,
    ParquetCreditPositionRepository,
    ParquetIncomeRepository,
)
from credit_risk_engine.pipeline import RiskAssessmentPipeline


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging for the engine."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Credit Risk Decision Engine - Portfolio Risk Assessment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m credit_risk_engine.main --generate-data\n"
            "  python -m credit_risk_engine.main --data-dir data/synthetic\n"
            "  python -m credit_risk_engine.main --generate-data --num-clients 5000\n"
        ),
    )
    parser.add_argument(
        "--generate-data",
        action="store_true",
        default=False,
        help="Generate synthetic test data before running the pipeline",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/synthetic",
        help="Directory containing input Parquet files (default: data/synthetic)",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="reports",
        help="Directory for output reports (default: reports)",
    )
    parser.add_argument(
        "--num-clients",
        type=int,
        default=10_000,
        help="Number of synthetic clients to generate (default: 10000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        default=False,
        help="Skip report generation (assessment only)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the Credit Risk Decision Engine."""
    args = parse_args()
    configure_logging(args.log_level)

    logger = logging.getLogger("credit_risk_engine")
    logger.info("=" * 72)
    logger.info("  CREDIT RISK DECISION ENGINE v1.0.0")
    logger.info("=" * 72)

    data_dir = Path(args.data_dir)

    # ── Phase 1: Data Generation (optional) ─────────────────────────────
    if args.generate_data:
        logger.info("Phase 1: Generating synthetic portfolio data...")
        synthetic_settings = SyntheticDataSettings(
            num_clients=args.num_clients,
            random_seed=args.seed,
            output_dir=args.data_dir,
        )
        generator = SyntheticPortfolioGenerator(synthetic_settings)
        data_paths = generator.generate_all()
        logger.info(
            "Synthetic data generated: %s",
            {k: str(v) for k, v in data_paths.items()},
        )
    else:
        logger.info("Using existing data from: %s", data_dir)

    # ── Validate data files exist ───────────────────────────────────────
    required_files = {
        "clients": data_dir / "clients.parquet",
        "income_records": data_dir / "income_records.parquet",
        "credit_positions": data_dir / "credit_positions.parquet",
    }
    for name, path in required_files.items():
        if not path.exists():
            logger.error("Required data file not found: %s (%s)", name, path)
            sys.exit(1)

    # ── Phase 2: Risk Assessment Pipeline ───────────────────────────────
    logger.info("Phase 2: Executing risk assessment pipeline...")

    # Build settings
    settings = EngineSettings(
        data_dir=args.data_dir,
        report=ReportSettings(output_dir=args.report_dir),
        log_level=args.log_level,
    )

    # Wire repositories (Dependency Injection)
    client_repo = ParquetClientRepository(required_files["clients"])
    income_repo = ParquetIncomeRepository(required_files["income_records"])
    position_repo = ParquetCreditPositionRepository(
        required_files["credit_positions"]
    )

    # Build and execute pipeline
    pipeline = RiskAssessmentPipeline(
        settings=settings,
        client_repo=client_repo,
        income_repo=income_repo,
        position_repo=position_repo,
    )

    result = pipeline.execute(generate_report=not args.no_report)

    # ── Summary ─────────────────────────────────────────────────────────
    logger.info("=" * 72)
    logger.info("  EXECUTION SUMMARY")
    logger.info("=" * 72)
    logger.info("  Clients processed:      %d", result.clients_processed)
    logger.info("  Errors:                 %d", len(result.errors))
    logger.info(
        "  Execution time:         %.2f seconds",
        result.execution_time_seconds,
    )
    logger.info(
        f"  Total exposure (EUR):   {result.portfolio_summary.total_exposure:,.2f}"
    )
    logger.info(
        f"  Total expected loss:    {result.portfolio_summary.total_expected_loss:,.2f}"
    )
    logger.info(
        f"  Avg PD:                 {result.portfolio_summary.avg_probability_of_default:.4%}"
    )
    logger.info(
        f"  Avg DTI:                {result.portfolio_summary.avg_dti_ratio:.2%}"
    )
    logger.info(
        "  Avg Credit Score:       %.0f",
        result.portfolio_summary.avg_credit_score,
    )
    logger.info(
        f"  Delinquency rate:       {result.portfolio_summary.delinquency_rate:.2%}"
    )
    logger.info(
        f"  Default rate:           {result.portfolio_summary.default_rate:.2%}"
    )
    logger.info("  Risk distribution:      %s", result.portfolio_summary.risk_distribution)

    if result.report_path:
        logger.info("  Report path:            %s", result.report_path)

    if result.errors:
        logger.warning("  Errors encountered:")
        for err in result.errors[:10]:
            logger.warning("    - %s", err)

    logger.info("=" * 72)


if __name__ == "__main__":
    main()
