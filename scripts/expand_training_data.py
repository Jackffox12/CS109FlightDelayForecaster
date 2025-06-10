#!/usr/bin/env python3
"""Script to expand training data for more accurate predictions."""

import asyncio
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

# Realistic flight routes for major US carriers
REALISTIC_ROUTES = {
    "DL": [
        ("JFK", "ATH", "18:00"),  # International
        ("JFK", "LAX", "08:30"),  # Cross-country
        ("LAX", "JFK", "11:45"),  # Cross-country
        ("ATL", "LAX", "07:15"),  # Hub-to-hub
        ("ATL", "JFK", "14:30"),  # Hub-to-hub
        ("ATL", "LGA", "16:45"),  # Hub-to-NYC
        ("JFK", "LHR", "22:10"),  # International
        ("SEA", "ATL", "17:45"),  # Cross-country
        ("BOS", "ATL", "09:30"),  # East-to-hub
        ("ATL", "MIA", "13:20"),  # Hub-to-south
    ],
    "AA": [
        ("DFW", "LAX", "09:25"),  # Hub-to-west
        ("LAX", "JFK", "13:55"),  # Cross-country
        ("ORD", "LAX", "16:40"),  # Hub-to-west
        ("DFW", "LGA", "19:15"),  # Hub-to-NYC
        ("JFK", "LHR", "20:30"),  # International
        ("DFW", "JFK", "11:30"),  # Hub-to-east
        ("ORD", "JFK", "12:45"),  # Hub-to-east
        ("LAX", "DFW", "14:30"),  # West-to-hub
        ("MIA", "LAX", "08:45"),  # South-to-west
        ("DFW", "MIA", "15:30"),  # Hub-to-south
    ],
    "UA": [
        ("SFO", "JFK", "08:00"),  # Cross-country
        ("JFK", "SFO", "18:30"),  # Cross-country
        ("ORD", "SFO", "12:15"),  # Hub-to-west
        ("EWR", "LAX", "15:25"),  # NYC-to-west
        ("ORD", "LAX", "10:30"),  # Hub-to-west
        ("SFO", "ORD", "07:45"),  # West-to-hub
        ("ORD", "EWR", "13:20"),  # Hub-to-NYC
        ("LAX", "ORD", "16:15"),  # West-to-hub
        ("SFO", "EWR", "09:30"),  # Cross-country
        ("ORD", "JFK", "11:45"),  # Hub-to-NYC
    ],
    "SW": [
        ("MDW", "LAX", "06:30"),  # Chicago-to-west
        ("DAL", "LAX", "10:45"),  # Dallas-to-west
        ("BWI", "LAX", "17:20"),  # East-to-west
        ("LAX", "MDW", "12:30"),  # West-to-Chicago
        ("LAX", "DAL", "15:45"),  # West-to-Dallas
        ("DAL", "MDW", "08:15"),  # Dallas-to-Chicago
        ("BWI", "MDW", "14:20"),  # East-to-Chicago
        ("LAX", "BWI", "19:30"),  # West-to-east
        ("MDW", "BWI", "11:15"),  # Chicago-to-east
        ("DAL", "BWI", "16:45"),  # Dallas-to-east
    ],
    "B6": [
        ("JFK", "LAX", "08:00"),  # Cross-country
        ("BOS", "LAX", "14:30"),  # East-to-west
        ("JFK", "SFO", "11:15"),  # NYC-to-SF
        ("LAX", "JFK", "16:45"),  # West-to-NYC
        ("BOS", "SFO", "12:30"),  # Boston-to-SF
        ("JFK", "SEA", "13:45"),  # NYC-to-Seattle
        ("LAX", "BOS", "20:15"),  # West-to-Boston
        ("SFO", "JFK", "09:30"),  # SF-to-NYC
    ],
    "AS": [
        ("SEA", "LAX", "07:30"),  # Seattle-to-LA
        ("SEA", "SFO", "16:00"),  # Seattle-to-SF
        ("LAX", "SEA", "11:45"),  # LA-to-Seattle
        ("SFO", "SEA", "18:30"),  # SF-to-Seattle
        ("SEA", "PDX", "14:20"),  # Seattle-to-Portland
        ("PDX", "SEA", "12:15"),  # Portland-to-Seattle
        ("SEA", "ANC", "10:30"),  # Seattle-to-Anchorage
        ("ANC", "SEA", "15:45"),  # Anchorage-to-Seattle
    ],
}

# Historical delay rates by carrier (realistic based on DOT data)
CARRIER_DELAY_RATES = {
    "DL": 0.22,  # Delta - better performance
    "AA": 0.26,  # American - average
    "UA": 0.24,  # United - average
    "SW": 0.28,  # Southwest - worse
    "B6": 0.32,  # JetBlue - worse
    "AS": 0.18,  # Alaska - best
}

# Airport delay factors
AIRPORT_DELAY_FACTORS = {
    "LGA": 0.15,
    "EWR": 0.12,
    "JFK": 0.10,
    "ORD": 0.08,
    "ATL": 0.06,
    "DEN": 0.05,
    "SFO": 0.08,
    "LAX": 0.07,
    "MDW": 0.06,
    "BWI": 0.04,
    "DAL": 0.05,
    "BOS": 0.07,
    "MIA": 0.08,
    "SEA": 0.04,
    "PDX": 0.03,
    "ANC": 0.02,
}


