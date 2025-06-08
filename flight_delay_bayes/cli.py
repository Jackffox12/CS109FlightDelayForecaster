"""flight_delay_bayes CLI module."""
import click
from pathlib import Path

from .ingestion.bts_ingest import ingest_historic_data
from .bayes.prior_estimator import compute_beta_prior


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


if __name__ == "__main__":  # pragma: no cover
    cli() 