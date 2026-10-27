import { useEffect, useState } from "react";
import {
  approveRoleUpgrade,
  getPendingRoleUpgrades,
  getUsers,
  getSupervisors,
  assignAgentSupervisor,
  rejectRoleUpgrade,
  updateUserRole,
} from "./api";
import "./UserManagement.css";

const SUPER_ADMIN_EMAIL = (import.meta.env.VITE_SUPER_ADMIN_EMAIL || "piyushagrawal300504@gmail.com").toLowerCase();

function isSuperAdminUser(email) {
  const em = (email || "").toLowerCase().trim();
  return em === "piyushagrawal300504@gmail.com" || (SUPER_ADMIN_EMAIL && em === SUPER_ADMIN_EMAIL);
}

function UserManagement({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [supervisors, setSupervisors] = useState([]);
  const [pendingUpgrades, setPendingUpgrades] = useState([]);
  const [processingUpgradeId, setProcessingUpgradeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);
  const [assigningId, setAssigningId] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  useEffect(() => {
    loadUsers();
    // Poll pending upgrade requests every 5 seconds so new submissions appear in real-time
    const interval = setInterval(() => {
      getPendingRoleUpgrades()
        .then((data) => setPendingUpgrades(data || []))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const [usersData, pendingData, supData] = await Promise.all([
        getUsers(),
        getPendingRoleUpgrades().catch(() => []),
        getSupervisors().catch(() => []),
      ]);
      const normalized = (usersData || []).map((u) => {
        if (isSuperAdminUser(u.email)) {
          return { ...u, role: "admin", is_active: true };
        }
        return u;
      });
      setUsers(normalized);
      setPendingUpgrades(pendingData || []);
      setSupervisors(supData || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleApproveUpgrade(requestId, targetUserId, newRole) {
    setProcessingUpgradeId(requestId);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await approveRoleUpgrade(requestId);
      setSuccessMsg(res.message);
      setPendingUpgrades((prev) => prev.filter((r) => r.id !== requestId));
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUserId ? { ...u, role: newRole } : u))
      );
      // Reload supervisors in case someone was promoted to supervisor
      getSupervisors().then(setSupervisors).catch(() => {});
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      setError(err.message || "Failed to approve role upgrade.");
    } finally {
      setProcessingUpgradeId(null);
    }
  }

  async function handleRejectUpgrade(requestId) {
    setProcessingUpgradeId(requestId);
    setError(null);
    try {
      const res = await rejectRoleUpgrade(requestId);
      setSuccessMsg(res.message);
      setPendingUpgrades((prev) => prev.filter((r) => r.id !== requestId));
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message || "Failed to decline role upgrade.");
    } finally {
      setProcessingUpgradeId(null);
    }
  }

  async function handleRoleChange(userId, newRole) {
    setUpdatingId(userId);
    setSuccessMsg(null);
    setError(null);
    try {
      await updateUserRole(userId, newRole);
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      );
      setSuccessMsg(`User role successfully changed to ${newRole.toUpperCase()}`);
      getSupervisors().then(setSupervisors).catch(() => {});
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      setError(err.message || "Failed to change user role.");
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleAssignSupervisor(agentId, supervisorId) {
    setAssigningId(agentId);
    setError(null);
    setSuccessMsg(null);
    const supId = supervisorId ? parseInt(supervisorId, 10) : null;
    try {
      const res = await assignAgentSupervisor(agentId, supId);
      setSuccessMsg(res.message);
      setUsers((prev) =>
        prev.map((u) => {
          if (u.id === agentId) {
            const assignedSup = supervisors.find((s) => s.id === supId);
            return {
              ...u,
              supervisor_id: supId,
              supervisor_name: assignedSup ? assignedSup.full_name : null,
              supervisor_email: assignedSup ? assignedSup.email : null,
            };
          }
          return u;
        })
      );
      // Refresh supervisor capacities
      getSupervisors().then(setSupervisors).catch(() => {});
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      setError(err.message || "Failed to assign supervisor.");
    } finally {
      setAssigningId(null);
    }
  }

  const roleStats = users.reduce(
    (acc, u) => {
      acc.total += 1;
      if (u.role === "agent") acc.agents += 1;
      else if (u.role === "supervisor") acc.supervisors += 1;
      else if (u.role === "admin") acc.admins += 1;
      return acc;
    },
    { total: 0, agents: 0, supervisors: 0, admins: 0 }
  );

  return (
    <div className="users-container">
      <div className="users-header">
        <div>
          <h2>User Role & Access Management</h2>
          <p className="users-subtitle">
            Admin Portal: Manage user permissions, enforce max 50 agents per supervisor hierarchy, and review promotions.
          </p>
        </div>
        <button className="secondary refresh-btn" onClick={loadUsers} disabled={loading}>
          {loading ? "Refreshing..." : "↻ Refresh List"}
        </button>
      </div>

      {/* Pending Role Elevation Requests Banner */}
      {pendingUpgrades.length > 0 && (
        <div className="pending-upgrades-banner">
          <div className="pending-upgrades-head">
            <span className="pending-badge-icon">🔔</span>
            <h3>Pending Role Upgrade Requests ({pendingUpgrades.length})</h3>
          </div>
          <div className="pending-upgrades-list">
            {pendingUpgrades.map((req) => (
              <div key={req.id} className="pending-upgrade-card">
                <div className="upgrade-card-info">
                  <div className="upgrade-user-name">
                    <strong>{req.full_name || req.email}</strong> <span className="upgrade-user-email">({req.email})</span>
                  </div>
                  <div className="upgrade-role-flow">
                    <span className={`role-badge role-${req.from_role}`}>{req.from_role}</span>
                    <span className="flow-arrow">➔</span>
                    <span className={`role-badge role-${req.to_role}`} style={{ fontWeight: 700 }}>
                      {req.to_role.toUpperCase()}
                    </span>
                  </div>
                  {req.reason && (
                    <div className="upgrade-reason">
                      <em>Justification:</em> "{req.reason}"
                    </div>
                  )}
                </div>
                <div className="upgrade-card-actions">
                  <button
                    type="button"
                    className="approve-upgrade-btn"
                    disabled={processingUpgradeId === req.id}
                    onClick={() => handleApproveUpgrade(req.id, req.user_id, req.to_role)}
                  >
                    {processingUpgradeId === req.id ? "Approving..." : "✓ Approve Elevation"}
                  </button>
                  <button
                    type="button"
                    className="reject-upgrade-btn"
                    disabled={processingUpgradeId === req.id}
                    onClick={() => handleRejectUpgrade(req.id)}
                  >
                    ✕ Decline
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-num">{roleStats.total}</div>
          <div className="stat-label">Total Users</div>
        </div>
        <div className="stat-card stat-agent">
          <div className="stat-num">{roleStats.agents}</div>
          <div className="stat-label">Agents</div>
        </div>
        <div className="stat-card stat-supervisor">
          <div className="stat-num">{roleStats.supervisors}</div>
          <div className="stat-label">Supervisors</div>
        </div>
        <div className="stat-card stat-admin">
          <div className="stat-num">{roleStats.admins}</div>
          <div className="stat-label">System Admins</div>
        </div>
      </div>

      {/* SUPERVISOR CAPACITY OVERVIEW WIDGET */}
      {supervisors.length > 0 && (
        <div className="supervisor-capacity-section">
          <div className="capacity-section-head">
            <h3>Supervisor Team Capacity (Max 50 Agents per Supervisor)</h3>
            <span className="capacity-subtitle">
              Approval requests from agents are automatically routed to their assigned supervisor.
            </span>
          </div>
          <div className="supervisor-capacity-grid">
            {supervisors.map((s) => {
              const count = parseInt(s.assigned_agent_count || 0, 10);
              const pct = Math.min(100, Math.round((count / 50) * 100));
              const isFull = count >= 50;
              return (
                <div key={s.id} className={`sup-capacity-card ${isFull ? "sup-card-full" : ""}`}>
                  <div className="sup-card-head">
                    <span className="sup-name">{s.full_name || s.email}</span>
                    <span className={`sup-capacity-pill ${isFull ? "pill-full" : "pill-available"}`}>
                      {isFull ? "FULL (50/50)" : `${count} / 50 Agents`}
                    </span>
                  </div>
                  <div className="sup-progress-bar-bg">
                    <div
                      className={`sup-progress-bar-fill ${isFull ? "fill-full" : ""}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="sup-card-foot">
                    <span>{50 - count} seats available</span>
                    <span className="sup-email-small">{s.email}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {successMsg && <div className="toast-success">{successMsg}</div>}
      {error && <div className="error">Error: {error}</div>}

      {loading && <p className="info">Loading users...</p>}

      {!loading && (
        <div className="table-wrap users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email Address</th>
                <th>Current Role</th>
                <th>Assigned Supervisor</th>
                <th>Status</th>
                <th>Change Role</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isCurrent = currentUser && currentUser.id === u.id;
                const userPendingReq = pendingUpgrades.find((r) => r.user_id === u.id);
                const isAgent = u.role === "agent";
                const isSupervisor = u.role === "supervisor";

                return (
                  <tr key={u.id} className={isCurrent ? "current-user-row" : ""}>
                    <td>
                      <span className="user-name-cell">{u.full_name || "User"}</span>
                      {isCurrent && <span className="you-pill">You</span>}
                      {isSuperAdminUser(u.email) && (
                        <span className="root-admin-pill" title="System Founder & Permanent Root Administrator">
                          👑 Owner
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="email-cell">{u.email}</span>
                    </td>
                    <td>
                      <span className={`role-badge role-${u.role}`}>{u.role}</span>
                      {userPendingReq && (
                        <span className="pending-upgrade-indicator" title={`Requested elevation to ${userPendingReq.to_role.toUpperCase()}`}>
                          ⏳ Req: {userPendingReq.to_role.toUpperCase()}
                        </span>
                      )}
                    </td>

                    {/* ASSIGNED SUPERVISOR COLUMN */}
                    <td>
                      {isAgent ? (
                        <div className="supervisor-assign-wrapper">
                          <select
                            className="supervisor-select"
                            value={u.supervisor_id || ""}
                            disabled={assigningId === u.id}
                            onChange={(e) => handleAssignSupervisor(u.id, e.target.value)}
                          >
                            <option value="">(Unassigned / General Queue)</option>
                            {supervisors.map((s) => {
                              const count = parseInt(s.assigned_agent_count || 0, 10);
                              const isSelfAssigned = u.supervisor_id === s.id;
                              const isFull = count >= 50 && !isSelfAssigned;
                              return (
                                <option
                                  key={s.id}
                                  value={s.id}
                                  disabled={isFull}
                                >
                                  {s.full_name || s.email} ({count}/50){isFull ? " - FULL" : ""}
                                </option>
                              );
                            })}
                          </select>
                          {assigningId === u.id && <span className="updating-spinner">...</span>}
                        </div>
                      ) : isSupervisor ? (
                        <span className="supervisor-lead-tag">
                          Team Lead ({supervisors.find((s) => s.id === u.id)?.assigned_agent_count || 0}/50)
                        </span>
                      ) : (
                        <span className="admin-tag">-</span>
                      )}
                    </td>

                    <td>
                      <span className="status-pill active-pill">Active</span>
                    </td>

                    <td>
                      {isSuperAdminUser(u.email) ? (
                        <span className="super-admin-lock-tag" title="Root Super Admin (Role is permanently locked)">
                          🔒 Permanent Admin
                        </span>
                      ) : (
                        <div className="role-change-wrapper">
                          <select
                            className="role-select"
                            value={u.role}
                            disabled={updatingId === u.id}
                            onChange={(e) => handleRoleChange(u.id, e.target.value)}
                          >
                            <option value="agent">Agent</option>
                            <option value="supervisor">Supervisor</option>
                            <option value="admin">Admin</option>
                          </select>
                          {updatingId === u.id && <span className="updating-spinner">...</span>}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default UserManagement;
