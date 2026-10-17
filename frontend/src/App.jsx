import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import {
  Zap,
  TrendingUp,
  IndianRupee,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import "./App.css";

const API = "http://localhost:8000";

export default function App() {
  const [units, setUnits] = useState(420);
  const [days, setDays] = useState(35);
  const [prediction, setPrediction] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function refreshPrediction() {
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
        throw new Error(await response.text());
      }

      setPrediction(await response.json());
    } catch (err) {
      setError("Cannot reach the backend. Check that FastAPI is running.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshPrediction();
  }, []);

  const chartData = prediction
    ? [
        { name: "Current", units: Number(units) },
        {
          name: "Forecast",
          units: prediction.predicted_final_units,
        },
        { name: "Slab limit", units: 500 },
      ]
    : [];

  const risk = prediction?.slab_risk || "Loading";

  return (
    <main className="dashboard">
      <header className="topbar">
        <div>
          <p className="eyebrow">RESIDENTIAL ENERGY INTELLIGENCE</p>
          <h1>Smart Energy Meter</h1>
          <p className="subtitle">
            Predict consumption. Manage your EB slab intelligently.
          </p>
        </div>
        <button onClick={refreshPrediction} className="refresh">
          <RefreshCw size={17} />
          Refresh
        </button>
      </header>

      <section className="notice">
        <Zap size={20} />
        <div>
          <strong>Predictive energy management</strong>
          <p>
            The current dashboard uses manually entered units.
            Live meter integration comes in a later step.
          </p>
        </div>
      </section>

      <section className="controls">
        <label>
          Current cycle consumption (units)
          <input
            type="number"
            min="0"
            value={units}
            onChange={(e) => setUnits(e.target.value)}
          />
        </label>
        <label>
          Days elapsed
          <input
            type="number"
            min="1"
            max="60"
            value={days}
            onChange={(e) => setDays(e.target.value)}
          />
        </label>
        <button onClick={refreshPrediction} disabled={loading}>
          {loading ? "Calculating..." : "Predict my bill"}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      <section className="cards">
        <article className="metric">
          <Zap />
          <span>Current consumption</span>
          <strong>{units || 0} units</strong>
        </article>

        <article className="metric">
          <TrendingUp />
          <span>Predicted final usage</span>
          <strong>
            {prediction
              ? `${prediction.predicted_final_units} units`
              : "—"}
          </strong>
        </article>

        <article className="metric">
          <IndianRupee />
          <span>Predicted energy charge</span>
          <strong>
            {prediction
              ? `₹${prediction.predicted_energy_charge.toLocaleString("en-IN")}`
              : "—"}
          </strong>
        </article>

        <article className="metric">
          <AlertTriangle />
          <span>Slab risk</span>
          <strong className="risk">{risk}</strong>
        </article>
      </section>

      <section className="panel">
        <h2>Consumption forecast</h2>
        <p className="muted">
          Compare current usage, forecast usage and the 500-unit threshold.
        </p>

        <div className="chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="units"
                stroke="#38bdf8"
                fill="#38bdf8"
                fillOpacity={0.15}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <footer>
        Raspberry Pi 4 · FastAPI · React · Forecasts are estimates,
        not actual meter readings.
      </footer>
    </main>
  );
}
