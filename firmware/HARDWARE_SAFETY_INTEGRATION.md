# Hardware Safety & Real Energy Meter Integration Guide

## 1. High-Voltage Mains Warning & Electrical Safety

> [!CAUTION]
> **LETHAL VOLTAGE HAZARD (230V AC)**  
> Residential electricity in Tamil Nadu / India operates at **230V RMS AC, 50 Hz**, which carries severe, potentially fatal electric shock and fire hazards.
> - **NEVER** connect raw mains voltage (Line/Neutral) directly to the ESP32, Raspberry Pi, or unrated breadboard circuits.
> - All high-voltage physical installation on the distribution board (DB) must be performed by a **licensed, qualified electrician**.
> - Switch off the main MCB (Miniature Circuit Breaker) before inspecting or installing any measurement devices.

---

## 2. Recommended Isolated Meter Interfaces

### Option A: PZEM-004T v3.0 Energy Monitoring Module (Recommended)
The PZEM-004T is an industry-standard, factory-calibrated AC power monitoring board equipped with built-in galvanic isolation:
- **Voltage Measurement:** 80 to 260V AC
- **Current Measurement:** 0 to 100A with a Non-Invasive Split-Core Current Transformer (CT)
- **Power Measurement:** 0 to 23 kW
- **Energy Measurement:** 0 to 9999.99 kWh
- **Communication Protocol:** Modbus-RTU over 9600 baud UART (5V / 3.3V logic)
- **Isolation:** Internal optocouplers physically separate the 230V AC measurement circuitry from the 3.3V/5V microcontroller logic header.

#### Wiring Diagram & Pinout
```text
  [ 230V AC Mains ]
       │      │
       ▼      ▼
   [ L ]    [ N ]
  ┌───────────────────────────────┐
  │       PZEM-004T v3.0          │
  │                               │
  │ [ CT1 ] ── Split-Core CT      │
  │ [ CT2 ]    (Clamped on Live)  │
  └───────────────────────────────┘
       │    │    │    │ (Optocoupled Low-Voltage Header)
      5V   GND   TX   RX
       │    │    │    │
       ▼    ▼    ▼    ▼
     VIN   GND  GPIO16 GPIO17
  ┌───────────────────────────────┐
  │         ESP32 Node            │
  └───────────────────────────────┘
```

#### Modbus-RTU Input Registers
| Register Address | Parameter | Resolution / Unit | Register Count |
| :---: | :---: | :---: | :---: |
| `0x0000` | Voltage | 0.1 V | 1 (16-bit) |
| `0x0001` - `0x0002` | Current | 0.001 A | 2 (32-bit low/high) |
| `0x0003` - `0x0004` | Power | 0.1 W | 2 (32-bit low/high) |
| `0x0005` - `0x0006` | Energy | 1 Wh (0.001 kWh) | 2 (32-bit low/high) |
| `0x0007` | Frequency | 0.1 Hz | 1 (16-bit) |
| `0x0008` | Power Factor | 0.01 | 1 (16-bit) |

---

### Option B: Industrial DIN-Rail Meter (Eastron SDM120 / SDM230 Modbus RS485)
For utility-grade installations in a distribution panel:
- Mounts directly to 35mm DIN rail.
- Communicates via RS-485 balanced serial bus.
- **Interfacing to Raspberry Pi:** Use an industrial USB-to-RS485 transceiver (with CH340 or FTDI chip and TVS surge diodes).
- Connect `A+` to `A+`, `B-` to `B-`.
- Python library `pymodbus` or `minimalmodbus` polls registers directly from the Raspberry Pi gateway.

---

## 3. Current Transformer (CT) Non-Invasive Safety Rules

1. **Never open-circuit a secondary CT under load:**
   If a Current Transformer (e.g. SCT-013) is clamped around an energized cable without a burden resistor or while unplugged, extreme high-voltage spikes can develop across the open secondary terminals, causing dielectric breakdown or electric shock.
2. **Directionality:**
   Install the CT clamp in the direction of the load (indicated by an arrow on the clamp).
3. **Single Conductor Only:**
   Clamp only the **Live (Phase)** wire, NOT both Live and Neutral together. Clamping both causes magnetic flux cancellation resulting in a 0A reading.

---

## 4. Software Disconnection & Brownout Recovery
- **Flash Persistence (NVS):** Cumulative kWh is stored in ESP32 Non-Volatile Flash (`Preferences` library). Upon reboot or grid power outage, the counter resumes from the last known state rather than zeroing out.
- **Timeout & Retries:** HTTP requests to the Raspberry Pi use a 5-second connection timeout. If the Pi or local Wi-Fi router is offline, the ESP32 logs an error and retries with backoff without dropping its internal energy accumulation.
- **Meter Rollover Detection:** The backend checks successive cumulative kWh readings. If a lower value is received (due to hardware replacement or 99999 kWh counter overflow), the interval delta calculation resets cleanly to 0 rather than creating negative energy consumption.
