#!/usr/bin/env python3
"""Build a comprehensive local airport database from reliable sources."""

import csv
import json
from pathlib import Path

import requests


def download_openflights_data():
    """Download airport data from OpenFlights GitHub repository."""
    print("📥 Downloading OpenFlights airport data...")

    url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.text


def parse_openflights_csv(csv_text: str) -> dict:
    """Parse OpenFlights CSV data into a dictionary."""
    airports = {}

    # Parse CSV without header
    reader = csv.reader(csv_text.strip().split("\n"))

    for row in reader:
        if len(row) >= 8:
            try:
                # OpenFlights format: ID,Name,City,Country,IATA,ICAO,Latitude,Longitude,Altitude,Timezone,DST,Tz,Type,Source
                airport_id = row[0]
                name = row[1].strip('"')
                city = row[2].strip('"')
                country = row[3].strip('"')
                iata = row[4].strip('"')
                icao = row[5].strip('"')
                lat = float(row[6]) if row[6] else None
                lng = float(row[7]) if row[7] else None

                # Only include airports with valid IATA codes and coordinates
                if iata and len(iata) == 3 and lat is not None and lng is not None:
                    airports[iata] = {
                        "iata": iata,
                        "icao": icao if icao else None,
                        "name": name,
                        "city": city,
                        "country": country,
                        "lat": lat,
                        "lng": lng,
                    }

            except (ValueError, IndexError) as e:
                print(f"⚠️  Skipping invalid row: {e}")
                continue

    return airports


def add_major_us_airports(airports: dict) -> dict:
    """Add/update major US airports with verified coordinates."""

    # Major US airports with verified coordinates
    major_airports = {
        "ATL": {
            "name": "Hartsfield-Jackson Atlanta International Airport",
            "city": "Atlanta",
            "country": "United States",
            "lat": 33.6367,
            "lng": -84.4281,
        },
        "LAX": {
            "name": "Los Angeles International Airport",
            "city": "Los Angeles",
            "country": "United States",
            "lat": 33.9425,
            "lng": -118.4081,
        },
        "ORD": {
            "name": "Chicago O'Hare International Airport",
            "city": "Chicago",
            "country": "United States",
            "lat": 41.9786,
            "lng": -87.9048,
        },
        "DFW": {
            "name": "Dallas/Fort Worth International Airport",
            "city": "Dallas",
            "country": "United States",
            "lat": 32.8968,
            "lng": -97.0380,
        },
        "DEN": {
            "name": "Denver International Airport",
            "city": "Denver",
            "country": "United States",
            "lat": 39.8561,
            "lng": -104.6737,
        },
        "JFK": {
            "name": "John F. Kennedy International Airport",
            "city": "New York",
            "country": "United States",
            "lat": 40.6413,
            "lng": -73.7781,
        },
        "SFO": {
            "name": "San Francisco International Airport",
            "city": "San Francisco",
            "country": "United States",
            "lat": 37.6213,
            "lng": -122.3790,
        },
        "LAS": {
            "name": "Harry Reid International Airport",
            "city": "Las Vegas",
            "country": "United States",
            "lat": 36.0840,
            "lng": -115.1537,
        },
        "SEA": {
            "name": "Seattle-Tacoma International Airport",
            "city": "Seattle",
            "country": "United States",
            "lat": 47.4502,
            "lng": -122.3088,
        },
        "CLT": {
            "name": "Charlotte Douglas International Airport",
            "city": "Charlotte",
            "country": "United States",
            "lat": 35.2144,
            "lng": -80.9473,
        },
        "MIA": {
            "name": "Miami International Airport",
            "city": "Miami",
            "country": "United States",
            "lat": 25.7959,
            "lng": -80.2870,
        },
        "PHX": {
            "name": "Phoenix Sky Harbor International Airport",
            "city": "Phoenix",
            "country": "United States",
            "lat": 33.4343,
            "lng": -112.0112,
        },
        "IAH": {
            "name": "George Bush Intercontinental Airport",
            "city": "Houston",
            "country": "United States",
            "lat": 29.9902,
            "lng": -95.3368,
        },
        "MCO": {
            "name": "Orlando International Airport",
            "city": "Orlando",
            "country": "United States",
            "lat": 28.4312,
            "lng": -81.3081,
        },
        "EWR": {
            "name": "Newark Liberty International Airport",
            "city": "Newark",
            "country": "United States",
            "lat": 40.6895,
            "lng": -74.1745,
        },
        "LGA": {
            "name": "LaGuardia Airport",
            "city": "New York",
            "country": "United States",
            "lat": 40.7769,
            "lng": -73.8740,
        },
        "BOS": {
            "name": "Logan International Airport",
            "city": "Boston",
            "country": "United States",
            "lat": 42.3656,
            "lng": -71.0096,
        },
        "MSP": {
            "name": "Minneapolis-Saint Paul International Airport",
            "city": "Minneapolis",
            "country": "United States",
            "lat": 44.8848,
            "lng": -93.2223,
        },
        "DTW": {
            "name": "Detroit Metropolitan Wayne County Airport",
            "city": "Detroit",
            "country": "United States",
            "lat": 42.2162,
            "lng": -83.3554,
        },
        "PHL": {
            "name": "Philadelphia International Airport",
            "city": "Philadelphia",
            "country": "United States",
            "lat": 39.8744,
            "lng": -75.2424,
        },
        "RSW": {
            "name": "Southwest Florida International Airport",
            "city": "Fort Myers",
            "country": "United States",
            "lat": 26.5362,
            "lng": -81.7552,
        },
        "FLL": {
            "name": "Fort Lauderdale-Hollywood International Airport",
            "city": "Fort Lauderdale",
            "country": "United States",
            "lat": 26.0742,
            "lng": -80.1506,
        },
        "BWI": {
            "name": "Baltimore/Washington International Thurgood Marshall Airport",
            "city": "Baltimore",
            "country": "United States",
            "lat": 39.1754,
            "lng": -76.6683,
        },
        "DCA": {
            "name": "Ronald Reagan Washington National Airport",
            "city": "Washington",
            "country": "United States",
            "lat": 38.8512,
            "lng": -77.0402,
        },
        "IAD": {
            "name": "Washington Dulles International Airport",
            "city": "Washington",
            "country": "United States",
            "lat": 38.9531,
            "lng": -77.4565,
        },
        "MDW": {
            "name": "Chicago Midway International Airport",
            "city": "Chicago",
            "country": "United States",
            "lat": 41.7868,
            "lng": -87.7522,
        },
        "TPA": {
            "name": "Tampa International Airport",
            "city": "Tampa",
            "country": "United States",
            "lat": 27.9755,
            "lng": -82.5332,
        },
        "SAN": {
            "name": "San Diego International Airport",
            "city": "San Diego",
            "country": "United States",
            "lat": 32.7338,
            "lng": -117.1933,
        },
        "PDX": {
            "name": "Portland International Airport",
            "city": "Portland",
            "country": "United States",
            "lat": 45.5898,
            "lng": -122.5951,
        },
        "SLC": {
            "name": "Salt Lake City International Airport",
            "city": "Salt Lake City",
            "country": "United States",
            "lat": 40.7899,
            "lng": -111.9791,
        },
    }

    # Add/update major airports
    for iata, info in major_airports.items():
        if iata in airports:
            # Update existing entry with verified coordinates
            airports[iata].update(info)
        else:
            # Add new entry
            airports[iata] = {"iata": iata, "icao": None, **info}

    return airports


