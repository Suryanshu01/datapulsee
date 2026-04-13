"""
Generate realistic banking sample datasets for DataPulse demos.

Three datasets are produced, each targeting one of NatWest's "Talk to Data"
use cases and containing enough rows and variation to demonstrate all four
query modes (change, compare, breakdown, summary).

Datasets:
  sme_lending.csv      — SME lending portfolio (approvals, disbursements, defaults)
  customer_support.csv — Banking support metrics (tickets, resolution, satisfaction)
  digital_banking.csv  — Digital channel adoption (users, transactions, signups)

Run:  python scripts/generate_samples.py
Output goes to assets/samples/
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
import numpy as np

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "samples"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def jitter(base: float, pct: float = 0.15) -> float:
    """Add ±pct% random noise to *base*."""
    return base * (1 + random.uniform(-pct, pct))


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ── 1. SME Lending Portfolio ───────────────────────────────────────────────────

def generate_sme_lending() -> pd.DataFrame:
    """
    50+ rows of monthly SME lending data across 4 regions and 3 product types.

    Realistic features:
      - Approvals dip in August (summer slowdown)
      - South region consistently outperforms others
      - Invoice Finance has higher default rates than Term Loans
      - Feb 2024 shows an anomaly: elevated defaults due to a fictional rate rise
    """
    months = pd.date_range("2023-01", periods=18, freq="MS").strftime("%Y-%m").tolist()
    regions = ["North", "South", "East", "West"]
    products = ["Term Loan", "Overdraft", "Invoice Finance"]

    rows = []
    for month_idx, month in enumerate(months):
        for region in regions:
            for product in products:
                # Base volumes vary by region
                region_factor = {"North": 1.0, "South": 1.3, "East": 0.85, "West": 0.95}[region]
                product_factor = {"Term Loan": 1.2, "Overdraft": 0.9, "Invoice Finance": 0.7}[product]

                # Seasonal dip in Aug (month_idx 7)
                seasonal = 0.75 if month_idx % 12 == 7 else 1.0

                applications = int(jitter(80 * region_factor * product_factor * seasonal))
                approval_rate = clamp(jitter(0.72), 0.50, 0.92)
                approvals = int(applications * approval_rate)
                avg_loan = {"Term Loan": 85_000, "Overdraft": 25_000, "Invoice Finance": 45_000}[product]
                disbursed = round(approvals * jitter(avg_loan) / 1_000, 1)  # £k

                # Elevated defaults Feb 2024 (index 13)
                base_default = {"Term Loan": 0.018, "Overdraft": 0.032, "Invoice Finance": 0.045}[product]
                default_rate = round(clamp(jitter(base_default), 0.005, 0.12) * (1.8 if month_idx == 13 else 1.0), 4)

                avg_days = round(jitter({"Term Loan": 12, "Overdraft": 5, "Invoice Finance": 8}[product], 0.20))
                segment = random.choice(["New", "New", "Existing", "Existing", "Existing"])

                rows.append({
                    "month": month,
                    "region": region,
                    "product_type": product,
                    "applications": applications,
                    "approvals": approvals,
                    "disbursed_amount_gbp_k": disbursed,
                    "default_rate": default_rate,
                    "avg_processing_days": avg_days,
                    "customer_segment": segment,
                })

    return pd.DataFrame(rows)


# ── 2. Customer Support Metrics ────────────────────────────────────────────────

def generate_customer_support() -> pd.DataFrame:
    """
    60+ rows of weekly banking support metrics across 4 channels and 4 categories.

    Realistic features:
      - App channel grows week-over-week (digital shift)
      - Fraud category spikes in weeks 8 and 20 (fictional phishing campaigns)
      - Branch satisfaction consistently highest; Chat lowest
      - first_contact_resolution improves over time as teams adapt
    """
    weeks = pd.date_range("2024-01-01", periods=26, freq="W-MON").strftime("%Y-%m-%d").tolist()
    channels = ["Branch", "Phone", "App", "Chat"]
    categories = ["Account", "Cards", "Mortgage", "Fraud"]

    rows = []
    for week_idx, date in enumerate(weeks):
        for channel in channels:
            for category in categories:
                # App grows over time; Branch shrinks
                channel_trend = {
                    "Branch": max(0.6, 1.0 - week_idx * 0.015),
                    "Phone": 1.0,
                    "App": 1.0 + week_idx * 0.02,
                    "Chat": 1.0 + week_idx * 0.01,
                }[channel]

                # Fraud spikes
                fraud_spike = 2.5 if category == "Fraud" and week_idx in (8, 20) else 1.0

                base_tickets = {"Branch": 45, "Phone": 90, "App": 120, "Chat": 60}[channel]
                cat_factor = {"Account": 1.2, "Cards": 1.0, "Mortgage": 0.6, "Fraud": 0.4}[category]
                tickets = int(jitter(base_tickets * cat_factor * channel_trend * fraud_spike))
                resolved = int(tickets * clamp(jitter(0.91), 0.70, 0.99))

                base_hrs = {"Branch": 1.2, "Phone": 3.5, "App": 8.0, "Chat": 4.5}[channel]
                avg_resolution_hrs = round(clamp(jitter(base_hrs), 0.5, 48.0), 1)

                base_sat = {"Branch": 4.4, "Phone": 3.9, "App": 3.7, "Chat": 3.5}[channel]
                satisfaction_score = round(clamp(jitter(base_sat, 0.05), 1.0, 5.0), 2)

                escalation_rate = round(clamp(jitter(0.08 * fraud_spike), 0.01, 0.35), 3)
                fcr = round(clamp(jitter(0.75 + week_idx * 0.005), 0.40, 0.98), 3)

                rows.append({
                    "date": date,
                    "channel": channel,
                    "category": category,
                    "tickets": tickets,
                    "resolved": resolved,
                    "avg_resolution_hrs": avg_resolution_hrs,
                    "satisfaction_score": satisfaction_score,
                    "escalation_rate": escalation_rate,
                    "first_contact_resolution_pct": fcr,
                })

    return pd.DataFrame(rows)


# ── 3. Digital Banking Adoption ────────────────────────────────────────────────

def generate_digital_banking() -> pd.DataFrame:
    """
    90+ rows of daily digital channel metrics across Mobile App, Web, and ATM.

    Realistic features:
      - Mobile App active_users grow steadily (digital adoption trend)
      - ATM transaction_value drops over time (shift to digital payments)
      - app_crashes spike in week 6 (fictional bad release, then hotfix)
      - Weekends show higher investment feature usage
    """
    dates = pd.date_range("2024-01-01", periods=90, freq="D").strftime("%Y-%m-%d").tolist()
    platforms = ["Mobile App", "Web", "ATM"]
    features = ["Transfer", "Payment", "Investment", "Support"]

    rows = []
    for day_idx, date in enumerate(dates):
        is_weekend = (day_idx % 7) in (5, 6)
        bad_release_week = 35 <= day_idx <= 41  # crash spike

        for platform in platforms:
            for feature in features:
                # Platform growth trends
                platform_trend = {
                    "Mobile App": 1.0 + day_idx * 0.008,
                    "Web": 1.0 + day_idx * 0.002,
                    "ATM": max(0.5, 1.0 - day_idx * 0.004),
                }[platform]

                # Feature usage varies by platform and day type
                feat_factor = {
                    "Transfer": 1.0,
                    "Payment": 1.2,
                    "Investment": 1.5 if is_weekend else 0.8,
                    "Support": 0.6,
                }[feature]

                base_users = {"Mobile App": 8_000, "Web": 3_500, "ATM": 1_200}[platform]
                active_users = int(jitter(base_users * platform_trend * feat_factor, 0.10))

                base_txns = {"Mobile App": 12_000, "Web": 5_000, "ATM": 2_500}[platform]
                transactions = int(jitter(base_txns * platform_trend * feat_factor, 0.12))

                avg_val = {"Mobile App": 220, "Web": 350, "ATM": 180}[platform]
                transaction_value = round(jitter(avg_val * transactions / 1_000, 0.08))  # £k

                signups = int(jitter(80 * platform_trend, 0.20)) if platform != "ATM" else 0

                base_churn = {"Mobile App": 0.015, "Web": 0.022, "ATM": 0.005}[platform]
                churn_rate = round(clamp(jitter(base_churn), 0.001, 0.08), 4)

                # Crash spike for Mobile App during bad release week
                if platform == "Mobile App" and bad_release_week:
                    app_crashes = int(jitter(320, 0.30))
                else:
                    app_crashes = int(jitter(12, 0.40)) if platform == "Mobile App" else 0

                avg_session = round(clamp(jitter(
                    {"Mobile App": 8.5, "Web": 5.2, "ATM": 1.5}[platform]
                ), 0.5, 30.0), 1)

                rows.append({
                    "date": date,
                    "platform": platform,
                    "active_users": active_users,
                    "transactions": transactions,
                    "transaction_value_gbp_k": transaction_value,
                    "signups": signups,
                    "churn_rate": churn_rate,
                    "app_crashes": app_crashes,
                    "avg_session_minutes": avg_session,
                    "feature_used": feature,
                })

    return pd.DataFrame(rows)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    datasets = [
        ("sme_lending.csv", generate_sme_lending),
        ("customer_support.csv", generate_customer_support),
        ("digital_banking.csv", generate_digital_banking),
    ]

    for filename, generator in datasets:
        df = generator()
        path = OUTPUT_DIR / filename
        df.to_csv(path, index=False)
        print(f"Generated {path} — {len(df):,} rows, {len(df.columns)} columns")

    print(f"\nAll sample datasets written to {OUTPUT_DIR}")
