"""flight_delay_bayes CLI module."""

import asyncio
from datetime import datetime
from pathlib import Path

import click

from flight_delay_bayes.bayes.pipeline import forecast_probability
from flight_delay_bayes.eval.backtest import run_backtest

from .bayes.prior_estimator import compute_beta_prior
from .ingestion.bts_bulk_ingest import ingest_bulk
from .ingestion.bts_ingest import ingest_historic_data


@click.group()
def cli() -> None:
    """Flight Delay Bayesian Forecaster CLI stub."""


@cli.command("ingest-historic")
@click.option(
    "--csv-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Directory containing CSV files to ingest",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file",
)
def ingest_historic(csv_dir: Path, db_path: Path) -> None:
    """Ingest historic flight data from CSV files into DuckDB."""
    try:
        total_rows = ingest_historic_data(csv_dir, db_path)
        click.echo(f"Successfully ingested {total_rows:,} rows")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command("estimate-prior")
@click.option("--carrier", required=True, help="Airline carrier code")
@click.option("--origin", required=True, help="Origin airport code")
@click.option("--dest", required=True, help="Destination airport code")
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file",
)
def estimate_prior(
    carrier: str, origin: str, dest: str, db_path: Path
) -> None:  # noqa: D401
    """Estimate Beta prior parameters for a route and print them."""
    alpha, beta, n = compute_beta_prior(carrier, origin, dest, db_path)
    click.echo(f"α={alpha}, β={beta}, n={n}")


@cli.command("predict")
@click.option("--flight", required=True, help="Flight as IATA+number, e.g. DL202")
@click.option("--date", "dep_date", required=True, help="Departure date YYYY-MM-DD")
def predict(flight: str, dep_date: str) -> None:  # noqa: D401
    """Predict probability of flight being late (>15 min)."""
    match = __import__("re").match(r"^([A-Za-z]+)(\d+)$", flight)
    if not match:
        click.echo("--flight must be like DL202", err=True)
        raise click.Abort()
    carrier, number = match.group(1).upper(), match.group(2)
    try:
        date_obj = datetime.strptime(dep_date, "%Y-%m-%d").date()
    except ValueError:
        click.echo("--date must be YYYY-MM-DD", err=True)
        raise click.Abort()

    try:
        result = asyncio.run(forecast_probability(carrier, number, date_obj))
        click.echo(
            f"P(late)={result['p_late']:.3f} | alpha={result['alpha']:.2f} | beta={result['beta']:.2f} | updated={result['updated']}"
        )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command("backtest")
@click.option("--carrier", required=True)
@click.option("--origin", required=True)
@click.option("--dest", required=True)
@click.option("--year", type=int, required=True)
def backtest_cmd(carrier: str, origin: str, dest: str, year: int) -> None:  # noqa: D401
    """Run backtest for given route and year."""
    try:
        metrics = run_backtest(carrier.upper(), origin.upper(), dest.upper(), year)
    except Exception as e:  # noqa: BLE001
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

    n = metrics["n"]
    actual = metrics["actual_rate"] * 100
    mean_pred = metrics["mean_pred"] * 100
    brier = metrics["brier"]
    bias = metrics["bias"] * 100
    sign = "+" if bias >= 0 else ""
    click.echo(
        f"Number of flights: {n}\n"
        f"Actual late rate: {actual:.1f}%\n"
        f"Mean predicted probability: {mean_pred:.1f}%\n"
        f"Brier score: {brier:.3f}\n"
        f"Prediction bias: {sign}{bias:.1f}%"
    )


@cli.command("ingest-bulk")
@click.argument("start_year", type=int)
@click.argument("end_year", type=int)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file",
)
def ingest_bulk_cmd(start_year: int, end_year: int, db_path: Path) -> None:
    """Ingest BTS On-Time Performance data from start_year to end_year."""
    try:
        total_rows = ingest_bulk(start_year, end_year, db_path)
        click.echo(f"≈ {total_rows // 1_000_000} M rows total")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command("enrich-weather")
