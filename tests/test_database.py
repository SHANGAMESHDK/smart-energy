import sys
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database


def test_database_connection_and_tables():
    conn = database.get_connection()
    tables = [row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    conn.close()
    assert "readings" in tables
    assert "predictions" in tables


def test_database_save_and_retrieve_reading():
    initial_readings = database.get_recent_readings(limit=10)
    initial_count = len(initial_readings)

    # Save a test reading
    test_kwh = 9999.88
    database.save_reading(test_kwh, source="test_suite")

    updated_readings = database.get_recent_readings(limit=10)
    assert len(updated_readings) >= initial_count

    # The most recent reading should match test_kwh
    latest = updated_readings[-1]
    assert latest["cumulative_kwh"] == test_kwh
    assert latest["source"] == "test_suite"


def test_database_save_prediction():
    test_result = {
        "current_units": 350.0,
        "predicted_final_units": 485.5,
        "predicted_energy_charge": 1478.65,
        "slab_risk": "NEAR LIMIT",
    }
    database.save_prediction(test_result)

    conn = database.get_connection()
    row = conn.execute("SELECT * FROM predictions ORDER BY id DESC LIMIT 1;").fetchone()
    conn.close()

    assert row is not None
    assert row["current_units"] == 350.0
    assert row["predicted_units"] == 485.5
    assert row["slab_risk"] == "NEAR LIMIT"