def generate_realistic_flight_data(
    start_year: int, end_year: int, flights_per_route_per_year: int = 100
) -> pd.DataFrame:
    """Generate realistic flight data for training."""
    flights = []

    for year in range(start_year, end_year + 1):
        for carrier, routes in REALISTIC_ROUTES.items():
            for route_idx, (origin, dest, dep_time) in enumerate(routes):

                # Generate flights for this route throughout the year
                for flight_idx in range(flights_per_route_per_year):
                    # Random date in the year
                    start_date = date(year, 1, 1)
                    end_date = date(year, 12, 31)
                    random_days = random.randint(0, (end_date - start_date).days)
                    flight_date = start_date + timedelta(days=random_days)

                    # Skip weekends for some flights (more realistic)
                    if flight_date.weekday() >= 5 and random.random() < 0.3:
                        continue

                    # Calculate departure hour from time string
                    dep_hour = int(dep_time.split(":")[0])

                    # Calculate realistic delay probability
                    base_delay_rate = CARRIER_DELAY_RATES[carrier]

                    # Airport factors
                    origin_factor = AIRPORT_DELAY_FACTORS.get(origin, 0.0)
                    dest_factor = AIRPORT_DELAY_FACTORS.get(dest, 0.0) * 0.5

                    # Time of day factors
                    time_factor = 0.0
                    if 6 <= dep_hour <= 8:
                        time_factor = -0.05  # Early morning better
                    elif 14 <= dep_hour <= 18:
                        time_factor = 0.08  # Afternoon rush worse
                    elif dep_hour >= 19:
                        time_factor = 0.05  # Evening worse

                    # Seasonal factors
                    month = flight_date.month
                    if month in [12, 1, 2]:  # Winter
                        seasonal_factor = 0.08
                    elif month in [6, 7, 8]:  # Summer travel season
                        seasonal_factor = 0.05
                    else:
                        seasonal_factor = 0.0

                    # Final delay probability
                    delay_prob = (
                        base_delay_rate
                        + origin_factor
                        + dest_factor
                        + time_factor
                        + seasonal_factor
                    )
                    delay_prob = max(0.05, min(0.75, delay_prob))

                    # Generate late/on-time outcome
                    is_late = random.random() < delay_prob

                    # Generate delay minutes
                    if is_late:
                        # Exponential distribution for delays
                        delay_minutes = max(
                            15, random.expovariate(1 / 25)
                        )  # Average 25 min delay
                        delay_minutes = min(delay_minutes, 180)  # Cap at 3 hours
                    else:
                        # Small delays for on-time flights
                        delay_minutes = max(-10, random.normalvariate(2, 5))

                    flights.append(
                        {
                            "flight_date": flight_date,
                            "carrier": carrier,
                            "origin": origin,
                            "dest": dest,
                            "dep_hour": dep_hour,
                            "dep_delay_minutes": round(delay_minutes, 1),
                            "late": is_late,
                        }
                    )

    return pd.DataFrame(flights)


def create_expanded_database(db_path: Path = Path("data/flights_expanded.duckdb")):
    """Create expanded database with diverse training data."""
    print("🔄 Generating realistic flight data...")

    # Generate 3 years of diverse data
    df = generate_realistic_flight_data(2021, 2023, flights_per_route_per_year=150)

    print(f"📊 Generated {len(df):,} flights")
    print(f"   - Carriers: {df['carrier'].nunique()}")
    print(f"   - Origins: {df['origin'].nunique()}")
    print(f"   - Destinations: {df['dest'].nunique()}")
    print(f"   - Routes: {df.groupby(['carrier', 'origin', 'dest']).ngroups}")
    print(f"   - Overall delay rate: {df['late'].mean():.1%}")

    # Save to database
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db_path)) as conn:
        # Create table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS historic_flights (
                flight_date DATE,
                carrier VARCHAR,
                origin VARCHAR,
                dest VARCHAR,
                dep_hour INTEGER,
                dep_delay_minutes REAL,
                late BOOLEAN,
                year INTEGER GENERATED ALWAYS AS (extract(year FROM flight_date))
            )
        """
        )

        # Insert data
        conn.execute("DELETE FROM historic_flights")  # Clear existing
        conn.execute("INSERT INTO historic_flights SELECT * FROM df")

        print(f"✅ Saved to {db_path}")

        # Print summary by carrier
        print("\n📈 Delay rates by carrier:")
        carrier_stats = conn.execute(
            """
            SELECT carrier, 
                   count(*) as flights,
                   avg(case when late then 1.0 else 0.0 end) as delay_rate
            FROM historic_flights 
            GROUP BY carrier
            ORDER BY delay_rate
        """
        ).fetchall()

        for carrier, flights, delay_rate in carrier_stats:
            print(f"   {carrier}: {delay_rate:.1%} ({flights:,} flights)")


if __name__ == "__main__":
    create_expanded_database()
