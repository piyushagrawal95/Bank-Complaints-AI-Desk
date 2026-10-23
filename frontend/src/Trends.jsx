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
  { value: 45, label: "45 Days (Full Cycle)" },
  { value: "custom", label: "Custom Days" },
];

const DATE_RANGE_SHORTCUTS = [
  { label: "Jan 1 – Jan 14, 2016 (Peak 2 Weeks)", from: "2016-01-01", to: "2016-01-14" },
  { label: "Dec 15, 2015 – Jan 14, 2016 (Last 30 Days)", from: "2015-12-15", to: "2016-01-14" },
  { label: "Dec 1 – Dec 31, 2015 (Full December)", from: "2015-12-01", to: "2015-12-31" },
  { label: "Dec 1, 2015 – Jan 14, 2016 (Full Dataset)", from: "2015-12-01", to: "2016-01-14" },
];

function formatChange(pct) {
  if (pct == null) {
    return "New";
  }
  return `${pct > 0 ? "+" : ""}${pct}%`;
}

function Trends() {
  const [groupBy, setGroupBy] = useState("product");
  const [timelineMode, setTimelineMode] = useState("presets"); // "presets" | "range"

  // Preset window mode states
  const [windowPreset, setWindowPreset] = useState(7);
  const [customDays, setCustomDays] = useState("21");
  const [asOfDate, setAsOfDate] = useState("");

  // Custom Date Range mode states (Start Date to End Date)
  const [dateFrom, setDateFrom] = useState("2016-01-01");
  const [dateTo, setDateTo] = useState("2016-01-14");

  // Advanced threshold states
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
      threshold,
      min_count: minCount,
    };

    if (timelineMode === "range") {
      if (dateFrom && dateTo) {
        if (dateFrom > dateTo) {
          setError("Start Date (From) must be before or equal to End Date (To).");
          setLoading(false);
          return;
        }
        params.date_from = dateFrom;
        params.date_to = dateTo;
      }
    } else {
      params.window_days = activeWindowDays;
      if (asOfDate) {
        params.as_of = asOfDate;
      }
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
  }, [groupBy, timelineMode, activeWindowDays, asOfDate, dateFrom, dateTo, threshold, minCount]);

  const spikes = data ? data.items.filter((i) => i.is_spike) : [];
  const others = data ? data.items.filter((i) => !i.is_spike).slice(0, 15) : [];

  return (
    <div className="trends-container">
      <div className="trends-header">
        <div>
          <h2>Operational Spikes &amp; Trend Analytics</h2>
          <p className="trends-subtitle">
            Supervisory Intelligence Portal: Monitor volume surges across custom date ranges, rolling windows, and historical comparative baselines.
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

      {/* Mode Switcher Tabs */}
      <div className="timeline-mode-switcher">
        <button
          type="button"
          className={`mode-tab ${timelineMode === "presets" ? "active" : ""}`}
          onClick={() => setTimelineMode("presets")}
        >
          ⚡ Rolling Days Window
        </button>
        <button
          type="button"
          className={`mode-tab ${timelineMode === "range" ? "active" : ""}`}
          onClick={() => setTimelineMode("range")}
        >
          📅 Custom Date Range (From – To)
        </button>
      </div>

      {/* Timeline Controls Panel */}
      <div className="timeline-panel">
        {timelineMode === "presets" ? (
          <div className="timeline-row">
            <div className="timeline-label-group">
              <span className="timeline-title">Observation Window:</span>
              <span className="timeline-subtext">Rolling timeframe analyzed against 4 historical baseline periods</span>
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
        ) : (
          <div className="date-range-builder">
            <div className="date-range-header">
              <span className="timeline-title">Specify Exact Date Range:</span>
              <span className="timeline-subtext">Dataset coverage: Dec 1, 2015 to Jan 14, 2016</span>
            </div>
            <div className="date-range-inputs">
              <div className="date-field-group">
                <label htmlFor="range-from">Start Date (From):</label>
                <input
                  id="range-from"
                  type="date"
                  min="2015-12-01"
                  max="2016-01-14"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="date-range-picker"
                />
              </div>

              <div className="date-range-arrow">➔</div>

              <div className="date-field-group">
                <label htmlFor="range-to">End Date (To):</label>
                <input
                  id="range-to"
                  type="date"
                  min="2015-12-01"
                  max="2016-01-14"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="date-range-picker"
                />
              </div>
            </div>

            {/* Quick shortcuts for convenient date selection */}
            <div className="date-shortcuts-bar">
              <span className="shortcuts-label">Quick Ranges:</span>
              {DATE_RANGE_SHORTCUTS.map((sc, i) => (
                <button
                  key={i}
                  type="button"
                  className={`shortcut-chip ${dateFrom === sc.from && dateTo === sc.to ? "active" : ""}`}
                  onClick={() => {
                    setDateFrom(sc.from);
                    setDateTo(sc.to);
                  }}
                >
                  {sc.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="timeline-secondary-row">
          {timelineMode === "presets" && (
            <div className="secondary-control-item">
              <label htmlFor="as-of-date">
                📅 End Date (As Of):
              </label>
              <div className="as-of-input-wrapper">
                <input
                  id="as-of-date"
                  type="date"
                  min="2015-12-01"
                  max="2016-01-14"
                  value={asOfDate}
                  onChange={(e) => setAsOfDate(e.target.value)}
                  className="date-picker-input"
                />
                {asOfDate && (
                  <button
                    type="button"
                    className="reset-date-btn"
                    onClick={() => setAsOfDate("")}
                    title="Reset to latest date (Jan 14, 2016)"
                  >
                    ✕ Latest
                  </button>
                )}
              </div>
            </div>
          )}

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
              <option value="10">≥ 10 complaints</option>
              <option value="25">≥ 25 complaints</option>
              <option value="50">≥ 50 complaints</option>
            </select>
          </div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <p className="info">Analyzing rolling historical baselines across chosen timeframe...</p>}

      {data && (
        <>
          {data.as_of === null ? (
            <p className="info">No complaint records found to calculate trends for this date range.</p>
          ) : (
            <>
              <div className="trend-summary-bar">
                <span>
                  Observation Range: <strong>{data.date_from}</strong> to <strong>{data.date_to}</strong> ({data.window_days} Days)
                </span>
                <span>
                  Comparison Baseline: <strong>4 Historical Periods ({data.window_days * 4} Days prior)</strong>
                </span>
                <span>
                  Alert Rule: <strong>≥ {data.threshold}x &amp; ≥ {data.min_count} complaints</strong>
                </span>
              </div>

              {!data.enough_history && (
                <div className="trend-warning">
                  <IconAlert size={15} /> Historical baseline prior to {data.date_from} has limited records; comparisons may be tentative.
                </div>
              )}

              {spikes.length > 0 ? (
                <div className="trend-banner trend-alert">
                  <IconAlert size={16} /> {spikes.length} High-Risk Volume Spike{spikes.length > 1 ? "s" : ""} Detected ({data.date_from} to {data.date_to})
                </div>
              ) : (
                <div className="trend-banner trend-ok">
                  <IconCheck size={16} /> Normal Operations: No volume surges exceeding ≥ {data.threshold}x baseline detected between {data.date_from} and {data.date_to}.
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
                        <strong>{s.current.toLocaleString()}</strong> complaints between {data.date_from} and {data.date_to} (Historical baseline avg: {Math.round(s.baseline_avg).toLocaleString()})
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {others.length > 0 && (
                <div className="trend-section">
                  <h3 className="trend-heading">Top Categories Volume ({data.date_from} to {data.date_to})</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>{GROUPS.find((g) => g.value === groupBy).label}</th>
                          <th>Selected Range Volume</th>
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
