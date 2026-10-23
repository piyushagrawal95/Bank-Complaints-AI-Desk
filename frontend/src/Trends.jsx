import { useEffect, useState } from "react";
import { getSpikes } from "./api";
import { IconAlert, IconCheck } from "./Icons";
import "./Trends.css";

const GROUPS = [
  { value: "product", label: "Product" },
  { value: "issue", label: "Issue" },
  { value: "company", label: "Company" },
];

const WINDOW_PRESETS = [
  { value: 7, label: "7 Days (1W)" },
  { value: 14, label: "14 Days (2W)" },
  { value: 30, label: "30 Days (1M)" },
  { value: 60, label: "60 Days (2M)" },
  { value: 90, label: "90 Days (Quarter)" },
  { value: "custom", label: "Custom" },
];

function formatChange(pct) {
  if (pct == null) {
    return "New";
  }
  return `${pct > 0 ? "+" : ""}${pct}%`;
}

function Trends() {
  const [groupBy, setGroupBy] = useState("product");
  const [windowPreset, setWindowPreset] = useState(7);
  const [customDays, setCustomDays] = useState("21");
  const [asOfDate, setAsOfDate] = useState("");
  const [threshold, setThreshold] = useState(1.5);
  const [minCount, setMinCount] = useState(10);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const activeWindowDays =
    windowPreset === "custom"
      ? Math.max(3, Math.min(180, parseInt(customDays, 10) || 7))
      : windowPreset;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const params = {
      group_by: groupBy,
      window_days: activeWindowDays,
      threshold,
      min_count: minCount,
    };
    if (asOfDate) {
      params.as_of = asOfDate;
    }

    getSpikes(params)
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
  }, [groupBy, activeWindowDays, threshold, minCount, asOfDate]);

  const spikes = data ? data.items.filter((i) => i.is_spike) : [];
  const others = data ? data.items.filter((i) => !i.is_spike).slice(0, 15) : [];

  return (
    <div className="trends-container">
      <div className="trends-header">
        <div>
          <h2>Operational Spikes & Trend Analytics</h2>
          <p className="trends-subtitle">
            Advanced Supervisory Portal: Customize observation timelines, historical as-of dates, and statistical thresholds to detect emerging complaint surges.
          </p>
        </div>
        <div className="trend-controls-group">
          <div className="control-item">
            <label htmlFor="group-by">Category:</label>
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
      </div>

      {/* Supervisory Timeline & Threshold Controls */}
      <div className="timeline-panel">
        <div className="timeline-row">
          <div className="timeline-label-group">
            <span className="timeline-title">Observation Window:</span>
            <span className="timeline-subtext">Rolling timeframe analyzed against historical baselines</span>
          </div>
          <div className="timeline-pills">
            {WINDOW_PRESETS.map((preset) => (
              <button
                key={preset.value}
                type="button"
                className={`timeline-pill ${windowPreset === preset.value ? "active" : ""}`}
                onClick={() => setWindowPreset(preset.value)}
              >
                {preset.label}
              </button>
            ))}
            {windowPreset === "custom" && (
              <div className="custom-days-wrapper">
                <input
                  type="number"
                  min="3"
                  max="180"
                  value={customDays}
                  onChange={(e) => setCustomDays(e.target.value)}
                  className="custom-days-input"
                  placeholder="Days"
                />
                <span className="custom-days-unit">days (3–180)</span>
              </div>
            )}
          </div>
        </div>

        <div className="timeline-secondary-row">
          <div className="secondary-control-item">
            <label htmlFor="as-of-date">
              📅 Reference Timeline (As Of):
            </label>
            <div className="as-of-input-wrapper">
              <input
                id="as-of-date"
                type="date"
                value={asOfDate}
                onChange={(e) => setAsOfDate(e.target.value)}
                className="date-picker-input"
              />
              {asOfDate && (
                <button
                  type="button"
                  className="reset-date-btn"
                  onClick={() => setAsOfDate("")}
                  title="Reset to latest live dataset date"
                >
                  ✕ Latest
                </button>
              )}
            </div>
          </div>

          <div className="secondary-control-item">
            <label htmlFor="spike-threshold">
              ⚡ Spike Threshold:
            </label>
            <select
              id="spike-threshold"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
            >
              <option value="1.25">High Sensitivity (≥ 1.25x)</option>
              <option value="1.5">Standard Alert (≥ 1.5x)</option>
              <option value="2.0">Critical Surges Only (≥ 2.0x)</option>
            </select>
          </div>

          <div className="secondary-control-item">
            <label htmlFor="min-count">
              🔢 Min Volume:
            </label>
            <select
              id="min-count"
              value={minCount}
              onChange={(e) => setMinCount(parseInt(e.target.value, 10))}
            >
              <option value="5">≥ 5 complaints</option>
              <option value="10">≥ 10 complaints (Recommended)</option>
              <option value="20">≥ 20 complaints</option>
              <option value="30">≥ 30 complaints</option>
            </select>
          </div>
        </div>
      </div>

      {error && <div className="error">Could not load trends: {error}</div>}
      {loading && <p className="info">Analyzing rolling historical baselines across custom timeline...</p>}

      {data && (
        <>
          {data.as_of === null ? (
            <p className="info">No complaint records found to calculate trends for this date/window.</p>
          ) : (
            <>
              <div className="trend-summary-bar">
                <span>Data As Of: <strong>{data.as_of}</strong> {asOfDate ? "(Custom Timeline)" : "(Latest)"}</span>
                <span>Active Window: <strong>Last {data.window_days} Days</strong></span>
                <span>Comparison Baseline: <strong>4 Historical Periods ({data.window_days * 4} Days prior)</strong></span>
                <span>Alert Rule: <strong>≥ {data.threshold}x &amp; ≥ {data.min_count} complaints</strong></span>
              </div>

              {!data.enough_history && (
                <div className="trend-warning">
                  <IconAlert size={15} /> The dataset has limited history prior to {data.as_of}; baseline comparisons may be tentative.
                </div>
              )}

              {spikes.length > 0 ? (
                <div className="trend-banner trend-alert">
                  <IconAlert size={16} /> {spikes.length} High-Risk Volume Spike{spikes.length > 1 ? "s" : ""} Detected across the selected {data.window_days}-day timeline
                </div>
              ) : (
                <div className="trend-banner trend-ok">
                  <IconCheck size={16} /> Normal Operations: No volume surges exceeding ≥ {data.threshold}x baseline detected in this {data.window_days}-day window.
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
                        <strong>{s.current.toLocaleString()}</strong> complaints in selected {data.window_days}-day window (Historical avg: {Math.round(s.baseline_avg).toLocaleString()})
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {others.length > 0 && (
                <div className="trend-section">
                  <h3 className="trend-heading">Top Baseline Categories ({data.window_days}-Day Volume)</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>{GROUPS.find((g) => g.value === groupBy).label}</th>
                          <th>Selected {data.window_days} Days</th>
                          <th>Baseline Avg</th>
                          <th>Volume Shift</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {others.map((o) => (
                          <tr key={o.group}>
                            <td><strong>{o.group}</strong></td>
                            <td>{o.current.toLocaleString()}</td>
                            <td>{Math.round(o.baseline_avg).toLocaleString()}</td>
                            <td>{formatChange(o.change_pct)}</td>
                            <td>
                              <span className="status-pill active-pill" style={{ background: "#f1f5f9", color: "#475569" }}>
                                Stable
                              </span>
                            </td>
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
