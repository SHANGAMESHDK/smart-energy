import csv
from pathlib import Path
from datetime import date

import pandas as pd

BILL_FILE = Path.home() / "smart-energy" / "data" / "bills.csv"


def load_bills():
    if not BILL_FILE.exists():
        raise FileNotFoundError(f"Bill file not found: {BILL_FILE}")

    df = pd.read_csv(BILL_FILE)

    required = {"billing_start", "billing_end", "units"}

    if not required.issubset(df.columns):
        raise ValueError(f"CSV must contain: {required}")

    df["billing_start"] = pd.to_datetime(
        df["billing_start"], errors="raise"
    )
    df["billing_end"] = pd.to_datetime(
        df["billing_end"], errors="raise"
    )
    df["units"] = pd.to_numeric(df["units"], errors="raise")

    if (df["units"] < 0).any():
        raise ValueError("Units cannot be negative")

    if (df["billing_end"] < df["billing_start"]).any():
        raise ValueError("Billing end cannot precede billing start")

    df = df.sort_values("billing_start").reset_index(drop=True)

    return df


if __name__ == "__main__":
    bills = load_bills()

    print("\nHISTORICAL EB BILLS")
    print(bills.to_string(index=False))

    print("\nTotal records:", len(bills))
    print("Average units per billing cycle:", round(bills["units"].mean(), 2))
    print("Maximum units:", bills["units"].max())
    print("Cycles exceeding 500 units:", int((bills["units"] > 500).sum()))
