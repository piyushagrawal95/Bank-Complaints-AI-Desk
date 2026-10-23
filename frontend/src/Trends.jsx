import { useEffect, useState } from "react";
import { getSpikes } from "./api";
import { IconAlert, IconCheck } from "./Icons";
import "./Trends.css";

const GROUPS = [
  { value: "product", label: "Product" },
  { value: "issue", label: "Issue" },
  { value: "company", label: "Company" },
];

function formatChange(pct) {
  if (pct == null) {
    return <span className="shift-badge shift-new">New Category</span>;
  }
  const isPos = pct > 0;
  return (
    <span className={`shift-badge ${isPos ? "shift-up" : "shift-down"}`}>
      {isPos ? `+${pct}%` : `${pct}%`}
    </span>
  );
}

function Trends() {
  const [groupBy, setGroupBy] = useState("product");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);

    getSpikes({ group_by: groupBy })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [groupBy]);

  const spikes = data ? data.items.filter((i) => i.is_spike) : [];
  const others = data ? data.items.filter((i) => !i.is_spike).slice(0, 15) : [];

  return (
    <div className="trends-container">
      <div className="trends-header">
        <div>
          <h2>Operational Spikes & Trend Analytics</h2>
          <p className="trends-subtitle">
            Monitors sudden volume surges across complaint categories to alert supervisors and compliance officers in real-time.
          </p>
        </div>
        <div className="trend-controls">
          <label htmlFor="group-by">Group By:</label>
          <select
            id="group-by"
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
          >
            {GROUPS.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="error">Could not load trends: {error}</div>}
      {loading && <p className="info">Analyzing rolling historical baselines...</p>}

      {data && (
        <>
          {data.as_of === null ? (
            <p className="info">No complaint records found to calculate trends.</p>
          ) : (
            <>
              <div className="trend-summary-bar">
                <span>Data As Of: <strong>{data.as_of}</strong></span>
                <span>Active Window: <strong>Last {data.window_days} Days</strong></span>
                <span>Spike Threshold: <strong>≥ {data.threshold}x Baseline</strong></span>
              </div>

              {!data.enough_history && (
                <div className="trend-warning">
                  <IconAlert size={15} /> The dataset has limited history; baseline comparisons may be tentative.
                </div>
              )}

              {spikes.length > 0 ? (
                <div className="trend-banner trend-alert">
                  <IconAlert size={16} /> {spikes.length} High-Risk Volume Spike{spikes.length > 1 ? "s" : ""} Detected
                </div>
              ) : (
                <div className="trend-banner trend-ok">
                  <IconCheck size={16} /> Normal Operations: No volume spikes exceeding threshold detected.
                </div>
              )}

              {spikes.length > 0 && (
                <div className="spike-grid">
                  {spikes.map((s) => (
                    <div className="spike-card" key={s.group}>
                      <div className="spike-head">
                        <div className="spike-name">{s.group}</div>
                        <div className="spike-change">{formatChange(s.change_pct)}</div>
                      </div>
                      <div className="spike-meta">
                        <strong>{s.current.toLocaleString()}</strong> complaints in last {data.window_days}d (Historical avg: {Math.round(s.baseline_avg).toLocaleString()})
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {others.length > 0 && (
                <div className="trend-section">
                  <h3 className="trend-heading">Top Baseline Categories</h3>
                  <div className="table-wrap modern-table-wrap">
                    <table className="modern-table">
                      <thead>
                        <tr>
                          <th>{GROUPS.find((g) => g.value === groupBy).label}</th>
                          <th>Last {data.window_days} Days</th>
                          <th>Baseline Avg</th>
                          <th>Volume Shift</th>
                        </tr>
                      </thead>
                      <tbody>
                        {others.map((o) => (
                          <tr key={o.group}>
                            <td><strong>{o.group}</strong></td>
                            <td>{o.current.toLocaleString()}</td>
                            <td>{Math.round(o.baseline_avg).toLocaleString()}</td>
                            <td>{formatChange(o.change_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default Trends;
