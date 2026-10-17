import os
import random
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tariff import calculate_energy_charge
from predictor import predict_consumption
from bills import load_bills
from database import (
    initialize_database,
    save_prediction,
    save_reading,
    get_recent_readings,
    get_recent_predictions,
    get_cycle_consumption,
    set_cycle_baseline,
    get_latest_baseline,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Smart Energy Meter",
    description=(
        "Predictive Tamil Nadu EB tariff management "
        "and residential energy monitoring"
    ),
    version="1.1.0",
    lifespan=lifespan,
)


# Allow the React dashboard to communicate with FastAPI.
# Configurable via ALLOWED_ORIGINS env var (comma-separated), with sensible local defaults.
env_origins = os.getenv("ALLOWED_ORIGINS", "")
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
]
configured_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
origins = list(dict.fromkeys(default_origins + configured_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)


class PredictionRequest(BaseModel):
    current_units: float = Field(ge=0, description="Current units consumed in billing cycle")
    days_elapsed: int = Field(ge=1, le=60, description="Days elapsed in the current cycle")
    cycle_days: int = Field(default=60, ge=1, le=60, description="Total cycle duration (usually 60 days)")


class ReadingRequest(BaseModel):
    cumulative_kwh: float = Field(ge=0, description="Cumulative meter energy in kWh")
    power_watts: Optional[float] = Field(default=None, ge=0, description="Active power in Watts")
    voltage: Optional[float] = Field(default=None, ge=0, description="AC Voltage in Volts")
    current_amps: Optional[float] = Field(default=None, ge=0, description="AC Current in Amperes")
    source: str = Field(default="manual", max_length=50, description="Sensor/device identifier")
    is_simulated: bool = Field(default=False, description="Flag explicitly designating test/simulated data")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp of measurement")


class BaselineRequest(BaseModel):
    baseline_kwh: float = Field(ge=0, description="Starting cumulative kWh meter reading for billing cycle")
    start_date: Optional[str] = Field(default=None, description="Cycle start ISO date/timestamp")
    cycle_days: int = Field(default=60, ge=1, le=60)
    notes: Optional[str] = None


@app.get("/")
def home():
    return {
        "project": "Smart Energy Meter",
        "status": "running",
        "version": "1.1.0",
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/config")
def config():
    return {
        "billing_cycle_days": 60,
        "monitored_threshold_units": 500,
        "currency": "INR",
        "tariff_source": (
            "User-supplied tariff table; verify against "
            "the applicable official TANGEDCO tariff"
        ),
        "notes": (
            "Energy charges estimate electricity slab rates only. Fixed charges, "
            "electricity duty (taxes), meter rent, and government subsidies may differ."
        ),
    }


@app.get("/api/tariff/{units}")
def tariff(units: float):
    if units < 0:
        raise HTTPException(
            status_code=400,
            detail="Units cannot be negative",
        )

    return {
        "units": units,
        "estimated_energy_charge": calculate_energy_charge(units),
        "note": "Energy charge estimate only; excludes fixed charges and duties.",
    }


@app.post("/api/prediction")
def prediction(data: PredictionRequest):
    if data.days_elapsed > data.cycle_days:
        raise HTTPException(
            status_code=400,
            detail="Elapsed days cannot exceed cycle days",
        )

    try:
        result = predict_consumption(
            current_units=data.current_units,
            days_elapsed=data.days_elapsed,
            cycle_days=data.cycle_days,
        )

        result["current_energy_charge"] = calculate_energy_charge(data.current_units)
        result["predicted_energy_charge"] = calculate_energy_charge(
            result["predicted_final_units"]
        )
        result["units_remaining_before_500"] = round(
            max(0.0, 500.0 - data.current_units), 2
        )
        result["method"] = "Weighted moving heuristic (70% current daily rate + 30% historical daily rate)"

        # Save the completed prediction to SQLite.
        save_prediction(result)

        return result

    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@app.post("/api/readings")
def add_reading(data: ReadingRequest):
    try:
        record = save_reading(
            cumulative_kwh=data.cumulative_kwh,
            power_watts=data.power_watts,
            voltage=data.voltage,
            current_amps=data.current_amps,
            source=data.source,
            is_simulated=data.is_simulated,
            timestamp=data.timestamp,
        )
        return {
            "status": "saved",
            "reading": record,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/api/readings")
def readings(limit: int = 100):
    return get_recent_readings(limit=min(limit, 500))


@app.get("/api/predictions")
def predictions(limit: int = 10):
    return get_recent_predictions(limit=min(limit, 50))


@app.get("/api/cycle")
def cycle_status():
    """Returns the current billing-cycle consumption derived from the configured baseline."""
    return get_cycle_consumption()


@app.post("/api/cycle/baseline")
def set_baseline(data: BaselineRequest):
    """Define a baseline cumulative reading for the start of the billing cycle."""
    try:
        set_cycle_baseline(
            baseline_kwh=data.baseline_kwh,
            start_date=data.start_date,
            cycle_days=data.cycle_days,
            notes=data.notes,
        )
        return {
            "status": "configured",
            "baseline": get_latest_baseline(),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/bills")
def historical_bills():
    """Retrieve validated historical bi-monthly bills."""
    try:
        df = load_bills()
        # Convert Timestamps to ISO strings for JSON serialization
        df_json = df.copy()
        df_json["billing_start"] = df_json["billing_start"].dt.strftime("%Y-%m-%d")
        df_json["billing_end"] = df_json["billing_end"].dt.strftime("%Y-%m-%d")
        return {
            "total_records": len(df_json),
            "average_units": round(float(df_json["units"].mean()), 2),
            "max_units": float(df_json["units"].max()),
            "bills": df_json.to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/readings/simulate")
def simulate_reading():
    """Generate a realistic test reading clearly flagged as simulated."""
    # Fetch last reading to increment cumulative_kwh realistically
    recent = get_recent_readings(limit=1)
    if recent:
        last_kwh = recent[-1]["cumulative_kwh"]
    else:
        last_kwh = 1200.0

    # Simulate realistic domestic household active power (200W - 1200W)
    power_watts = round(random.uniform(220.0, 950.0), 1)
    voltage = round(random.uniform(228.0, 235.0), 1)
    # Active current = Power / (Voltage * PowerFactor ~0.9)
    current_amps = round(power_watts / (voltage * 0.9), 2)
    # 5-minute equivalent energy increment = (watts * 5 / 60) / 1000 = watts / 12000
    increment_kwh = round(power_watts / 12000.0, 4)
    new_cumulative = round(last_kwh + increment_kwh, 4)

    record = save_reading(
        cumulative_kwh=new_cumulative,
        power_watts=power_watts,
        voltage=voltage,
        current_amps=current_amps,
        source="simulated_iot_node",
        is_simulated=True,
    )
    return {
        "status": "simulated",
        "reading": record,
    }
