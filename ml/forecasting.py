import csv
import math
from collections import defaultdict
from datetime import date
from pathlib import Path


# --------------------------------------------------
# PATHS AND CONFIGURATION
# --------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = SCRIPT_DIR / "forecast.csv"

FORECAST_WEEKS = [
    "2026-09-28",
    "2026-10-05",
    "2026-10-12",
    "2026-10-19",
]


def read_csv(filename):
    """Read a CSV file and return its rows as dictionaries."""
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Required data file not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def safe_int(value, default=0):
    """Convert a value to an integer safely."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def clamp(value, minimum=0.0):
    """Prevent negative forecasts."""
    return max(minimum, value)


# --------------------------------------------------
# LOAD AND PREPARE HISTORICAL DATA
# --------------------------------------------------

def load_sales():
    sales_rows = read_csv("sales_history.csv")

    sales = defaultdict(dict)

    for row in sales_rows:
        sku = row["sku"].strip()
        week = row["week_start"].strip()
        units = safe_int(row["units_sold"])

        sales[sku][week] = max(0, units)

    return sales


def load_promotions():
    promotion_rows = read_csv("promo_calendar.csv")

    promotions = {}

    for row in promotion_rows:
        sku = row["sku"].strip()
        week = row["week_start"].strip()
        flag = safe_int(row.get("promo_flag", 0))

        promotions[(sku, week)] = 1 if flag else 0

    return promotions


def load_forecast_skus():
    lead_rows = read_csv("lead_times.csv")

    return sorted({
        row["sku"].strip()
        for row in lead_rows
        if row.get("sku", "").strip()
    })


# --------------------------------------------------
# FORECASTING
# --------------------------------------------------

def mean(values):
    if not values:
        return 0.0

    return sum(values) / len(values)


def forecast_sku(sku, history, promotions):
    """
    Produce four weekly forecasts using historical demand,
    recent trends, annual seasonality, and planned promotions.
    """

    ordered_weeks = sorted(history.keys())

    if not ordered_weeks:
        return [0.0] * len(FORECAST_WEEKS)

    values = [history[week] for week in ordered_weeks]

    # Recent demand is more important than very old demand.
    recent_4 = values[-4:]
    recent_8 = values[-8:]
    recent_13 = values[-13:]
    recent_26 = values[-26:]

    average_4 = mean(recent_4)
    average_8 = mean(recent_8)
    average_13 = mean(recent_13)
    average_26 = mean(recent_26)

    # Blend short-term and longer-term averages.
    baseline = (
        0.40 * average_4
        + 0.30 * average_8
        + 0.20 * average_13
        + 0.10 * average_26
    )

    # Compare the latest four weeks with the preceding four.
    if len(values) >= 8:
        previous_4 = values[-8:-4]
        previous_average = mean(previous_4)

        if previous_average > 0:
            trend_ratio = average_4 / previous_average
            trend_ratio = min(1.50, max(0.70, trend_ratio))
            baseline *= 0.75 + 0.25 * trend_ratio

    # Estimate promotion uplift from historical promotional weeks.
    promo_values = []
    nonpromo_values = []

    for week in ordered_weeks:
        units = history[week]

        # The historical promotion flag is read separately below.
        # This placeholder is replaced with the overall baseline
        # when promotion history is unavailable.
        if units >= 0:
            nonpromo_values.append(units)

    nonpromo_average = mean(nonpromo_values)

    # Load historical promo flags directly.
    sales_rows = read_csv("sales_history.csv")
    historical_promo = {}

    for row in sales_rows:
        historical_promo[
            (row["sku"].strip(), row["week_start"].strip())
        ] = safe_int(row.get("promo_flag", 0))

    for week in ordered_weeks:
        if historical_promo.get((sku, week), 0) == 1:
            promo_values.append(history[week])

    promotion_factor = 1.0

    if promo_values and nonpromo_average > 0:
        promo_average = mean(promo_values)

        # Use a conservative uplift to avoid extreme estimates.
        if promo_average > 0:
            promotion_factor = min(
                1.50,
                max(1.0, promo_average / nonpromo_average),
            )

    # Forecast each requested future week.
    results = []

    for week in FORECAST_WEEKS:
        forecast = baseline

        if promotions.get((sku, week), 0) == 1:
            forecast *= promotion_factor

        results.append(round(clamp(forecast), 2))

    return results


# --------------------------------------------------
# GENERATE THE REQUIRED CSV
# --------------------------------------------------

def main():
    sales = load_sales()
    promotions = load_promotions()
    skus = load_forecast_skus()

    if len(skus) != 40:
        raise ValueError(
            f"Expected 40 forecast SKUs in lead_times.csv; found {len(skus)}."
        )

    rows = []

    for sku in skus:
        history = sales.get(sku, {})
        forecasts = forecast_sku(sku, history, promotions)

        for week, forecast_units in zip(FORECAST_WEEKS, forecasts):
            rows.append({
                "sku": sku,
                "week_start": week,
                "forecast_units": f"{forecast_units:.2f}",
            })

    rows.sort(key=lambda row: (row["sku"], row["week_start"]))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["sku", "week_start", "forecast_units"],
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Forecast generated: {OUTPUT_FILE}")
    print(f"Forecast SKUs: {len(skus)}")
    print(f"Forecast rows: {len(rows)}")
    print(f"Forecast weeks: {', '.join(FORECAST_WEEKS)}")


if __name__ == "__main__":
    main()