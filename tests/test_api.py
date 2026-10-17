import sys
from pathlib import Path
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app

client = TestClient(app)


def test_home_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["project"] == "Smart Energy Meter"
    assert data["status"] == "running"


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_config_endpoint():
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert data["billing_cycle_days"] == 60
    assert data["monitored_threshold_units"] == 500
    assert data["currency"] == "INR"


def test_tariff_endpoint():
    res = client.get("/api/tariff/400")
    assert res.status_code == 200
    assert res.json()["estimated_energy_charge"] == 940.0

    res_neg = client.get("/api/tariff/-10")
    assert res_neg.status_code == 400


def test_prediction_endpoint_valid():
    res = client.post(
        "/api/prediction",
        json={"current_units": 420, "days_elapsed": 35, "cycle_days": 60},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["current_units"] == 420.0
    assert data["predicted_final_units"] > 420.0
    assert "current_energy_charge" in data
    assert "predicted_energy_charge" in data
    assert "slab_risk" in data
    assert "units_remaining_before_500" in data


def test_prediction_endpoint_validation():
    # days_elapsed > cycle_days
    res = client.post(
        "/api/prediction",
        json={"current_units": 420, "days_elapsed": 50, "cycle_days": 40},
    )
    assert res.status_code == 400


def test_readings_endpoint_get_and_post():
    # POST a test reading with rich telemetry
    payload = {
        "cumulative_kwh": 3456.78,
        "power_watts": 450.5,
        "voltage": 230.2,
        "current_amps": 1.95,
        "source": "iot_test_node",
        "is_simulated": False,
    }
    post_res = client.post("/api/readings", json=payload)
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "saved"
    reading = post_res.json()["reading"]
    assert reading["cumulative_kwh"] == 3456.78
    assert reading["power_watts"] == 450.5
    assert reading["source"] == "iot_test_node"
    assert reading["is_simulated"] is False

    # GET readings
    get_res = client.get("/api/readings")
    assert get_res.status_code == 200
    readings = get_res.json()
    assert isinstance(readings, list)
    assert any(r["cumulative_kwh"] == 3456.78 for r in readings)


def test_simulation_endpoint():
    res = client.post("/api/readings/simulate")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "simulated"
    reading = data["reading"]
    assert reading["is_simulated"] is True
    assert reading["source"] == "simulated_iot_node"
    assert reading["power_watts"] > 0
    assert 220 <= reading["voltage"] <= 245


def test_cycle_and_baseline_endpoints():
    # Baseline setup
    base_res = client.post(
        "/api/cycle/baseline",
        json={"baseline_kwh": 3000.0, "notes": "Cycle started Nov 1"},
    )
    assert base_res.status_code == 200
    assert base_res.json()["status"] == "configured"

    # Query cycle status
    cycle_res = client.get("/api/cycle")
    assert cycle_res.status_code == 200
    cycle_data = cycle_res.json()
    assert cycle_data["baseline_defined"] is True
    assert cycle_data["baseline_kwh"] == 3000.0
    assert cycle_data["current_units"] >= 0.0


def test_bills_endpoint():
    res = client.get("/api/bills")
    assert res.status_code == 200
    data = res.json()
    assert data["total_records"] == 6
    assert data["average_units"] > 400
    assert len(data["bills"]) == 6
