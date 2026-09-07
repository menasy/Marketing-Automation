"""Headless CLI application entry point for running the marketing automation pipeline."""

import argparse
import asyncio
import sys
from datetime import date

from src.application.dto.pipeline_request import PipelineRequest
from src.application.use_cases.run_pipeline import RunPipelineUseCase
from src.domain.exceptions import DomainException


def build_parser() -> argparse.ArgumentParser:
    """Builds and configures argument parser for CLI execution."""
    parser = argparse.ArgumentParser(
        description="Marketing Automation Anomaly Detection Pipeline CLI"
    )
    parser.add_argument(
        "--google-csv",
        type=str,
        default=None,
        help="Path to Google Ads daily CSV export",
    )
    parser.add_argument(
        "--meta-csv",
        type=str,
        default=None,
        help="Path to Meta Ads daily CSV export",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Directory containing google_ads_daily.csv and meta_ads_daily.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory where artifact deliverables will be written (default: output)",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=14,
        help="Historical baseline sliding window size in days (default: 14)",
    )
    parser.add_argument(
        "--target-date",
        "--date",
        type=str,
        default=None,
        dest="target_date",
        help="Target evaluation date in YYYY-MM-DD format (default: max date in data)",
    )
    parser.add_argument(
        "--currency",
        type=str,
        default="USD",
        help="Target ISO currency code for financial normalization (default: USD)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point function.

    Args:
        argv: Optional list of command-line argument strings.

    Returns:
        Exit status code (0 for success/partial_success, 1 for failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    target_dt: date | None = None
    if args.target_date:
        try:
            target_dt = date.fromisoformat(args.target_date)
        except ValueError:
            print(
                f"Error: Invalid date format for --target-date '{args.target_date}'. "
                "Expected YYYY-MM-DD.",
                file=sys.stderr,
            )
            return 1

    try:
        request = PipelineRequest(
            google_csv_path=args.google_csv,
            meta_csv_path=args.meta_csv,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            window_days=args.window_days,
            reporting_currency=args.currency,
            target_date=target_dt,
        )

        use_case = RunPipelineUseCase()
        result = asyncio.run(use_case.execute(request))

        print("\n==================================================")
        print("     MARKETING AUTOMATION PIPELINE SUMMARY        ")
        print("==================================================")
        print(f"Execution ID     : {result.execution_id}")
        print(f"Status           : {result.status.upper()}")
        print(f"Duration         : {result.duration_seconds:.2f} seconds")
        print(f"Anomalies Found  : {result.anomalies_count}")
        print(f"Critical Count   : {result.critical_count}")
        print("--------------------------------------------------")
        print("Stage Statuses:")
        for stage, status in result.stage_statuses.items():
            print(f"  - {stage:<20}: {status}")
        print("--------------------------------------------------")
        print("Output Files:")
        for file_key, file_path in result.output_files.items():
            print(f"  - {file_key:<20}: {file_path}")
        print("==================================================\n")

        if result.status == "failed":
            print("Pipeline execution failed.", file=sys.stderr)
            return 1

        return 0

    except (DomainException, ValueError, RuntimeError) as err:
        print(f"Pipeline Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
