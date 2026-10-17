import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / "smart-energy" / "data" / "energy.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cumulative_kwh REAL NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual'
            )
        """)

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


def save_reading(cumulative_kwh, source="manual"):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO readings
                (timestamp, cumulative_kwh, source)
            VALUES (?, ?, ?)
            """,
            (
                datetime.now().astimezone().isoformat(),
                cumulative_kwh,
                source,
            ),
        )


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
            SELECT * FROM readings
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in reversed(rows)]


if __name__ == "__main__":
    initialize_database()
    print(f"Database ready: {DB_PATH}")
