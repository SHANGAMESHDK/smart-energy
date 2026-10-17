from datetime import date
from bills import load_bills


def predict_consumption(
    current_units: float,
    days_elapsed: int,
    cycle_days: int = 60,
):
    if current_units < 0:
        raise ValueError("Units cannot be negative")

    if not 1 <= days_elapsed <= cycle_days:
        raise ValueError("Invalid number of elapsed days")

    # Current average daily consumption
    daily_usage = current_units / days_elapsed

    # Historical average daily consumption
    bills = load_bills()

    bills["days"] = (
        bills["billing_end"] - bills["billing_start"]
    ).dt.days + 1

    historical_daily_usage = (
        bills["units"] / bills["days"]
    ).mean()

    # Blend current usage with historical usage.
    # Current usage gets more weight.
    estimated_daily_usage = (
        0.7 * daily_usage
        + 0.3 * historical_daily_usage
    )

    remaining_days = cycle_days - days_elapsed

    predicted_units = (
        current_units
        + estimated_daily_usage * remaining_days
    )

    return {
        "current_units": round(current_units, 2),
        "current_daily_average": round(daily_usage, 2),
        "historical_daily_average": round(
            historical_daily_usage, 2
        ),
        "predicted_daily_average": round(
            estimated_daily_usage, 2
        ),
        "predicted_final_units": round(predicted_units, 2),
        "slab_risk": (
            "HIGH" if predicted_units > 500
            else "NEAR LIMIT" if predicted_units >= 475
            else "LOW"
        ),
    }


if __name__ == "__main__":
    # Example: 420 units after 35 days of a 60-day cycle
    result = predict_consumption(
        current_units=420,
        days_elapsed=35,
        cycle_days=60,
    )

    print("\nSMART ENERGY METER — PREDICTION")
    print("-" * 40)

    for key, value in result.items():
        print(f"{key}: {value}")
