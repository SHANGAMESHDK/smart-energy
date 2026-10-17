from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tariff import calculate_energy_charge
from predictor import predict_consumption
from database import (
    initialize_database,
    save_prediction,
    save_reading,
    get_recent_readings,
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
    version="1.0.0",
    lifespan=lifespan,
)


# Allow the React dashboard to communicate with FastAPI.
# Add your actual frontend origin here if it differs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.1.7:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class PredictionRequest(BaseModel):
    current_units: float = Field(ge=0)
    days_elapsed: int = Field(ge=1, le=60)
    cycle_days: int = Field(default=60, ge=1, le=60)


class ReadingRequest(BaseModel):
    cumulative_kwh: float = Field(ge=0)


@app.get("/")
def home():
    return {
        "project": "Smart Energy Meter",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/tariff/{units}")
def tariff(units: float):
    if units < 0:
        raise HTTPException(
            status_code=400,
            detail="Units cannot be negative",
        )

    return {
        "units": units,
        "estimated_energy_charge":
            calculate_energy_charge(units),
        "note": "Energy charge estimate only",
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

        result["current_energy_charge"] = (
            calculate_energy_charge(data.current_units)
        )

        result["predicted_energy_charge"] = (
            calculate_energy_charge(
                result["predicted_final_units"]
            )
        )

        result["units_remaining_before_500"] = round(
            max(0, 500 - data.current_units), 2
        )

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
        save_reading(data.cumulative_kwh, source="manual")

        return {
            "status": "saved",
            "cumulative_kwh": data.cumulative_kwh,
        }

    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/api/readings")
def readings():
    return get_recent_readings()


@app.get("/api/config")
def config():
    return {
        "billing_cycle_days": 60,
        "monitored_threshold_units": 500,
        "currency": "INR",
        "tariff_source": (
            "User-supplied tariff table; verify against "
            "the applicable official tariff"
        ),
    }
