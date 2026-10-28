import { useState, useEffect } from "react";
import { getPendingApprovals, approveComplaintResponse, rejectComplaintResponse } from "./api";
import { IconCheck, IconShield, IconComplaints } from "./Icons";
import "./ApprovalsPortal.css";

export default function ApprovalsPortal({ onViewComplaint, onRefreshCount }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingList, setPendingList] = useState([]);
  const [approvingId, setApprovingId] = useState(null);
  const [actionNotice, setActionNotice] = useState(null);
  const [draftEdits, setDraftEdits] = useState({});
  const [customerEmails, setCustomerEmails] = useState({});
  const [rejectingId, setRejectingId] = useState(null);
  const [rejectReasons, setRejectReasons] = useState({});
  const [rejectSubmittingId, setRejectSubmittingId] = useState(null);

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

  function handleEmailChange(id, val) {
    setCustomerEmails((prev) => ({ ...prev, [id]: val }));
  }

  function handleReasonChange(id, val) {
    setRejectReasons((prev) => ({ ...prev, [id]: val }));
  }

  async function handleApprove(complaint) {
    const id = complaint.complaint_id;
    const textToApprove = draftEdits[id] !== undefined ? draftEdits[id] : complaint.response_text;
    const emailToUse = customerEmails[id] !== undefined ? customerEmails[id] : (complaint.consumer_email || "");

    if (!textToApprove || textToApprove.trim().length < 10) {
      alert("Resolution letter cannot be empty (must be at least 10 characters).");
      return;
    }

    setApprovingId(id);
    setActionNotice(null);

    try {
      const res = await approveComplaintResponse(id, textToApprove, emailToUse.trim() || null);
      const emailNotice = res.email_dispatched && res.consumer_email
        ? ` Official resolution letter queued for dispatch to ${res.consumer_email}.`
        : res.consumer_email
        ? ` (Email delivery initiated for ${res.consumer_email}).`
        : " (Approved without email dispatch - no customer email specified).";

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

  async function handleConfirmReject(complaint) {
    const id = complaint.complaint_id;
    const reason = (rejectReasons[id] || "").trim();

    if (!reason || reason.length < 3) {
      alert("Please provide feedback/instructions for the agent explaining why this draft is being returned.");
      return;
    }

    setRejectSubmittingId(id);
    setActionNotice(null);

    try {
      await rejectComplaintResponse(id, reason);
      setActionNotice({
        type: "success",
        message: `Complaint #${id} draft rejected. Revision instructions dispatched to Agent ${complaint.requested_by_name || "Agent"}.`,
      });

      // Remove from list immediately
      setPendingList((prev) => prev.filter((item) => item.complaint_id !== id));
      setRejectingId(null);
      if (onRefreshCount) {
        onRefreshCount(Math.max(0, pendingList.length - 1));
      }
    } catch (err) {
      setActionNotice({
        type: "error",
        message: `Failed to reject Complaint #${id}: ${err.message}`,
      });
    } finally {
      setRejectSubmittingId(null);
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
              Review and formally sign off on agent-drafted resolution letters. Approving dispatches the official notice directly to the consumer's email address.
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
            There are currently no agent resolution letters awaiting supervisor approval in your queue.
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

            const currentEmail = customerEmails[item.complaint_id] !== undefined
              ? customerEmails[item.complaint_id]
              : (item.consumer_email || "");

            const isRejecting = rejectingId === item.complaint_id;

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
                    {item.assigned_to_name && (
                      <div className="meta-col">
                        <span className="meta-lbl">Assigned Supervisor:</span>
                        <span className="meta-val supervisor-badge">
                          {item.assigned_to_name}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Customer Grievance Narrative */}
                  <div className="narrative-preview-box">
                    <span className="box-title">Customer Dispute Narrative:</span>
                    <p className="narrative-content">{item.narrative || "No detailed narrative provided."}</p>
                  </div>

                  {/* Customer Notification Email - Auto populated or placeholder */}
                  <div className="delivery-email-box">
                    <div className="box-title-row">
                      <span className="box-title">Customer Delivery Email:</span>
                      <span className="editor-hint">
                        {item.consumer_email ? "Auto-populated from complaint (editable)" : "Enter email below to dispatch letter upon approval"}
                      </span>
                    </div>
                    <input
                      type="email"
                      className="delivery-email-input"
                      placeholder="Enter customer email address (e.g. customer@example.com)..."
                      value={currentEmail}
                      onChange={(e) => handleEmailChange(item.complaint_id, e.target.value)}
                    />
                    {!currentEmail && (
                      <span className="no-email-hint">
                        Notice: No customer email on file. You can enter an email address above to dispatch notice, or approve as letter-only.
                      </span>
                    )}
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

                  {/* Rejection Panel (Toggleable) */}
                  {isRejecting && (
                    <div className="rejection-panel">
                      <div className="rejection-panel-head">
                        <span className="rejection-panel-title">Rejection Reason & Revision Instructions for Agent:</span>
                        <span className="rejection-panel-sub">Agent will be notified and can edit & re-submit</span>
                      </div>
                      <textarea
                        className="rejection-reason-textarea"
                        rows={3}
                        placeholder="Explain what needs to be changed (e.g. missing provisional credit timeline under Regulation E, incorrect fee amount, etc.)..."
                        value={rejectReasons[item.complaint_id] || ""}
                        onChange={(e) => handleReasonChange(item.complaint_id, e.target.value)}
                      />
                      <div className="rejection-panel-actions">
                        <button
                          className="btn-cancel-rejection"
                          onClick={() => setRejectingId(null)}
                          disabled={rejectSubmittingId === item.complaint_id}
                        >
                          Cancel
                        </button>
                        <button
                          className="btn-confirm-rejection"
                          onClick={() => handleConfirmReject(item)}
                          disabled={rejectSubmittingId === item.complaint_id}
                        >
                          {rejectSubmittingId === item.complaint_id ? "Submitting Rejection..." : "Confirm & Send to Agent"}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="approval-card-actions">
                    <button
                      className="btn-approve-dispatch"
                      disabled={approvingId === item.complaint_id || isRejecting}
                      onClick={() => handleApprove(item)}
                    >
                      <IconCheck size={16} />
                      {approvingId === item.complaint_id
                        ? "Approving & Queuing Dispatch..."
                        : currentEmail
                        ? `Approve & Dispatch Email (${currentEmail})`
                        : "Approve Resolution Letter"}
                    </button>

                    {!isRejecting ? (
                      <button
                        className="btn-reject-trigger"
                        onClick={() => setRejectingId(item.complaint_id)}
                        disabled={approvingId === item.complaint_id}
                      >
                        ✕ Reject / Request Changes
                      </button>
                    ) : null}

                    <button
                      className="btn-view-explorer"
                      onClick={() => onViewComplaint(item.complaint_id)}
                    >
                      <IconComplaints size={15} /> View Full Case
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
