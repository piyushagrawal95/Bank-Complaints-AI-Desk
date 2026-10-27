import { useState, useEffect } from "react";
import { getPendingApprovals, approveComplaintResponse } from "./api";
import { IconCheck, IconShield, IconComplaints } from "./Icons";
import "./ApprovalsPortal.css";

export default function ApprovalsPortal({ onViewComplaint, onRefreshCount }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingList, setPendingList] = useState([]);
  const [approvingId, setApprovingId] = useState(null);
  const [actionNotice, setActionNotice] = useState(null);
  const [draftEdits, setDraftEdits] = useState({});

  async function loadPending() {
    setLoading(true);
    setError(null);
    try {
      const res = await getPendingApprovals();
      setPendingList(res.items || []);
      if (onRefreshCount) {
        onRefreshCount(res.count || 0);
      }
    } catch (err) {
      setError(err.message || "Failed to load pending approvals.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPending();
  }, []);

  function handleDraftChange(id, val) {
    setDraftEdits((prev) => ({ ...prev, [id]: val }));
  }

  async function handleApprove(complaint) {
    const id = complaint.complaint_id;
    const textToApprove = draftEdits[id] !== undefined ? draftEdits[id] : complaint.response_text;

    if (!textToApprove || textToApprove.trim().length < 10) {
      alert("Resolution letter cannot be empty (must be at least 10 characters).");
      return;
    }

    setApprovingId(id);
    setActionNotice(null);

    try {
      const res = await approveComplaintResponse(id, textToApprove);
      const emailNotice = res.email_dispatched && res.consumer_email
        ? ` Official resolution letter emailed to ${res.consumer_email}.`
        : res.consumer_email
        ? ` (Email delivery attempted to ${res.consumer_email}).`
        : " (No consumer email on file).";

      setActionNotice({
        type: "success",
        message: `Complaint #${id} approved successfully!${emailNotice}`,
      });

      // Remove from list immediately
      setPendingList((prev) => prev.filter((item) => item.complaint_id !== id));
      if (onRefreshCount) {
        onRefreshCount(Math.max(0, pendingList.length - 1));
      }
    } catch (err) {
      setActionNotice({
        type: "error",
        message: `Failed to approve Complaint #${id}: ${err.message}`,
      });
    } finally {
      setApprovingId(null);
    }
  }

  return (
    <div className="approvals-portal-wrapper">
      <div className="approvals-portal-header">
        <div className="title-row">
          <div className="icon-badge-approval">
            <IconShield size={24} />
          </div>
          <div>
            <h2>Supervisor Resolution Approvals</h2>
            <p className="subtitle">
              Review and formally approve resolution letters drafted by agents. Approving dispatches the official notice directly to the consumer's email address.
            </p>
          </div>
        </div>
        <button className="btn-refresh-approvals" onClick={loadPending} disabled={loading}>
          {loading ? "Checking..." : "Refresh Queue"}
        </button>
      </div>

      {actionNotice && (
        <div className={`approval-action-toast ${actionNotice.type}`}>
          <span className="toast-icon">{actionNotice.type === "success" ? "✓" : "✕"}</span>
          <span className="toast-msg">{actionNotice.message}</span>
          <button className="toast-dismiss" onClick={() => setActionNotice(null)}>✕</button>
        </div>
      )}

      {error && <div className="form-error-banner">{error}</div>}

      {loading ? (
        <div className="approvals-loading-box">
          <div className="app-init-spinner"></div>
          <p>Loading pending supervisor approval requests...</p>
        </div>
      ) : pendingList.length === 0 ? (
        <div className="approvals-empty-card">
          <div className="empty-icon-ring">
            <IconCheck size={36} />
          </div>
          <h3>Queue is Clean & Up to Date</h3>
          <p className="empty-sub">
            There are currently no agent resolution letters awaiting supervisor approval.
          </p>
          <button className="btn-secondary" onClick={loadPending}>
            Recheck Queue
          </button>
        </div>
      ) : (
        <div className="pending-cards-grid">
          <div className="pending-count-strip">
            <span><strong>{pendingList.length}</strong> dispute {pendingList.length === 1 ? "draft" : "drafts"} awaiting your sign-off</span>
          </div>

          {pendingList.map((item) => {
            const currentDraftText = draftEdits[item.complaint_id] !== undefined
              ? draftEdits[item.complaint_id]
              : item.response_text;

            return (
              <div key={item.complaint_id} className="approval-card">
                <div className="approval-card-topbar">
                  <div className="card-top-left">
                    <span className="complaint-id-tag">Complaint #{item.complaint_id}</span>
                    <span className="company-tag">{item.company}</span>
                    <span className="product-tag">{item.product}</span>
                  </div>
                  <div className="card-top-right">
                    <span className="status-badge-pending">Pending Approval</span>
                  </div>
                </div>

                <div className="approval-card-body">
                  <div className="issue-headline-row">
                    <h4>{item.issue}</h4>
                  </div>

                  <div className="approval-meta-row">
                    <div className="meta-col">
                      <span className="meta-lbl">Submitted By:</span>
                      <span className="meta-val">
                        Agent {item.requested_by_name || "Agent"} ({item.requested_by_role || "agent"})
                      </span>
                    </div>
                    {item.requested_at && (
                      <div className="meta-col">
                        <span className="meta-lbl">Requested At:</span>
                        <span className="meta-val">{new Date(item.requested_at).toLocaleString()}</span>
                      </div>
                    )}
                    <div className="meta-col">
                      <span className="meta-lbl">Consumer Email:</span>
                      <span className={`meta-val ${item.consumer_email ? "email-tag" : "no-email-tag"}`}>
                        {item.consumer_email || "No email on file (Letter only)"}
                      </span>
                    </div>
                  </div>

                  {/* Customer Grievance Narrative */}
                  <div className="narrative-preview-box">
                    <span className="box-title">Customer Dispute Narrative:</span>
                    <p className="narrative-content">{item.narrative || "No detailed narrative provided."}</p>
                  </div>

                  {/* Editable Resolution Letter */}
                  <div className="resolution-editor-box">
                    <div className="box-title-row">
                      <span className="box-title">Draft Bank Resolution Letter (Review & Edit):</span>
                      <span className="editor-hint">Edit directly before approving</span>
                    </div>
                    <textarea
                      className="resolution-textarea"
                      rows={8}
                      value={currentDraftText}
                      onChange={(e) => handleDraftChange(item.complaint_id, e.target.value)}
                    />
                  </div>

                  {/* Action Buttons */}
                  <div className="approval-card-actions">
                    <button
                      className="btn-approve-dispatch"
                      disabled={approvingId === item.complaint_id}
                      onClick={() => handleApprove(item)}
                    >
                      <IconCheck size={16} />
                      {approvingId === item.complaint_id
                        ? "Approving & Emailing..."
                        : item.consumer_email
                        ? "Approve & Email Customer"
                        : "Approve Resolution Letter"}
                    </button>
                    <button
                      className="btn-view-explorer"
                      onClick={() => onViewComplaint(item.complaint_id)}
                    >
                      <IconComplaints size={15} /> View Full Complaint
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
