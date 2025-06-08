"""
Cron job to validate live model performance against a Brier score threshold.

This script reads the `live_perf.parquet` file, calculates the Brier score
for the last 7 days, and sends a Slack alert if performance degrades.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

# --- Configuration ---
DATA_DIR = Path(__file__).parent.parent / "data"
PERF_FILE = DATA_DIR / "live_perf.parquet"
BRIER_THRESHOLD = 0.18
LOOKBACK_DAYS = 7
MIN_OBSERVATIONS = 20  # Minimum flights needed to trigger an alert


def get_performance_data() -> pd.DataFrame:
    """Load performance data, returning an empty frame if not found."""
    if not PERF_FILE.exists():
        print(f"Performance file not found at {PERF_FILE}. Exiting gracefully.")
        sys.exit(0)

    try:
        df = pd.read_parquet(PERF_FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as e:
        print(f"Error reading performance file: {e}", file=sys.stderr)
        sys.exit(1)


def send_slack_alert(message: str):
    """Send an alert to a Slack webhook if configured."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("\n--- SLACK ALERT ---")
        print(message)
        print("--- END SLACK ALERT ---")
        print("(Set SLACK_WEBHOOK_URL environment variable to send real alerts)")
        return

    try:
        response = requests.post(webhook_url, json={"text": message}, timeout=10)
        response.raise_for_status()
        print("Slack alert sent successfully.")
    except requests.RequestException as e:
        print(f"Failed to send Slack alert: {e}", file=sys.stderr)


def main():
    """Main validation logic."""
    print("📈 Validating live model performance...")
    df = get_performance_data()

    # Filter for recent data
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    recent_df = df[df["timestamp"] >= cutoff_date].copy()

    print(f"Found {len(recent_df)} observations in the last {LOOKBACK_DAYS} days.")

    if len(recent_df) < MIN_OBSERVATIONS:
        print(
            f"Not enough recent data to validate (minimum is {MIN_OBSERVATIONS}). Skipping."
        )
        sys.exit(0)

    # Calculate Brier score
    recent_df["y_true_int"] = recent_df["y_true"].astype(int)
    brier_score = ((recent_df["p_pred"] - recent_df["y_true_int"]) ** 2).mean()

    print(f"7-day rolling Brier score: {brier_score:.4f}")

    if brier_score > BRIER_THRESHOLD:
        message = (
            f"🚨 *Model Performance Alert* 🚨\n\n"
            f"The 7-day rolling Brier score is `{brier_score:.4f}`, "
            f"which has exceeded the threshold of `{BRIER_THRESHOLD}`.\n\n"
            f"This indicates a potential regression in live model performance."
        )
        send_slack_alert(message)
        print("\n❌ REGRESSION DETECTED: Brier score is above threshold.")
        sys.exit(1)
    else:
        print("✅ Performance is within acceptable limits.")
        sys.exit(0)


if __name__ == "__main__":
    main()
