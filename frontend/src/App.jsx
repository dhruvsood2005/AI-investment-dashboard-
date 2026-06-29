import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A';
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/A';
  return Number(value).toFixed(2);
}

function MetricCard({ label, value, type = 'percent' }) {
  return (
    <div className="metric-card">
      <p>{label}</p>
      <h3>{type === 'number' ? formatNumber(value) : formatPercent(value)}</h3>
    </div>
  );
}

export default function App() {
  const [ticker, setTicker] = useState('CBA.AX');
  const [benchmark, setBenchmark] = useState('^AXJO');
  const [period, setPeriod] = useState('5y');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleAnalyze(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    setData(null);

    try {
      const url = new URL(`${API_BASE}/api/analyze`);
      url.searchParams.set('ticker', ticker);
      url.searchParams.set('benchmark', benchmark);
      url.searchParams.set('period', period);
      url.searchParams.set('var_confidence', '0.95');
      url.searchParams.set('risk_free_rate', '0.04');

      const response = await fetch(url);
      const json = await response.json();

      if (!response.ok) {
        throw new Error(json.detail || 'Something went wrong');
      }

      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const metrics = data?.metrics;
  const summary = data?.summary;

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Finance + actuarial + coding + AI - DHRUV SOOD</p>
        <h1>AI Investment Risk Dashboard</h1>
        <p className="subtitle">
          Analyse listed equities and ETFs using returns, volatility, drawdowns, VaR, Expected Shortfall,
          benchmark comparison, and an AI-style risk summary.
        </p>
      </section>

      <form className="panel form-panel" onSubmit={handleAnalyze}>
        <label>
          Stock / ETF ticker
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="CBA.AX" />
        </label>

        <label>
          Benchmark
          <input value={benchmark} onChange={(e) => setBenchmark(e.target.value)} placeholder="^AXJO" />
        </label>

        <label>
          Period
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="6mo">6 months</option>
            <option value="1y">1 year</option>
            <option value="2y">2 years</option>
            <option value="5y">5 years</option>
            <option value="10y">10 years</option>
            <option value="max">Max</option>
          </select>
        </label>

        <button type="submit" disabled={loading}>{loading ? 'Analysing...' : 'Analyse risk'}</button>
      </form>

      {error && <div className="error">{error}</div>}

      {data && (
        <>
          <section className="panel">
            <div className="section-heading">
              <h2>{data.ticker} vs {data.benchmark}</h2>
              <p>{data.disclaimer}</p>
            </div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={360}>
                <LineChart data={data.chart_data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" minTickGap={40} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="indexed_price" name={`${data.ticker} indexed`} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="indexed_benchmark" name={`${data.benchmark} indexed`} dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="metrics-grid">
            <MetricCard label="Annualised return" value={metrics.annualised_return} />
            <MetricCard label="Volatility" value={metrics.volatility} />
            <MetricCard label="Max drawdown" value={metrics.max_drawdown} />
            <MetricCard label="Sharpe ratio" value={metrics.sharpe_ratio} type="number" />
            <MetricCard label="95% daily VaR" value={metrics.value_at_risk} />
            <MetricCard label="Expected Shortfall" value={metrics.expected_shortfall} />
            <MetricCard label="Benchmark annualised return" value={metrics.benchmark_annualised_return} />
            <MetricCard label="Excess return vs benchmark" value={metrics.excess_return_vs_benchmark} />
            <MetricCard label="Beta vs benchmark" value={metrics.beta_vs_benchmark} type="number" />
            <MetricCard label="Correlation vs benchmark" value={metrics.correlation_vs_benchmark} type="number" />
          </section>

          <section className="panel summary-grid">
            <div>
              <h3>Risks</h3>
              <p>{summary.risks}</p>
            </div>
            <div>
              <h3>Bull case</h3>
              <p>{summary.bull_case}</p>
            </div>
            <div>
              <h3>Bear case</h3>
              <p>{summary.bear_case}</p>
            </div>
            <div>
              <h3>Catalysts to research</h3>
              <p>{summary.catalysts}</p>
            </div>
            <div>
              <h3>Sharpe comment</h3>
              <p>{summary.sharpe_comment}</p>
            </div>
            <div>
              <h3>AI note</h3>
              <p>{summary.ai_note}</p>
            </div>
            <div>
              <h3>Summary source</h3>
              <p>{summary.summary_source || 'unknown'}</p>
            </div>

            <div>
              <h3>Model used</h3>
              <p>{summary.model_used || 'unknown'}</p>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
