import { useEffect, useState, useRef } from "react";
import {
  clearToken,
  getComplaints,
  getMe,
  getProducts,
  getToken,
  setUnauthorizedHandler,
} from "./api";
import AskRules from "./AskRules";
import ComplaintDetail from "./ComplaintDetail";
import Login from "./Login";
import Trends from "./Trends";
import UserManagement from "./UserManagement";
import {
  IconAlert,
  IconArrowRight,
  IconBuilding,
  IconCalendar,
  IconCheck,
  IconComplaints,
  IconFilter,
  IconLogout,
  IconRules,
  IconSearch,
  IconShield,
  IconSparkles,
  IconTrends,
  IconUsers,
} from "./Icons";

const EMPTY = { q: "", product: "", state: "", date_from: "", date_to: "" };
const PAGE_SIZE = 25;
const TREND_ROLES = ["supervisor", "admin"];
const ADMIN_ROLES = ["admin"];

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const parts = dateStr.split("-");
    if (parts.length !== 3) return dateStr;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const m = months[parseInt(parts[1], 10) - 1] || parts[1];
    return `${m} ${parseInt(parts[2], 10)}, ${parts[0]}`;
  } catch {
    return dateStr;
  }
}

function getProductCategory(product = "") {
  const p = product.toLowerCase();
  if (p.includes("credit card") || p.includes("prepaid")) return { cls: "prod-card", label: "Credit Card" };
  if (p.includes("mortgage")) return { cls: "prod-mortgage", label: "Mortgage" };
  if (p.includes("checking") || p.includes("savings") || p.includes("bank account")) return { cls: "prod-bank", label: "Banking" };
  if (p.includes("debt") || p.includes("collection")) return { cls: "prod-debt", label: "Debt Collection" };
  if (p.includes("credit report") || p.includes("repair")) return { cls: "prod-report", label: "Credit Report" };
  if (p.includes("loan") || p.includes("student") || p.includes("vehicle")) return { cls: "prod-loan", label: "Loan" };
  return { cls: "prod-other", label: "Finance" };
}

function renderResponseBadge(resp = "") {
  const r = (resp || "").toLowerCase();
  if (r.includes("monetary relief") && !r.includes("non-monetary")) {
    return <span className="response-pill resp-monetary">💰 Monetary Relief</span>;
  }
  if (r.includes("non-monetary")) {
    return <span className="response-pill resp-nonmonetary">⚖️ Non-monetary</span>;
  }
  if (r.includes("explanation")) {
    return <span className="response-pill resp-explanation">📄 Explanation</span>;
  }
  if (r.includes("progress")) {
    return <span className="response-pill resp-progress">⏳ In Progress</span>;
  }
  return <span className="response-pill resp-default">{resp || "Under Review"}</span>;
}

const QUICK_FILTERS = [
  { label: "All Complaints", product: "" },
  { label: "💳 Credit Cards", product: "Credit card or prepaid card" },
  { label: "🏠 Mortgages", product: "Mortgage" },
  { label: "🏦 Checking & Savings", product: "Checking or savings account" },
  { label: "📊 Debt Collection", product: "Debt collection" },
  { label: "📑 Credit Reporting", product: "Credit reporting, credit repair services, or other personal consumer reports" },
];

