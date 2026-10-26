import { useEffect, useState, useRef } from "react";
import {
  clearToken,
  getComplaints,
  getMe,
  getMyRoleUpgradeStatus,
  getProducts,
  getToken,
  requestRoleUpgrade,
  setUnauthorizedHandler,
} from "./api";
import AskRules from "./AskRules";
import ComplaintDetail from "./ComplaintDetail";
import Login from "./Login";
import Trends from "./Trends";
import UserManagement from "./UserManagement";
import {
  IconComplaints,
  IconLogout,
  IconRules,
  IconSearch,
  IconShield,
  IconTrends,
  IconUsers,
} from "./Icons";

const EMPTY = { q: "", product: "", state: "", date_from: "", date_to: "" };
const SUPER_ADMIN_EMAIL = (import.meta.env.VITE_SUPER_ADMIN_EMAIL || "piyushagrawal300504@gmail.com").toLowerCase();

function isSuperAdminUser(email) {
  const em = (email || "").toLowerCase().trim();
  return em === "piyushagrawal300504@gmail.com" || (SUPER_ADMIN_EMAIL && em === SUPER_ADMIN_EMAIL);
}

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

  return (
    <>
      {/* Metrics Banner */}
      <div className="overview-cards">
        <div className="metric-card">
          <div className="metric-icon">
            <IconComplaints size={20} />
          </div>
          <div className="metric-info">
            <span className="metric-val">{data ? data.total.toLocaleString() : "..."}</span>
            <span className="metric-sub">Total Complaints Indexed</span>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">
            <IconRules size={20} />
          </div>
          <div className="metric-info">
            <span className="metric-val">Federal Regulations</span>
            <span className="metric-sub">Reg E, F, V, Z Multi-RAG</span>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">
            <IconShield size={20} />
          </div>
          <div className="metric-info">
            <span className="metric-val">AI Desk Ready</span>
            <span className="metric-sub">Groq Fast Inference Engine</span>
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <form className="filters" onSubmit={applyFilters}>
        <div className="search-box">
          <span className="search-icon">
            <IconSearch size={15} />
          </span>
          <input
            name="q"
            placeholder="Search keyword, issue, or bank..."
            value={draft.q}
            onChange={change}
          />
        </div>
        <select name="product" value={draft.product} onChange={change}>
          <option value="">All Products</option>
          {products.map((p) => (
            <option key={p.product} value={p.product}>
              {p.product} ({p.count})
            </option>
          ))}
        </select>
        <input
          name="state"
          placeholder="State (e.g. CA, NY)"
          maxLength={2}
          value={draft.state}
          onChange={change}
          style={{ width: "95px" }}
        />
        <input
          name="date_from"
          type="date"
          title="Received from"
          value={draft.date_from}
          onChange={change}
        />
        <input
          name="date_to"
          type="date"
          title="Received until"
          value={draft.date_to}
          onChange={change}
        />
        <button type="submit" className="primary-btn">
          Filter
        </button>
        {isFiltered && (
          <button type="button" className="secondary reset-btn" onClick={resetFilters}>
            ✕ Clear
          </button>
        )}
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
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", padding: "1rem 0", color: "#0284c7" }}>
          <div className="inline-spinner"></div>
          <span style={{ fontSize: "0.92rem", fontWeight: 500 }}>Loading complaint records from database...</span>
        </div>
      )}

      {!error && data && (
        <>
          <div className="table-header-meta">
            <span>Showing page {page} of {totalPages} ({data.total.toLocaleString()} total)</span>
            {isFiltered && <span className="filter-badge">Filtered</span>}
          </div>

          {data.items.length === 0 ? (
            <div className="table-wrap" style={{ padding: "2rem", textAlign: "center" }}>
              <p className="info">No complaints match your search criteria.</p>
              <button className="secondary" onClick={resetFilters}>
                Reset Search Filters
              </button>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Date</th>
                    <th>Product</th>
                    <th>Issue Description</th>
                    <th>Company</th>
                    <th>State</th>
                    <th>Response Status</th>
                    <th>Timely</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((c) => {
                    const prodCategory = getProductCategory(c.product);
                    const companyInitial = c.company ? c.company.trim().charAt(0).toUpperCase() : "B";
                    return (
                      <tr
                        key={c.complaint_id}
                        className="clickable"
                        onClick={() => setSelectedId(c.complaint_id)}
                      >
                        <td>
                          <span className="id-tag-modern">#{c.complaint_id}</span>
                        </td>
                        <td>
                          <span className="date-cell">{formatDate(c.date_received)}</span>
                        </td>
                        <td>
                          <span className={`product-pill-modern ${prodCategory.cls}`} title={c.product}>
                            {c.product}
                          </span>
                        </td>
                        <td>
                          <div className="issue-cell" title={c.issue}>
                            <span className="issue-title-modern">{c.issue}</span>
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
                        <td>
                          <span className="state-badge-modern">{c.state || "—"}</span>
                        </td>
                        <td>
                          {renderResponseBadge(c.company_response_to_consumer)}
                        </td>
                        <td>
                          <span className="timely-badge">
                            {c.timely_response === null ? (
                              "—"
                            ) : c.timely_response ? (
                              <span className="timely-pill timely-yes">✓ Yes</span>
                            ) : (
                              <span className="timely-pill timely-no">✗ No</span>
                            )}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="pagination">
            <button
              className="secondary"
              disabled={page <= 1 || loading}
              onClick={() => setPage(page - 1)}
            >
              ← Previous
            </button>
            <span className="page-indicator">
              Page {page} of {totalPages}
            </span>
            <button
              className="secondary"
              disabled={page >= totalPages || loading}
              onClick={() => setPage(page + 1)}
            >
              Next →
            </button>
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
  const [upgradeStatus, setUpgradeStatus] = useState(null);
  const [showUpgradeForm, setShowUpgradeForm] = useState(false);
  const [targetRole, setTargetRole] = useState("supervisor");
  const [upgradeReason, setUpgradeReason] = useState("");
  const [submittingUpgrade, setSubmittingUpgrade] = useState(false);
  const [upgradeMessage, setUpgradeMessage] = useState(null);
  const [upgradeError, setUpgradeError] = useState(null);
  const [livePromotionNotice, setLivePromotionNotice] = useState(null);
  const profileTimeoutRef = useRef(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    if (showProfileModal && user) {
      const isSuper = isSuperAdminUser(user.email);
      const role = isSuper ? "admin" : (user.role || "agent");
      if (!isSuper && role !== "admin") {
        getMyRoleUpgradeStatus()
          .then((res) => {
            setUpgradeStatus(res);
          })
          .catch(() => {});
      }
    }
  }, [showProfileModal, user]);

  const handleUpgradeSubmit = async (e) => {
    e.preventDefault();
    setSubmittingUpgrade(true);
    setUpgradeError(null);
    setUpgradeMessage(null);
    try {
      const res = await requestRoleUpgrade(targetRole, upgradeReason);
      setUpgradeMessage(res.message);
      setUpgradeStatus({
        has_pending: true,
        request: {
          to_role: targetRole,
          reason: upgradeReason,
        },
      });
      setShowUpgradeForm(false);
    } catch (err) {
      setUpgradeError(err.message || "Failed to submit role upgrade request.");
    } finally {
      setSubmittingUpgrade(false);
    }
  };

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

  // Background sync: polls every 10 seconds to auto-elevate user when admin approves promotion
  useEffect(() => {
    if (!user || isSuperAdminUser(user.email) || user.role === "admin") return;
    const interval = setInterval(() => {
      getMe()
        .then((freshUser) => {
          if (freshUser && freshUser.role && freshUser.role !== user.role) {
            setUser(freshUser);
            setLivePromotionNotice(`🎉 Congratulations! Your promotion to ${freshUser.role.toUpperCase()} was approved by Admin!`);
            getMyRoleUpgradeStatus().then(setUpgradeStatus).catch(() => {});
          }
        })
        .catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [user]);

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

  const isSuper = isSuperAdminUser(user.email);
  const effectiveRole = isSuper ? "admin" : (user.role || "agent");
  const canSeeTrends = isSuper || TREND_ROLES.includes(effectiveRole);
  const canManageUsers = isSuper || ADMIN_ROLES.includes(effectiveRole);
  const showTrends = canSeeTrends && view === "trends";

  return (
    <div className="container">
      {livePromotionNotice && (
        <div className="live-promotion-toast">
          <div className="live-toast-content">
            <span className="live-toast-icon">🎉</span>
            <span className="live-toast-text">{livePromotionNotice}</span>
          </div>
          <button className="live-toast-close" onClick={() => setLivePromotionNotice(null)}>✕</button>
        </div>
      )}
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
                <span className={`badge badge-${effectiveRole}`}>
                  {isSuper ? "👑 Super Admin" : effectiveRole}
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
                  <span className={`badge badge-${effectiveRole}`}>
                    {isSuper
                      ? "👑 Permanent Super Admin"
                      : effectiveRole.toUpperCase()}
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

            {/* Role Elevation Section (For Non-Admins) */}
            {!isSuper && effectiveRole !== "admin" && (
              <div className="role-upgrade-section">
                {upgradeMessage && (
                  <div className="upgrade-alert-success">{upgradeMessage}</div>
                )}

                {upgradeStatus?.has_pending ? (
                  <div className="upgrade-pending-card">
                    <div className="upgrade-pending-title">
                      <span>⏳</span>
                      <strong>Promotion Request Pending Admin Review</strong>
                    </div>
                    <div className="upgrade-pending-details">
                      <div>Requested Role: <strong>{upgradeStatus.request.to_role.toUpperCase()}</strong></div>
                      {upgradeStatus.request.reason && (
                        <div style={{ marginTop: "4px" }}>Reason: <em>"{upgradeStatus.request.reason}"</em></div>
                      )}
                    </div>
                    <p className="upgrade-pending-note">
                      Your permissions remain as <strong>{effectiveRole.toUpperCase()}</strong> until the Administrator approves your request.
                    </p>
                  </div>
                ) : (
                  <>
                    {!upgradeStatus?.has_pending && upgradeStatus?.request?.status === "approved" && (
                      <div className="upgrade-approved-card">
                        <div className="upgrade-approved-title">
                          <span>🎉</span>
                          <strong>Promotion Approved by Admin!</strong>
                        </div>
                        <div className="upgrade-approved-details">
                          Your request for <strong>{upgradeStatus.request.to_role.toUpperCase()}</strong> was approved. Your elevated permissions are active right now!
                        </div>
                      </div>
                    )}
                    {!upgradeStatus?.has_pending && upgradeStatus?.request?.status === "rejected" && (
                      <div className="upgrade-rejected-card">
                        <div className="upgrade-rejected-title">
                          <span>ℹ️</span>
                          <strong>Promotion Request Update</strong>
                        </div>
                        <div className="upgrade-rejected-details">
                          Your recent request for <strong>{upgradeStatus.request.to_role.toUpperCase()}</strong> was reviewed and declined by Admin. You may submit another request when ready.
                        </div>
                      </div>
                    )}
                    {!showUpgradeForm ? (
                      <div style={{ marginTop: "1rem" }}>
                        <button
                          type="button"
                          className="secondary upgrade-trigger-btn"
                          onClick={() => {
                            setShowUpgradeForm(true);
                            setTargetRole(effectiveRole === "supervisor" ? "admin" : "supervisor");
                            setUpgradeError(null);
                            setUpgradeMessage(null);
                          }}
                        >
                          <span>📢</span> Request Role Upgrade to {effectiveRole === "supervisor" ? "Admin" : "Supervisor / Admin"}
                        </button>
                      </div>
                    ) : (
                      <form className="upgrade-form-box" onSubmit={handleUpgradeSubmit}>
                        <h4 className="upgrade-form-title">Request Role Elevation</h4>
                        <div className="upgrade-form-field">
                          <label>Desired Role:</label>
                          <select
                            className="upgrade-select"
                            value={targetRole}
                            onChange={(e) => setTargetRole(e.target.value)}
                          >
                            {effectiveRole === "agent" && (
                              <option value="supervisor">Supervisor</option>
                            )}
                            <option value="admin">Administrator (Admin)</option>
                          </select>
                        </div>
                        <div className="upgrade-form-field">
                          <label>Reason / Department Justification:</label>
                          <textarea
                            className="upgrade-textarea"
                            rows={2}
                            placeholder="e.g. Transferred to senior escalation desk, need supervisory trends access..."
                            value={upgradeReason}
                            onChange={(e) => setUpgradeReason(e.target.value)}
                          />
                        </div>
                        {upgradeError && <div className="upgrade-alert-error">{upgradeError}</div>}
                        <div className="upgrade-form-actions">
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setShowUpgradeForm(false)}
                            disabled={submittingUpgrade}
                          >
                            Cancel
                          </button>
                          <button
                            type="submit"
                            className="primary-btn"
                            disabled={submittingUpgrade}
                          >
                            {submittingUpgrade ? "Submitting..." : "Submit to Admin"}
                          </button>
                        </div>
                      </form>
                    )}
                  </>
                )}
              </div>
            )}

            <div style={{ textAlign: "right", marginTop: "1.2rem" }}>
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