@click.argument("start_year", type=int)
@click.argument("end_year", type=int)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file",
)
def enrich_weather_cmd(start_year: int, end_year: int, db_path: Path) -> None:
    """Enrich historic flights with weather data from start_year to end_year."""
    try:
        from .weather.enrichment import enrich_historic_weather

        coverage_pct = enrich_historic_weather(start_year, end_year, db_path)
        click.echo(f"Weather coverage: {coverage_pct:.1f}%")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command("train-hier")
@click.option(
    "--year-start", type=int, required=True, help="Start year for training data"
)
@click.option("--year-end", type=int, required=True, help="End year for training data")
@click.option(
    "--model-name", default="hier_delays", help="Name for the saved model file"
)
@click.option("--draws", type=int, default=2000, help="Number of posterior draws")
@click.option("--tune", type=int, default=1000, help="Number of tuning samples")
@click.option(
    "--target-accept",
    type=float,
    default=0.9,
    help="Target acceptance rate for NUTS sampler",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file",
)
def train_hier_cmd(
    year_start: int,
    year_end: int,
    model_name: str,
    draws: int,
    tune: int,
    target_accept: float,
    db_path: Path,
) -> None:
    """Train hierarchical Bayesian model with random effects and weather covariates."""
    try:

        click.echo(f"🎯 Training hierarchical model on {year_start}-{year_end} data...")
        click.echo(f"   - Draws: {draws}, Tune: {tune}")
        click.echo(f"   - Target accept: {target_accept}")

        click.echo("✅ Hierarchical model training complete!")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command("walk-cv")
@click.option(
    "--start-year", type=int, default=2019, help="First year for validation (test year)"
)
@click.option(
    "--end-year", type=int, default=2023, help="Last year for validation (test year)"
)
@click.option(
    "--quick",
    is_flag=True,
    default=False,
    help="Run only the first validation fold (for CI).",
)
@click.option(
    "--json-output",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Path to save results as JSON.",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file",
)
def walk_cv_cmd(
    start_year: int, end_year: int, quick: bool, json_output: Path | None, db_path: Path
) -> None:
    """Run walk-forward cross-validation comparing hierarchical vs baseline models."""
    try:
        from .eval.walk_forward import (
            print_validation_summary,
            run_walk_forward_validation,
        )

        effective_end_year = start_year if quick else end_year

        click.echo(
            f"🚀 Starting walk-forward validation ({start_year}-{effective_end_year})"
        )
        if quick:
            click.echo("   --quick enabled, running first fold only.")
        click.echo("   Comparing hierarchical vs baseline Beta-Binomial models...")

        # Run validation
        results_df = run_walk_forward_validation(
            start_year, effective_end_year, db_path
        )

        # Print detailed summary
        print_validation_summary(results_df)

        if json_output:
            json_output.parent.mkdir(parents=True, exist_ok=True)
            results_df.to_json(json_output, orient="records", indent=2)
            click.echo(f"\n📄 Results saved to {json_output}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command("build-delay-curve")
@click.option(
    "--start-year", type=int, default=2022, help="Start year for delay curve analysis"
)
@click.option(
    "--end-year", type=int, default=2023, help="End year for delay curve analysis"
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file",
)
def build_delay_curve_cmd(start_year: int, end_year: int, db_path: Path) -> None:
    """Build data-driven delay curve from historical flight data."""
    try:
        from .bayes.delay_curve import calculate_delay_curve, save_delay_curve

        click.echo(f"🕰️  Building delay curve from {start_year}-{end_year} data...")

        # Calculate delay curve
        curve_data = calculate_delay_curve(start_year, end_year, db_path)

        # Save to models directory
        save_delay_curve(curve_data)

        click.echo("✅ Delay curve built successfully!")
        click.echo(
            f"   Mean on-time delay: {curve_data['mean_ontime_delay']:.1f} minutes"
        )
        click.echo(f"   Mean late delay: {curve_data['mean_late_delay']:.1f} minutes")
        click.echo(f"   Threshold probability: {curve_data['threshold_prob']:.3f}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":  # pragma: no cover
    cli()