function ComplaintsPage({ currentUser }) {
  const [draft, setDraft] = useState(EMPTY);
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [products, setProducts] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    getProducts().then(setProducts).catch(() => setProducts([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getComplaints({ ...filters, page, page_size: PAGE_SIZE })
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
  }, [filters, page]);

  function change(e) {
    const { name, value } = e.target;
    setDraft((prev) => ({ ...prev, [name]: value }));
  }

  function applyFilters(e) {
    e.preventDefault();
    setPage(1);
    setFilters({ ...draft });
  }

  function resetFilters() {
    setDraft(EMPTY);
    setFilters(EMPTY);
    setPage(1);
  }

  const totalPages = data ? data.total_pages : 0;
  const isFiltered = Object.values(filters).some((v) => v !== "");
  const timelyCount = data && data.items ? data.items.filter((i) => i.timely_response).length : 0;
  const timelyRate = data && data.items && data.items.length > 0
    ? Math.round((timelyCount / data.items.length) * 100)
    : 98;

  return (
    <>
      {/* 4-Card Modern Fintech Overview Cards */}
      <div className="overview-cards">
        <div className="metric-card metric-card-total">
          <div className="metric-icon icon-blue">
            <IconComplaints size={22} />
          </div>
          <div className="metric-info">
            <div className="metric-header-row">
              <span className="metric-val">{data ? data.total.toLocaleString() : "..."}</span>
              <span className="metric-pill pill-blue">CFPB Live</span>
            </div>
            <span className="metric-sub">Federal Complaints Indexed</span>
          </div>
        </div>

        <div className="metric-card metric-card-sla">
          <div className="metric-icon icon-emerald">
            <IconCheck size={22} />
          </div>
          <div className="metric-info">
            <div className="metric-header-row">
              <span className="metric-val">{timelyRate}% Timely</span>
              <span className="metric-pill pill-emerald">SLA ≥ 95%</span>
            </div>
            <span className="metric-sub">Timely Response Performance</span>
          </div>
        </div>

        <div className="metric-card metric-card-rag">
          <div className="metric-icon icon-indigo">
            <IconRules size={22} />
          </div>
          <div className="metric-info">
            <div className="metric-header-row">
              <span className="metric-val">12 CFR Regulations</span>
            </div>
            <div className="metric-chips-row">
              <span className="reg-chip">Reg E</span>
              <span className="reg-chip">Reg F</span>
              <span className="reg-chip">Reg V</span>
              <span className="reg-chip">Reg Z</span>
            </div>
          </div>
        </div>

        <div className="metric-card metric-card-ai">
          <div className="metric-icon icon-violet">
            <IconSparkles size={22} />
          </div>
          <div className="metric-info">
            <div className="metric-header-row">
              <span className="metric-val">AI Resolution Desk</span>
              <span className="metric-pulse-badge">
                <span className="pulse-dot"></span> Online
              </span>
            </div>
            <span className="metric-sub">Groq LLaMA-3.3 Semantic RAG</span>
          </div>
        </div>
      </div>

      {/* Quick Category Chips */}
      <div className="quick-filter-bar">
        <span className="quick-filter-title">
          <IconFilter size={13} /> Quick Filters:
        </span>
        <div className="quick-filter-chips">
          {QUICK_FILTERS.map((qf) => {
            const isActive = (filters.product || "") === qf.product;
            return (
              <button
                key={qf.label}
                type="button"
                className={`quick-chip ${isActive ? "active" : ""}`}
                onClick={() => {
                  setDraft((prev) => ({ ...prev, product: qf.product }));
                  setFilters((prev) => ({ ...prev, product: qf.product }));
                  setPage(1);
                }}
              >
                {qf.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Modern Filter Toolbar */}
      <form className="filters modern-filters" onSubmit={applyFilters}>
        <div className="search-box modern-search">
          <span className="search-icon">
            <IconSearch size={16} />
          </span>
          <input
            name="q"
            placeholder="Search keyword, issue, bank name, or complaint story..."
            value={draft.q}
            onChange={change}
          />
          {draft.q && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={() => {
                setDraft((prev) => ({ ...prev, q: "" }));
                setFilters((prev) => ({ ...prev, q: "" }));
                setPage(1);
              }}
              title="Clear search query"
            >
              ✕
            </button>
          )}
        </div>

        <div className="filter-controls-group">
          <select name="product" value={draft.product} onChange={change} className="filter-select">
            <option value="">All Products ({products.length})</option>
            {products.map((p) => (
              <option key={p.product} value={p.product}>
                {p.product} ({p.count})
              </option>
            ))}
          </select>

          <input
            name="state"
            placeholder="State (CA, NY...)"
            maxLength={2}
            value={draft.state}
            onChange={change}
            className="state-code-input"
            autoCapitalize="characters"
          />

          <div className="date-filter-box" title="Received from date">
            <span className="date-filter-label">From:</span>
            <input
              name="date_from"
              type="date"
              value={draft.date_from}
              onChange={change}
            />
          </div>

          <div className="date-filter-box" title="Received until date">
            <span className="date-filter-label">To:</span>
            <input
              name="date_to"
              type="date"
              value={draft.date_to}
              onChange={change}
            />
          </div>

          <button type="submit" className="primary-btn apply-filter-btn">
            Filter
          </button>

          {isFiltered && (
            <button type="button" className="secondary reset-btn" onClick={resetFilters}>
              ✕ Clear All
            </button>
          )}
        </div>
      </form>

      {/* Selected Complaint Detail Drawer */}
      {selectedId && (
        <ComplaintDetail
          key={selectedId}
          id={selectedId}
          currentUser={currentUser}
          onClose={() => setSelectedId(null)}
        />
      )}

      {error && <div className="error">Could not load complaints: {error}</div>}
      {loading && (
        <div className="loading-state-banner">
          <div className="inline-spinner"></div>
          <span>Loading complaint records from secure database...</span>
        </div>
      )}

      {!error && data && (
        <>
          <div className="table-header-meta">
            <div className="meta-left">
              <span className="meta-results-count">
                Showing <strong>{((page - 1) * PAGE_SIZE) + 1}</strong>–<strong>{Math.min(page * PAGE_SIZE, data.total)}</strong> of <strong>{data.total.toLocaleString()}</strong> complaints
              </span>
              {isFiltered && <span className="filter-badge">Active Filters Applied</span>}
            </div>
            <div className="meta-right">
              <span className="meta-page-badge">Page {page} of {totalPages}</span>
            </div>
          </div>

          {data.items.length === 0 ? (
            <div className="empty-table-state">
              <div className="empty-state-icon">🔍</div>
              <h3>No complaints found</h3>
              <p>No records matched your specific search filters. Try loosening your search terms or clearing filters.</p>
              <button className="primary-btn" onClick={resetFilters}>
                Reset Search Filters
              </button>
            </div>
          ) : (
            <div className="table-wrap modern-table-wrap">
              <table className="modern-table">
                <thead>
                  <tr>
                    <th style={{ width: "120px" }}>Case ID</th>
                    <th style={{ width: "125px" }}>Date</th>
                    <th style={{ width: "175px" }}>Product Category</th>
                    <th>Issue Description</th>
                    <th style={{ width: "170px" }}>Institution</th>
                    <th style={{ width: "65px", textAlign: "center" }}>State</th>
                    <th style={{ width: "175px" }}>Resolution</th>
                    <th style={{ width: "95px", textAlign: "center" }}>Timely</th>
                    <th style={{ width: "105px", textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((c) => {
                    const prodCategory = getProductCategory(c.product);
                    const companyInitial = c.company ? c.company.trim().charAt(0).toUpperCase() : "B";
                    return (
                      <tr
                        key={c.complaint_id}
                        className="clickable modern-case-row"
                        onClick={() => setSelectedId(c.complaint_id)}
                      >
                        <td>
                          <span className="id-tag-modern">#{c.complaint_id}</span>
                        </td>
                        <td>
                          <span className="date-cell-modern">{formatDate(c.date_received)}</span>
                        </td>
                        <td>
                          <span className={`product-pill-modern ${prodCategory.cls}`} title={c.product}>
                            {c.product}
                          </span>
                        </td>
                        <td>
                          <div className="issue-cell-wrap">
                            <span className="issue-title-modern" title={c.issue}>
                              {c.issue}
                            </span>
                            {c.sub_issue && (
                              <span className="sub-issue-tag" title={c.sub_issue}>
                                {c.sub_issue}
                              </span>
                            )}
                          </div>
                        </td>
                        <td>
                          <div className="company-cell-modern">
                            <span className="company-avatar-circle">{companyInitial}</span>
                            <span className="company-name-text" title={c.company}>
                              {c.company}
                            </span>
                          </div>
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <span className="state-badge-modern">{c.state || "—"}</span>
                        </td>
                        <td>
                          {renderResponseBadge(c.company_response_to_consumer)}
                        </td>
                        <td style={{ textAlign: "center" }}>
                          {c.timely_response === null ? (
                            <span className="timely-pill timely-na">—</span>
                          ) : c.timely_response ? (
                            <span className="timely-pill timely-yes">✓ Timely</span>
                          ) : (
                            <span className="timely-pill timely-no">✕ Delayed</span>
                          )}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <span className="row-action-pill">
                            Open <IconArrowRight size={12} />
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Modern Responsive Pagination */}
          <div className="modern-pagination">
            <div className="pagination-text">
              Page <strong>{page}</strong> of <strong>{totalPages}</strong>
            </div>
            <div className="pagination-btns">
              <button
                className="secondary pagination-btn"
                disabled={page <= 1 || loading}
                onClick={() => setPage(page - 1)}
              >
                ← Previous
              </button>
              
              <div className="page-numbers-list">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pNum;
                  if (totalPages <= 5) {
                    pNum = i + 1;
                  } else if (page <= 3) {
                    pNum = i + 1;
                  } else if (page >= totalPages - 2) {
                    pNum = totalPages - 4 + i;
                  } else {
                    pNum = page - 2 + i;
                  }
                  return (
                    <button
                      key={pNum}
                      type="button"
                      className={`page-number-btn ${page === pNum ? "active" : ""}`}
                      onClick={() => setPage(pNum)}
                    >
                      {pNum}
                    </button>
                  );
                })}
              </div>

              <button
                className="secondary pagination-btn"
                disabled={page >= totalPages || loading}
                onClick={() => setPage(page + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("complaints");
  const [checking, setChecking] = useState(Boolean(getToken()));
  const [profileOpen, setProfileOpen] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const profileTimeoutRef = useRef(null);
  const dropdownRef = useRef(null);

  const handleProfileEnter = () => {
    if (profileTimeoutRef.current) clearTimeout(profileTimeoutRef.current);
    setProfileOpen(true);
  };

  const handleProfileLeave = () => {
    profileTimeoutRef.current = setTimeout(() => {
      setProfileOpen(false);
    }, 280);
  };

  const handleTriggerClick = (e) => {
    e.stopPropagation();
    if (profileTimeoutRef.current) clearTimeout(profileTimeoutRef.current);
    setProfileOpen((prev) => !prev);
  };

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setProfileOpen(false);
      }
    }
    window.addEventListener("click", handleClickOutside);
    return () => {
      window.removeEventListener("click", handleClickOutside);
      if (profileTimeoutRef.current) clearTimeout(profileTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape") {
        setShowProfileModal(false);
        setProfileOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearToken();
      setUser(null);
    });
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    getMe()
      .then(setUser)
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);

  function handleLogout() {
    clearToken();
    setUser(null);
    setView("complaints");
  }

  if (checking) {
    return (
      <div className="container" style={{ padding: "5rem 2rem", textAlign: "center" }}>
        <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
          <div className="app-init-spinner"></div>
          <p style={{ color: "#334155", fontWeight: 500, margin: 0, fontSize: "1.05rem" }}>
            Initializing Bank Complaint AI Desk...
          </p>
          <span style={{ fontSize: "0.84rem", color: "#64748b" }}>
            Connecting to regulatory compliance intelligence service
          </span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Login onLoggedIn={setUser} />;
  }

  const canSeeTrends = TREND_ROLES.includes(user.role);
  const canManageUsers = ADMIN_ROLES.includes(user.role);
  const showTrends = canSeeTrends && view === "trends";

  return (
    <div className="container">
      <header className="topbar">
        <div className="brand-group">
          <div className="logo-shield">
            <IconShield size={22} />
          </div>
          <div>
            <h1>Bank Complaint AI Desk</h1>
            <p className="tagline">Intelligent Complaint Resolution & Regulatory Compliance</p>
          </div>
        </div>

        <div className="userbox">
          <div
            ref={dropdownRef}
            className="user-dropdown-wrapper"
            onMouseEnter={handleProfileEnter}
            onMouseLeave={handleProfileLeave}
          >
            <div
              className={`user-profile-trigger ${profileOpen ? "open" : ""}`}
              onClick={handleTriggerClick}
            >
              <span className="user-avatar">
                {user.full_name ? user.full_name[0].toUpperCase() : "U"}
              </span>
              <div className="user-details">
                <span className="user-name">{user.full_name || user.email}</span>
                <span className={`badge badge-${user.role}`}>
                  {user.email.toLowerCase() === "piyushagrawal300504@gmail.com"
                    ? "👑 Super Admin"
                    : user.role}
                </span>
              </div>
              <span className="dropdown-caret">▾</span>
            </div>

            {profileOpen && (
              <div className="profile-menu-dropdown">
                <div className="dropdown-user-header">
                  <span className="dropdown-avatar-large">
                    {user.full_name ? user.full_name[0].toUpperCase() : "U"}
                  </span>
                  <div className="dropdown-user-info">
                    <span className="dropdown-name">{user.full_name || "Bank Officer"}</span>
                    <span className="dropdown-email">{user.email}</span>
                    <span className="dropdown-session-badge">
                      <span className="active-dot"></span> Active Session
                    </span>
                  </div>
                </div>

                <div className="dropdown-divider"></div>

                <div className="dropdown-actions-list">
                  <button
                    type="button"
                    className="dropdown-menu-item"
                    onClick={() => {
                      if (profileTimeoutRef.current) clearTimeout(profileTimeoutRef.current);
                      setProfileOpen(false);
                      setShowProfileModal(true);
                    }}
                  >
                    <span className="menu-item-icon">👤</span>
                    <span>My Profile & Details</span>
                  </button>

                  {canManageUsers && (
                    <button
                      type="button"
                      className="dropdown-menu-item"
                      onClick={() => {
                        if (profileTimeoutRef.current) clearTimeout(profileTimeoutRef.current);
                        setProfileOpen(false);
                        setView("users");
                      }}
                    >
                      <span className="menu-item-icon">👥</span>
                      <span>User Management Portal</span>
                    </button>
                  )}

                  <div className="dropdown-divider"></div>

                  <button
                    type="button"
                    className="dropdown-menu-item logout-item"
                    onClick={() => {
                      if (profileTimeoutRef.current) clearTimeout(profileTimeoutRef.current);
                      setProfileOpen(false);
                      handleLogout();
                    }}
                  >
                    <IconLogout size={15} />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <nav className="tabs">
        <button
          className={"tab" + (view === "complaints" ? " active" : "")}
          onClick={() => setView("complaints")}
        >
          <IconComplaints size={16} /> Complaints
        </button>
        <button
          className={"tab" + (view === "rules" ? " active" : "")}
          onClick={() => setView("rules")}
        >
          <IconRules size={16} /> Ask Rules
        </button>
        {canSeeTrends && (
          <button
            className={"tab" + (showTrends ? " active" : "")}
            onClick={() => setView("trends")}
          >
            <IconTrends size={16} /> Operational Trends
          </button>
        )}
        {canManageUsers && (
          <button
            className={"tab" + (view === "users" ? " active" : "")}
            onClick={() => setView("users")}
          >
            <IconUsers size={16} /> User Management
          </button>
        )}
      </nav>

      <main className="main-content">
        {view === "rules" ? (
          <AskRules />
        ) : showTrends ? (
          <Trends />
        ) : view === "users" && canManageUsers ? (
          <UserManagement currentUser={user} />
        ) : (
          <ComplaintsPage currentUser={user} />
        )}
      </main>

      {/* User Profile Details Modal */}
      {showProfileModal && (
        <div
          className="profile-modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowProfileModal(false);
          }}
        >
          <div className="profile-modal-card">
            <div className="profile-modal-head">
              <h3>User Profile & Account Info</h3>
              <button
                type="button"
                className="secondary"
                onClick={() => setShowProfileModal(false)}
              >
                ✕ Close
              </button>
            </div>

            <div className="profile-info-grid">
              <div className="profile-row">
                <span className="profile-lbl">Account Name:</span>
                <span className="profile-val">{user.full_name || "Bank Desk Officer"}</span>
              </div>
              <div className="profile-row">
                <span className="profile-lbl">Email Address:</span>
                <span className="profile-val">{user.email}</span>
              </div>
              <div className="profile-row">
                <span className="profile-lbl">System Role:</span>
                <span className="profile-val">
                  <span className={`badge badge-${user.role}`}>
                    {user.email.toLowerCase() === "piyushagrawal300504@gmail.com"
                      ? "👑 Permanent Super Admin"
                      : user.role.toUpperCase()}
                  </span>
                </span>
              </div>
              <div className="profile-row">
                <span className="profile-lbl">Account Status:</span>
                <span className="profile-val" style={{ color: "#16a34a" }}>
                  ● Active & Verified
                </span>
              </div>
            </div>

            <div style={{ textAlign: "right" }}>
              <button
                type="button"
                className="primary-btn"
                onClick={() => setShowProfileModal(false)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
