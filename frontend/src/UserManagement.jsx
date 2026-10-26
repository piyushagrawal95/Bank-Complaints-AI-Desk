import { useEffect, useState } from "react";
import {
  approveRoleUpgrade,
  getPendingRoleUpgrades,
  getUsers,
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
  const [pendingUpgrades, setPendingUpgrades] = useState([]);
  const [processingUpgradeId, setProcessingUpgradeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  useEffect(() => {
    loadUsers();
  }, []);

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const [usersData, pendingData] = await Promise.all([
        getUsers(),
        getPendingRoleUpgrades().catch(() => []),
      ]);
      const normalized = (usersData || []).map((u) => {
        if (isSuperAdminUser(u.email)) {
          return { ...u, role: "admin", is_active: true };
        }
        return u;
      });
      setUsers(normalized);
      setPendingUpgrades(pendingData || []);
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
      setSuccessMsg(`Successfully updated role to ${newRole.toUpperCase()}!`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingId(null);
    }
  }

  const roleStats = {
    total: users.length,
    agents: users.filter((u) => u.role === "agent").length,
    supervisors: users.filter((u) => u.role === "supervisor").length,
    admins: users.filter((u) => u.role === "admin").length,
  };

  return (
    <div className="users-container">
      <div className="users-header">
        <div>
          <h2>User Role & Access Management</h2>
          <p className="users-subtitle">
            Admin Portal: Manage user permissions, assign operational roles, and enforce security policies.
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

      {successMsg && <div className="toast-success">{successMsg}</div>}
      {error && <div className="error">Error loading user directory: {error}</div>}

      {loading && <p className="info">Loading users...</p>}

      {!loading && (
        <div className="table-wrap users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email Address</th>
                <th>Current Role</th>
                <th>Status</th>
                <th>Change Role</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isCurrent = currentUser && currentUser.id === u.id;
                const userPendingReq = pendingUpgrades.find((r) => r.user_id === u.id);
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
