import { useEffect, useState, useCallback } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import {
  Zap,
  TrendingUp,
  IndianRupee,
  AlertTriangle,
  RefreshCw,
  Cpu,
  History,
  Activity,
  CheckCircle,
  XCircle,
  HelpCircle,
} from "lucide-react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [units, setUnits] = useState(420);
  const [days, setDays] = useState(35);
  const [prediction, setPrediction] = useState(null);
  const [readings, setReadings] = useState([]);
  const [cycleInfo, setCycleInfo] = useState(null);
  const [historicalBills, setHistoricalBills] = useState([]);
  const [loading, setLoading] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [connected, setConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("forecast"); // "forecast" | "readings" | "history"

  const fetchCycleAndReadings = useCallback(async () => {
    try {
      const [cycleRes, readingsRes, billsRes] = await Promise.all([
        fetch(`${API}/api/cycle`),
        fetch(`${API}/api/readings?limit=15`),
        fetch(`${API}/api/bills`),
      ]);

      if (cycleRes.ok) {
        const cData = await cycleRes.json();
        setCycleInfo(cData);
      }

      if (readingsRes.ok) {
        const rData = await readingsRes.json();
        setReadings(rData);
      }

      if (billsRes.ok) {
        const bData = await billsRes.json();
        setHistoricalBills(bData.bills || []);
      }

      setConnected(true);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch {
      setConnected(false);
    }
  }, []);

  const refreshPrediction = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API}/api/prediction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_units: Number(units),
          days_elapsed: Number(days),
          cycle_days: 60,
        }),
      });

      if (!response.ok) {
        const errDetail = await response.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(errDetail.detail || "Prediction request rejected by backend");
      }

      const pData = await response.json();
      setPrediction(pData);
      setConnected(true);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setConnected(false);
      setError(err.message || "Cannot reach the backend. Check that FastAPI is running.");
    } finally {
      setLoading(false);
    }
  }, [units, days]);

  const handleSimulateReading = async () => {
    setSimulating(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/readings/simulate`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Simulation failed");
      await fetchCycleAndReadings();
    } catch (err) {
      setError("Failed to generate simulated reading: " + err.message);
    } finally {
      setSimulating(false);
    }
  };

  const handleSyncWithLiveMeter = () => {
    if (cycleInfo && cycleInfo.current_units > 0) {
      setUnits(cycleInfo.current_units);
    }
  };

  useEffect(() => {
    fetchCycleAndReadings();
    refreshPrediction();
    const interval = setInterval(fetchCycleAndReadings, 15000); // Polling every 15s for live telemetry
    return () => clearInterval(interval);
  }, [fetchCycleAndReadings, refreshPrediction]);

  // Generate 60-day projection trajectory points for the chart
  const buildTrajectoryData = () => {
    if (!prediction) return [];
    const currentUnitsNum = Number(units);
    const daysElapsedNum = Number(days);
    const finalPredicted = prediction.predicted_final_units;
    const dailyProjectedPace = (finalPredicted - currentUnitsNum) / Math.max(1, 60 - daysElapsedNum);

    const points = [];
    const step = 5; // Day intervals: 0, 5, 10, ... 60
    for (let d = 0; d <= 60; d += step) {
      const point = { day: `Day ${d}`, threshold: 500 };
      if (d <= daysElapsedNum) {
        // Actual historical pace up to current day
        point.actual = roundVal((currentUnitsNum / daysElapsedNum) * d);
        if (d === daysElapsedNum) {
          point.forecast = point.actual;
        }
      } else {
        // Forecasted pace from current day onwards
        point.forecast = roundVal(currentUnitsNum + dailyProjectedPace * (d - daysElapsedNum));
      }
      points.push(point);
    }
    return points;
  };

  const roundVal = (v) => Math.round(v * 10) / 10;
  const trajectoryData = buildTrajectoryData();
  const latestReading = readings.length > 0 ? readings[readings.length - 1] : null;

  return (
    <main className="dashboard">
      {/* Top Header */}
      <header className="topbar">
        <div>
          <div className="status-row">
            <span className="eyebrow">RESIDENTIAL ENERGY INTELLIGENCE</span>
            <span className={`pill-badge ${connected ? "pill-online" : "pill-offline"}`}>
              {connected ? <CheckCircle size={13} /> : <XCircle size={13} />}
              {connected ? "API CONNECTED" : "OFFLINE / DISCONNECTED"}
            </span>
            {lastUpdated && <span className="timestamp-note">Synced {lastUpdated}</span>}
          </div>
          <h1>Smart Energy Meter</h1>
          <p className="subtitle">
            Tamil Nadu EB (TANGEDCO) Predictive Tariff Management &amp; IoT Monitor
          </p>
        </div>

        <div className="top-actions">
          <button
            onClick={handleSimulateReading}
            disabled={simulating}
            className="btn-secondary"
            title="Generate a realistic test reading clearly marked as simulated"
          >
            <Cpu size={16} />
            {simulating ? "Generating..." : "Simulate IoT Pulse"}
          </button>
          <button onClick={refreshPrediction} disabled={loading} className="refresh">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Refresh
          </button>
        </div>
      </header>

      {/* IoT Gateway Status Banner */}
      <section className="iot-banner">
        <div className="iot-status-left">
          <Activity size={22} className="accent-icon" />
          <div>
            <strong>Raspberry Pi 4 IoT Gateway</strong>
            <p className="muted">
              {latestReading
                ? `Latest Telemetry: ${latestReading.cumulative_kwh} kWh | Active Load: ${latestReading.power_watts ?? "—"} W | Source: ${latestReading.source}`
                : "No telemetry packets received yet. Click 'Simulate IoT Pulse' to inject test readings."}
            </p>
          </div>
        </div>
        {latestReading && (
          <span className={`tag ${latestReading.is_simulated ? "tag-simulated" : "tag-measured"}`}>
            {latestReading.is_simulated ? "SIMULATED TELEMETRY" : "MEASURED HARDWARE"}
          </span>
        )}
      </section>

      {/* Main Prediction & Cycle Controls */}
      <section className="controls">
        <label>
          Current Cycle Units (kWh)
          <div className="input-with-button">
            <input
              type="number"
              min="0"
              step="0.1"
              value={units}
              onChange={(e) => setUnits(e.target.value)}
            />
            {cycleInfo && cycleInfo.current_units > 0 && (
              <button
                type="button"
                className="btn-inline"
                onClick={handleSyncWithLiveMeter}
                title="Populate from latest meter baseline calculation"
              >
                Use Live ({cycleInfo.current_units}u)
              </button>
            )}
          </div>
        </label>
        <label>
          Days Elapsed in 60-Day Cycle
          <input
            type="number"
            min="1"
            max="60"
            value={days}
            onChange={(e) => setDays(e.target.value)}
          />
        </label>
        <button onClick={refreshPrediction} disabled={loading} className="btn-primary">
          {loading ? "Calculating..." : "Predict Bill & Slab Risk"}
        </button>
      </section>

      {error && <div className="error-banner">{error}</div>}

      {/* Key Metric Cards */}
      <section className="cards">
        <article className="metric">
          <div className="metric-header">
            <Zap size={20} />
            <span>Current Consumption</span>
          </div>
          <strong>{units || 0} units</strong>
          <span className="metric-detail">
            Rate: {days > 0 ? (Number(units) / Number(days)).toFixed(1) : 0} units/day
          </span>
        </article>

        <article className="metric">
          <div className="metric-header">
            <TrendingUp size={20} />
            <span>Predicted Final Units</span>
          </div>
          <strong>
            {prediction ? `${prediction.predicted_final_units} units` : "—"}
          </strong>
          <span className="metric-detail">
            {prediction ? `Forecast: ${prediction.predicted_daily_average} u/day` : "Awaiting calculation"}
          </span>
        </article>

        <article className="metric">
          <div className="metric-header">
            <IndianRupee size={20} />
            <span>Predicted Energy Charge</span>
          </div>
          <strong>
            {prediction ? `₹${prediction.predicted_energy_charge.toLocaleString("en-IN")}` : "—"}
          </strong>
          <span className="metric-detail">
            Current pace: {prediction ? `₹${prediction.current_energy_charge.toLocaleString("en-IN")}` : "—"}
          </span>
        </article>

        <article className={`metric metric-risk ${prediction?.slab_risk === "HIGH" ? "risk-high" : ""}`}>
          <div className="metric-header">
            <AlertTriangle size={20} />
            <span>500-Unit Slab Risk</span>
          </div>
          <strong className="risk-badge">
            {prediction ? prediction.slab_risk : "Loading"}
          </strong>
          <span className="metric-detail">
            {prediction && prediction.units_remaining_before_500 > 0
              ? `${prediction.units_remaining_before_500} units until penalty threshold`
              : "Crossed 500-unit threshold"}
          </span>
        </article>
      </section>

      {/* Visual Tab Navigation */}
      <section className="tab-nav">
        <button
          className={`tab-btn ${activeTab === "forecast" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("forecast")}
        >
          <TrendingUp size={16} />
          Consumption Forecast (60 Days)
        </button>
        <button
          className={`tab-btn ${activeTab === "readings" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("readings")}
        >
          <Activity size={16} />
          Live Meter Readings ({readings.length})
        </button>
        <button
          className={`tab-btn ${activeTab === "history" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("history")}
        >
          <History size={16} />
          Historical EB Bills ({historicalBills.length})
        </button>
      </section>

      {/* Tab Panels */}
      {activeTab === "forecast" && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Bi-Monthly Trajectory Projection</h2>
              <p className="muted">
                Tracking consumption from Day 1 to Day 60 against the critical 500-unit TANGEDCO cliff.
              </p>
            </div>
            <div className="legend-pills">
              <span className="pill pill-actual">Actual Pace</span>
              <span className="pill pill-forecast">Projected Forecast</span>
              <span className="pill pill-threshold">500-Unit Threshold</span>
            </div>
          </div>

          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={trajectoryData} margin={{ top: 20, right: 30, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2d42" />
                <XAxis dataKey="day" stroke="#718096" tick={{ fill: "#a0aec0", fontSize: 12 }} />
                <YAxis stroke="#718096" tick={{ fill: "#a0aec0", fontSize: 12 }} unit=" u" />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0e1726", borderColor: "#2d3748", borderRadius: 8 }}
                  formatter={(val, name) => [`${val} units`, name === "actual" ? "Recorded" : name === "forecast" ? "Projected" : "Threshold"]}
                />
                <ReferenceLine
                  y={500}
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  strokeWidth={2}
                  label={{ value: "500-Unit Slab Limit", fill: "#ef4444", position: "insideTopRight" }}
                />
                <Area
                  type="monotone"
                  dataKey="actual"
                  stroke="#38bdf8"
                  fill="#38bdf8"
                  fillOpacity={0.2}
                  strokeWidth={3}
                />
                <Line
                  type="monotone"
                  dataKey="forecast"
                  stroke="#fbbf24"
                  strokeDasharray="5 5"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: "#fbbf24" }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {activeTab === "readings" && (
        <section className="panel">
          <h2>Recent Telemetry Packets</h2>
          <p className="muted">Telemetry streamed via ESP32 Wi-Fi or diagnostic test generator.</p>

          <div className="table-wrapper">
            <table className="telemetry-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Cumulative kWh</th>
                  <th>Interval Delta</th>
                  <th>Active Power</th>
                  <th>Voltage</th>
                  <th>Source</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {readings.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="text-center muted">No telemetry recorded yet.</td>
                  </tr>
                ) : (
                  [...readings].reverse().map((r) => (
                    <tr key={r.id}>
                      <td>{new Date(r.timestamp).toLocaleString()}</td>
                      <td><strong>{r.cumulative_kwh.toFixed(2)} kWh</strong></td>
                      <td>+{r.interval_kwh ? r.interval_kwh.toFixed(3) : "0.000"} kWh</td>
                      <td>{r.power_watts ? `${r.power_watts} W` : "—"}</td>
                      <td>{r.voltage ? `${r.voltage} V` : "—"}</td>
                      <td><code>{r.source}</code></td>
                      <td>
                        <span className={`tag-sm ${r.is_simulated ? "tag-sim" : "tag-meas"}`}>
                          {r.is_simulated ? "SIMULATED" : "MEASURED"}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {activeTab === "history" && (
        <section className="panel">
          <h2>Historical Tamil Nadu EB Billing Cycles</h2>
          <p className="muted">Verified historical records loaded from data/bills.csv.</p>

          <div className="table-wrapper">
            <table className="telemetry-table">
              <thead>
                <tr>
                  <th>Cycle Period</th>
                  <th>Total Units Consumed</th>
                  <th>Average Daily Rate</th>
                  <th>Threshold Status</th>
                </tr>
              </thead>
              <tbody>
                {historicalBills.map((b, idx) => (
                  <tr key={idx}>
                    <td>{b.billing_start} to {b.billing_end}</td>
                    <td><strong>{b.units} units</strong></td>
                    <td>~{(b.units / 60).toFixed(1)} u/day</td>
                    <td>
                      <span className={`tag-sm ${b.units <= 500 ? "tag-meas" : "tag-sim"}`}>
                        {b.units <= 500 ? "Within Free Tier Slab (<=500)" : "Crossed 500 Units"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Methodology & Safety Disclaimers */}
      <footer className="footer-disclaimer">
        <div className="disclaimer-content">
          <HelpCircle size={16} />
          <span>
            <strong>Tariff &amp; Algorithm Methodology:</strong> Predictions utilize a weighted moving heuristic
            (70% current daily pace + 30% validated historical baseline average). Tariff calculation evaluates Tamil Nadu EB
            telescopic slab tiers. Estimates reflect energy slab charges only; electricity duty (taxes), fixed meter charges,
            and solar net-metering adjustments are not included. Never connect microcontrollers directly to 230V mains without galvanic isolation.
          </span>
        </div>
      </footer>
    </main>
  );
}