def build_airport_database():
    """Build comprehensive airport database."""
    print("🏗️  Building comprehensive airport database...")

    # Download OpenFlights data
    csv_text = download_openflights_data()

    # Parse the data
    print("📊 Parsing airport data...")
    airports = parse_openflights_csv(csv_text)
    print(f"   Found {len(airports):,} airports with IATA codes")

    # Add/verify major US airports
    print("🇺🇸 Adding verified major US airports...")
    airports = add_major_us_airports(airports)

    # Create output directories
    webapp_dir = Path("webapp/src/data")
    webapp_dir.mkdir(parents=True, exist_ok=True)

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    # Save as JSON for frontend
    airport_json_path = webapp_dir / "airports.json"
    with open(airport_json_path, "w") as f:
        json.dump(airports, f, indent=2)

    print(f"💾 Saved {len(airports):,} airports to {airport_json_path}")

    # Create TypeScript interface for frontend
    ts_path = webapp_dir / "airports.ts"
    with open(ts_path, "w") as f:
        f.write(
            """// Auto-generated airport database
// Run 'python scripts/build_airport_database.py' to update

export interface Airport {
  iata: string;
  icao?: string;
  name: string;
  city: string;
  country: string;
  lat: number;
  lng: number;
}

export const AIRPORTS: Record<string, Airport> = 
"""
        )
        json.dump(airports, f, indent=2)
        f.write(
            """

export function getAirportByIATA(iata: string): Airport | null {
  return AIRPORTS[iata.toUpperCase()] || null;
}

export function searchAirports(query: string): Airport[] {
  const normalizedQuery = query.toLowerCase();
  return Object.values(AIRPORTS).filter(airport => 
    airport.iata.toLowerCase().includes(normalizedQuery) ||
    airport.name.toLowerCase().includes(normalizedQuery) ||
    airport.city.toLowerCase().includes(normalizedQuery)
  );
}
"""
        )

    print(f"📝 Created TypeScript interface at {ts_path}")

    # Save summary statistics
    stats = {
        "total_airports": len(airports),
        "countries": len(set(airport["country"] for airport in airports.values())),
        "us_airports": len(
            [a for a in airports.values() if a["country"] == "United States"]
        ),
        "major_hubs": len(
            [
                a
                for a in airports.values()
                if a["iata"]
                in [
                    "ATL",
                    "LAX",
                    "ORD",
                    "DFW",
                    "DEN",
                    "JFK",
                    "SFO",
                    "LAS",
                    "SEA",
                    "CLT",
                ]
            ]
        ),
    }

    print("\n📈 Database Statistics:")
    print(f"   Total airports: {stats['total_airports']:,}")
    print(f"   Countries: {stats['countries']:,}")
    print(f"   US airports: {stats['us_airports']:,}")
    print(f"   Major hubs: {stats['major_hubs']}")

    print("\n✅ Airport database build complete!")
    print("🔧 Next: Update your frontend to use the local database")


if __name__ == "__main__":
    build_airport_database()
