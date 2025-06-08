"""flight_delay_bayes CLI module."""
import click
from pathlib import Path
from datetime import datetime
import asyncio

from .ingestion.bts_ingest import ingest_historic_data
from .bayes.prior_estimator import compute_beta_prior
from flight_delay_bayes.bayes.pipeline import forecast_probability
from flight_delay_bayes.eval.backtest import run_backtest


@click.group()
def cli() -> None:
    """Flight Delay Bayesian Forecaster CLI stub."""


@cli.command("ingest-historic")
@click.option(
    "--csv-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Directory containing CSV files to ingest"
)
@click.option(
    "--db-path", 
    type=click.Path(path_type=Path),
    default=Path("data/flights.duckdb"),
    help="Path to DuckDB database file"
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
def estimate_prior(carrier: str, origin: str, dest: str, db_path: Path) -> None:  # noqa: D401
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


if __name__ == "__main__":  # pragma: no cover
    cli() 