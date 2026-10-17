# Smart Energy Meter & Predictive Tamil Nadu EB Tariff Monitor

An end-to-end residential electricity monitoring and predictive billing platform engineered for Tamil Nadu Electricity Board (TANGEDCO) bi-monthly domestic tariffs.

The platform combines an **ESP32 IoT sensor node**, a **Raspberry Pi 4 / Linux Gateway (FastAPI)**, an **SQLite persistent telemetry store**, and a **React 19 / Vite responsive dashboard**.

---

## Architecture Overview

```text
  [ 230V AC Mains ]
         │
    (CT Clamp)
         ▼
 ┌───────────────┐        Wi-Fi / HTTP POST         ┌─────────────────────────────────┐
 │  ESP32 Node   │ ───────────────────────────────> │  Raspberry Pi 4 Model B Gateway │
 │ (PZEM-004T or │      JSON Telemetry Packet       │  • FastAPI REST Engine (Port 8000)
 │  Simulation)  │                                  │  • SQLite Storage (data/energy.db)
 └───────────────┘                                  │  • Tariff & Prediction Heuristics
                                                    └─────────────────────────────────┘
                                                                     │
                                                             HTTP / WebSocket
                                                                     ▼
                                                    ┌─────────────────────────────────┐
                                                    │  React 19 + Vite Dashboard      │
                                                    │  • Live Telemetry Stream        │
                                                    │  • 60-Day Trajectory Projection │
                                                    │  • 500-Unit Slab Risk Warnings  │
                                                    └─────────────────────────────────┘
```

---

## Features

- **TANGEDCO Domestic Tariff Calculator:** Models tiered slab billing (0–200, 201–400, 401–500, 501–600, 601–800, 801–1000, >1000 units), explicitly identifying the steep ₹478 penalty cliff when consumption crosses 500 units.
- **Consumption Predictor:** Combines current billing cycle daily pace ($70\%$) with validated historical baseline averages ($30\%$) to forecast 60-day consumption and slab risk (`LOW`, `NEAR LIMIT`, `HIGH`).
- **Telemetry Ingestion Pipeline:** Standardized JSON telemetry format accepting cumulative energy (`kWh`), active power (`W`), RMS voltage (`V`), and current (`A`), with automatic interval delta calculation and meter rollover protection.
- **Measured vs. Simulated Distinction:** Explicit tagging on every telemetry packet (`is_simulated: boolean`) prevents test pulses from being mistaken for real hardware measurements.
- **Interactive Dark Dashboard:** Responsive interface built with React 19, Recharts, and Lucide React featuring trajectory projection curves, live packet feeds, and historical bill lookups.

---

## Quickstart Guide

### 1. Backend Setup (FastAPI & SQLite)

**Prerequisites:** Python 3.11+ (Python 3.13 supported)

```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server on port 8000
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Root:** `http://localhost:8000`
- **Swagger Documentation:** `http://localhost:8000/docs`
- **Healthcheck:** `http://localhost:8000/api/health`

### 2. Frontend Setup (React & Vite)

**Prerequisites:** Node.js v18+ and npm

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Or build for production
npm run build
```

The dashboard will open at `http://localhost:5173`.

### 3. Run Automated Tests

The repository contains a full unit and integration test suite:

```bash
# From the project root
python -m pytest -v
```

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Healthcheck returning `{"status": "healthy"}` |
| `GET` | `/api/config` | Global billing cycle length, threshold units, and tariff notes |
| `GET` | `/api/tariff/{units}` | Calculate estimated energy charge for specified units |
| `POST` | `/api/prediction` | Forecast end-of-cycle units and slab risk from current elapsed days |
| `GET` | `/api/readings` | Retrieve recent telemetry packets |
| `POST` | `/api/readings` | Ingest new meter reading (`cumulative_kwh`, `power_watts`, etc.) |
| `POST` | `/api/readings/simulate` | Generate a realistic diagnostic test reading |
| `GET` | `/api/cycle` | Active billing-cycle units derived from baseline |
| `POST` | `/api/cycle/baseline` | Set the cycle start baseline reading |
| `GET` | `/api/bills` | Historical bi-monthly bills loaded from `data/bills.csv` |

---

## ESP32 Firmware Setup

1. Open `firmware/esp32/` in Arduino IDE or VS Code with PlatformIO.
2. Copy `config.h.example` to `config.h`.
3. Fill in your Wi-Fi SSID, password, and Raspberry Pi IP address:
   ```c
   #define WIFI_SSID       "YourWiFiNetwork"
   #define WIFI_PASSWORD   "YourWiFiPassword"
   #define API_BASE_URL    "http://192.168.1.100:8000"
   ```
4. Choose operating mode:
   - `HARDWARE_SENSOR_CONNECTED 0`: Safe test simulation mode (injects realistic pulses).
   - `HARDWARE_SENSOR_CONNECTED 1`: Hardware mode interfacing with PZEM-004T v3.0 via UART.
5. Flash to ESP32 Dev Module @ 115200 baud.

For electrical wiring, isolation guidelines, and non-invasive CT rules, see [firmware/HARDWARE_SAFETY_INTEGRATION.md](file:///c:/Users/dksss/smart-energy/firmware/HARDWARE_SAFETY_INTEGRATION.md).

---

## Limitations & Disclaimer

- **Tariff Rates:** Calculations reflect the user-supplied TANGEDCO tiered slab formula. Electricity duty (taxes), fixed meter charges, and power purchase adjustments are excluded. Verify rates against official TNERC tariff orders before relying on estimates.
- **Forecasting Algorithm:** Predictions use a transparent, weighted moving heuristic ($70\%$ current cycle rate + $30\%$ historical baseline). This is not an AI/ML black-box model.
- **High-Voltage Safety:** Never connect microcontrollers directly to 230V AC mains. Always use certified, galvanically isolated measurement modules.
