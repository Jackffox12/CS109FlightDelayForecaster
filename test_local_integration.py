#!/usr/bin/env python3
"""Test script to verify local integration of fast model with pipeline."""

import asyncio
from datetime import date
from pathlib import Path


async def test_local_integration():
    """Test the complete pipeline with real data and fast model."""
    print("🧪 Testing Local Integration")
    print("=" * 50)

    # Check if required files exist
    real_db = Path("data/flights_real.duckdb")
    fast_model = Path("models/fast_delay_model_logistic.pkl")

    print(f"📊 Real data DB: {'✅' if real_db.exists() else '❌'} {real_db}")
    print(f"🚀 Fast model: {'✅' if fast_model.exists() else '❌'} {fast_model}")

    if not real_db.exists():
        print("\n❌ Real data not found. Run:")
        print("   python scripts/ingest_kaggle_data.py")
        return

    if not fast_model.exists():
        print("\n❌ Fast model not found. Run:")
        print("   python scripts/train_fast_model.py")
        return

    # Test the pipeline
    try:
        from flight_delay_bayes.bayes.pipeline import forecast_probability

        print("\n🔮 Testing forecast pipeline...")

        # Test with a few different flights (use past dates)
        test_flights = [
            ("DL", "202", date(2024, 11, 15)),  # Past date with data
            ("AA", "1059", date(2024, 11, 15)),  # Past date with data
            ("SW", "1", date(2024, 11, 15)),  # Past date with data
        ]

        for carrier, flight_num, dep_date in test_flights:
            print(f"\n📋 Testing {carrier}{flight_num} on {dep_date}...")

            try:
                result = await forecast_probability(carrier, flight_num, dep_date)

                print(f"   🎯 Delay probability: {result['p_late']:.1%}")
                print(
                    f"   🧠 Hierarchical used: {result.get('hierarchical_used', False)}"
                )
                print(f"   🚀 Fast model used: {result.get('fast_model_used', False)}")
                print(f"   ⏱️  Update time: {result.get('update_time_ms', 0):.1f}ms")

            except Exception as e:
                print(f"   ⚠️  Failed: {e}")

    except Exception as e:
        print(f"\n❌ Pipeline test failed: {e}")
        return

    print("\n✅ Local integration test complete!")


if __name__ == "__main__":
    asyncio.run(test_local_integration())
