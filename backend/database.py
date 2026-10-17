import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "energy.db"


_initialized = False

def get_connection():
    global _initialized
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    if not _initialized:
        _initialized = True
        initialize_database()
    return connection


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cumulative_kwh REAL NOT NULL,
                power_watts REAL,
                voltage REAL,
                current_amps REAL,
                interval_kwh REAL DEFAULT 0.0,
                source TEXT NOT NULL DEFAULT 'manual',
                is_simulated INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Non-destructive schema migration for pre-existing readings tables
        existing_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(readings)").fetchall()
        }
        columns_to_add = [
            ("power_watts", "REAL"),
            ("voltage", "REAL"),
            ("current_amps", "REAL"),
            ("interval_kwh", "REAL DEFAULT 0.0"),
            ("is_simulated", "INTEGER NOT NULL DEFAULT 0"),
        ]
        for col_name, col_type in columns_to_add:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE readings ADD COLUMN {col_name} {col_type}")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                current_units REAL NOT NULL,
                predicted_units REAL NOT NULL,
                predicted_charge REAL NOT NULL,
                slab_risk TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cycle_baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                baseline_kwh REAL NOT NULL,
                cycle_days INTEGER NOT NULL DEFAULT 60,
                notes TEXT,
                created_at TEXT NOT NULL
            )
        """)


def save_reading(
    cumulative_kwh: float,
    power_watts: float = None,
    voltage: float = None,
    current_amps: float = None,
    source: str = "manual",
    is_simulated: bool = False,
    timestamp: str = None,
):
    if cumulative_kwh < 0:
        raise ValueError("Cumulative kWh cannot be negative")

    reading_time = timestamp or datetime.now().astimezone().isoformat()

    with get_connection() as conn:
        # Fetch the most recent reading to derive interval consumption and detect resets
        prev = conn.execute(
            """
            SELECT cumulative_kwh, timestamp
            FROM readings
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()

        if prev is not None:
            prev_kwh = float(prev["cumulative_kwh"])
            if cumulative_kwh >= prev_kwh:
                interval_kwh = round(cumulative_kwh - prev_kwh, 4)
            else:
                # Meter rollover or hardware reset detected: prevent negative intervals
                interval_kwh = round(cumulative_kwh, 4)
        else:
            interval_kwh = 0.0

        cursor = conn.execute(
            """
            INSERT INTO readings
                (timestamp, cumulative_kwh, power_watts, voltage,
                 current_amps, interval_kwh, source, is_simulated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reading_time,
                round(float(cumulative_kwh), 4),
                round(float(power_watts), 2) if power_watts is not None else None,
                round(float(voltage), 2) if voltage is not None else None,
                round(float(current_amps), 3) if current_amps is not None else None,
                interval_kwh,
                source,
                1 if is_simulated else 0,
            ),
        )
        new_id = cursor.lastrowid

    return {
        "id": new_id,
        "timestamp": reading_time,
        "cumulative_kwh": round(float(cumulative_kwh), 4),
        "power_watts": power_watts,
        "voltage": voltage,
        "current_amps": current_amps,
        "interval_kwh": interval_kwh,
        "source": source,
        "is_simulated": bool(is_simulated),
    }


def save_prediction(result):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO predictions
                (timestamp, current_units, predicted_units,
                 predicted_charge, slab_risk)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now().astimezone().isoformat(),
                result["current_units"],
                result["predicted_final_units"],
                result["predicted_energy_charge"],
                result["slab_risk"],
            ),
        )


def get_recent_readings(limit=100):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, cumulative_kwh, power_watts,
                   voltage, current_amps, interval_kwh, source,
                   is_simulated
            FROM readings
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()

    readings = []
    for row in reversed(rows):
        d = dict(row)
        d["is_simulated"] = bool(d.get("is_simulated", 0))
        readings.append(d)
    return readings


def get_recent_predictions(limit=10):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, current_units, predicted_units,
                   predicted_charge, slab_risk
            FROM predictions
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def set_cycle_baseline(baseline_kwh: float, start_date: str = None, cycle_days: int = 60, notes: str = None):
    now = datetime.now().astimezone().isoformat()
    start = start_date or now
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cycle_baselines
                (start_date, baseline_kwh, cycle_days, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (start, float(baseline_kwh), cycle_days, notes, now),
        )


def get_latest_baseline():
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM cycle_baselines
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def get_cycle_consumption():
    """Derive current billing-cycle consumption from the active baseline."""
    with get_connection() as conn:
        latest_reading = conn.execute(
            """
            SELECT cumulative_kwh, timestamp, power_watts, source, is_simulated
            FROM readings
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()

        if not latest_reading:
            return {
                "current_units": 0.0,
                "baseline_kwh": 0.0,
                "latest_cumulative_kwh": 0.0,
                "baseline_defined": False,
                "latest_reading": None,
            }

        baseline = get_latest_baseline()
        latest_kwh = float(latest_reading["cumulative_kwh"])

        if baseline:
            base_kwh = float(baseline["baseline_kwh"])
            units = max(0.0, round(latest_kwh - base_kwh, 2))
            baseline_defined = True
        else:
            # If no baseline has been explicitly configured, use earliest reading in database
            earliest = conn.execute(
                "SELECT cumulative_kwh FROM readings ORDER BY id ASC LIMIT 1"
            ).fetchone()
            base_kwh = float(earliest["cumulative_kwh"]) if earliest else latest_kwh
            units = max(0.0, round(latest_kwh - base_kwh, 2))
            baseline_defined = False

    return {
        "current_units": units,
        "baseline_kwh": base_kwh,
        "latest_cumulative_kwh": latest_kwh,
        "baseline_defined": baseline_defined,
        "latest_reading": {
            "timestamp": latest_reading["timestamp"],
            "cumulative_kwh": latest_reading["cumulative_kwh"],
            "power_watts": latest_reading["power_watts"],
            "source": latest_reading["source"],
            "is_simulated": bool(latest_reading["is_simulated"]),
        },
    }


if __name__ == "__main__":
    initialize_database()
    print(f"Database ready: {DB_PATH}")
