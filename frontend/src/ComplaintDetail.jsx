import { useEffect, useState } from "react";
import {
  analyzeComplaint,
  approveComplaintResponse,
  draftReply,
  getComplaint,
  getSimilarComplaints,
  requestComplaintApproval,
  updateComplaintEmail,
} from "./api";
import {
  IconAlert,
  IconBuilding,
  IconCalendar,
  IconCheck,
  IconEdit,
  IconMail,
  IconSearch,
  IconSparkles,
} from "./Icons";
import "./ComplaintDetail.css";

function ComplaintDetail({ id, currentUser, onClose }) {
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Consumer Email edit state
  const [isEditingEmail, setIsEditingEmail] = useState(false);
  const [emailInput, setEmailInput] = useState("");
  const [updatingEmail, setUpdatingEmail] = useState(false);

  // AI Classification
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  // Similar Complaints
  const [similarCases, setSimilarCases] = useState([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);
  const [hasSearchedSimilar, setHasSearchedSimilar] = useState(false);

  // AI Draft Reply & Approval Workflow
  const [replyDraft, setReplyDraft] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [responseRecord, setResponseRecord] = useState(null);
  const [approving, setApproving] = useState(false);
  const [approvalFeedback, setApprovalFeedback] = useState(null);
  const [copied, setCopied] = useState(false);

  const isAgent = (currentUser?.role || "agent") === "agent";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setReplyDraft("");
    setResponseRecord(null);
    setApprovalFeedback(null);
    setIsEditingEmail(false);

    getComplaint(id)
      .then((result) => {
        if (cancelled) return;
        setComplaint(result);
        setEmailInput(result.consumer_email || "");
        setAnalysis(null);
        if (result.response) {
          setReplyDraft(result.response.response_text);
          setResponseRecord(result.response);
        }
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
  }, [id]);

  async function handleSaveEmail() {
    if (!emailInput || !emailInput.includes("@")) {
      alert("Please enter a valid email address.");
      return;
    }
    setUpdatingEmail(true);
    try {
      const res = await updateComplaintEmail(id, emailInput.trim());
      setComplaint((prev) => ({ ...prev, consumer_email: res.consumer_email }));
      setIsEditingEmail(false);
    } catch (err) {
      alert("Failed to update email: " + err.message);
    } finally {
      setUpdatingEmail(false);
    }
  }

  async function runAnalysis(refresh = false) {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const data = await analyzeComplaint(id, refresh);
      setAnalysis(data);
    } catch (err) {
      setAnalyzeError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  async function loadSimilarCases() {
    setLoadingSimilar(true);
    setHasSearchedSimilar(true);
    try {
      const res = await getSimilarComplaints(id);
      setSimilarCases(res.similar || []);
    } catch (err) {
      console.error(err);
      setSimilarCases([]);
    } finally {
      setLoadingSimilar(false);
    }
  }

  async function generateDraft() {
    setDrafting(true);
    setApprovalFeedback(null);
    try {
      const res = await draftReply(id);
      setReplyDraft(res.draft);
      setResponseRecord(null);
    } catch (err) {
      alert("Error generating reply draft: " + err.message);
    } finally {
      setDrafting(false);
    }
  }

  // Agent action: submit draft for supervisor approval
  async function handleRequestApproval() {
    if (!replyDraft || replyDraft.trim().length < 10) {
      alert("Cannot submit an empty draft response.");
      return;
    }
    setApproving(true);
    setApprovalFeedback(null);
    try {
      const record = await requestComplaintApproval(id, replyDraft);
      setResponseRecord(record);
      setApprovalFeedback({
        type: "success",
        message: "Draft successfully submitted for supervisor approval.",
      });
    } catch (err) {
      alert("Failed to submit draft: " + err.message);
    } finally {
      setApproving(false);
    }
  }

  // Supervisor / Admin action: approve response and trigger consumer email
  async function handleApprove() {
    if (!replyDraft || replyDraft.trim().length < 10) {
      alert("Cannot approve an empty response draft.");
      return;
    }
    setApproving(true);
    setApprovalFeedback(null);
    try {
      const record = await approveComplaintResponse(id, replyDraft);
      setResponseRecord(record);
      if (record.email_dispatched) {
        setApprovalFeedback({
          type: "success",
          message: `Official resolution approved! Notification email successfully dispatched to ${record.consumer_email}.`,
        });
      } else if (record.consumer_email) {
        setApprovalFeedback({
          type: "info",
          message: `Resolution approved. (Email delivery skipped or queued for ${record.consumer_email}).`,
        });
      } else {
        setApprovalFeedback({
          type: "info",
          message: "Resolution approved. (No consumer email on file for automated notification).",
        });
      }
    } catch (err) {
      alert("Failed to approve response: " + err.message);
    } finally {
      setApproving(false);
    }
  }

  function handleCopy() {
    if (!replyDraft) return;
    navigator.clipboard.writeText(replyDraft);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    if (!replyDraft) return;
    const blob = new Blob([replyDraft], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `Complaint_${id}_Official_Response.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  const isApproved = responseRecord?.status === "approved" || responseRecord?.status === "dispatched";
  const isPending = responseRecord?.status === "pending_approval";
  const isRejected = responseRecord?.status === "rejected";

  const approverRole = (responseRecord?.approved_by_role || "Supervisor").toUpperCase();
  const approverName = responseRecord?.approved_by_name || "Compliance Officer";

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="detail-modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="detail-modal-container">
        <div className="detail-card">
          <div className="detail-head">
            <div className="detail-title-group">
              <span className="case-id-tag">Case Record</span>
              <h2>Complaint #{id}</h2>
            </div>
            <button className="modal-close-btn" onClick={onClose} title="Close (Esc)">
              ✕ Close
            </button>
          </div>

          {loading && <p className="info">Loading complaint record...</p>}
          {error && <div className="error">Could not load complaint: {error}</div>}

          {complaint && (
            <div className="detail-body">
              {/* METADATA BAR WITH CONSUMER EMAIL */}
              <div className="detail-metadata">
                <span><strong>Product:</strong> {complaint.product}</span>
                <span><strong>Issue:</strong> {complaint.issue}</span>
                <span><strong>Company:</strong> {complaint.company}</span>
                <span><strong>Date:</strong> {complaint.date_received}</span>
                <span><strong>State:</strong> {complaint.state || "N/A"}</span>
                <span className="consumer-email-meta">
                  <strong>Consumer Email:</strong>{" "}
                  {isEditingEmail ? (
                    <span className="inline-email-editor">
                      <input
                        type="email"
                        value={emailInput}
                        placeholder="customer@example.com"
                        onChange={(e) => setEmailInput(e.target.value)}
                        className="email-inline-input"
                      />
                      <button
                        className="btn-save-email"
                        onClick={handleSaveEmail}
                        disabled={updatingEmail}
                      >
                        {updatingEmail ? "Saving..." : "Save"}
                      </button>
                      <button
                        className="btn-cancel-email"
                        onClick={() => setIsEditingEmail(false)}
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <span>
                      {complaint.consumer_email ? (
                        <span className="email-chip"><IconMail size={12} /> {complaint.consumer_email}</span>
                      ) : (
                        <span className="email-empty">(No email recorded)</span>
                      )}
                      <button
                        className="btn-edit-email-link"
                        onClick={() => {
                          setEmailInput(complaint.consumer_email || "");
                          setIsEditingEmail(true);
                        }}
                      >
                        {complaint.consumer_email ? "Edit" : "+ Add Email"}
                      </button>
                    </span>
                  )}
                </span>
              </div>

              {/* Customer Grievance Narrative */}
              <section className="section-block">
                <h3>Customer's Narrative</h3>
                <p className="narrative-box">
                  {complaint.narrative || "No customer written story provided for this record."}
                </p>
              </section>

              {/* AI Categorization & Summary */}
              <section className="section-block">
                <div className="section-head-row">
                  <h3>AI Categorization & Summary</h3>
                  {analysis && (
                    <button
                      className="refresh-ai-btn"
                      disabled={analyzing}
                      onClick={() => runAnalysis(true)}
                      title="Re-run AI analysis with fresh insights"
                    >
                      {analyzing ? "Re-analyzing..." : "↻ Refresh AI"}
                    </button>
                  )}
                </div>

                {analysis ? (
                  <div className="analysis-box">
                    <div className="analysis-badge-row">
                      <span className="badge category-badge">{analysis.category}</span>
                      <span className="analysis-basis">
                        {analysis.basis === "metadata"
                          ? "Based on product labels only"
                          : "Based on customer narrative"}
                      </span>
                    </div>
                    <p className="summary-text">{analysis.summary}</p>
                  </div>
                ) : (
                  <button
                    className="ai-trigger-btn"
                    disabled={analyzing}
                    onClick={() => runAnalysis(false)}
                  >
                    {analyzing ? "Analyzing with AI..." : (<><IconSparkles size={15} /> Analyze with AI</>)}
                  </button>
                )}
                {analyzeError && (
                  <div className="server-error-banner" style={{ margin: "0.8rem 0" }}>
                    <div className="server-error-left">
                      <span className="server-error-icon">⚠️</span>
                      <div>
                        <div className="server-error-title">AI Engine Unavailable</div>
                        <div className="server-error-msg">{analyzeError}</div>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-retry-modern"
                      onClick={() => runAnalysis(true)}
                    >
                      🔄 Retry
                    </button>
                  </div>
                )}
              </section>

              {/* Similar Past Complaints */}
              <section className="section-block">
                <div className="section-head-row">
                  <div>
                    <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700, color: "#0f172a" }}>
                      Similar Past Cases
                    </h3>
                    <p style={{ margin: "3px 0 0", fontSize: "0.82rem", color: "#64748b" }}>
                      Past resolved complaints matching this dispute pattern
                    </p>
                  </div>
                  <button
                    className="fetch-similar-btn"
                    disabled={loadingSimilar}
                    onClick={loadSimilarCases}
                  >
                    {loadingSimilar ? (
                      <>
                        <span className="inline-spinner" style={{ width: 13, height: 13, borderWidth: 2 }} />
                        <span>Searching Similar Cases...</span>
                      </>
                    ) : (
                      <>
                        <IconSearch size={14} />
                        <span>{similarCases.length > 0 ? "Refresh Similar Cases" : "Find Similar Cases"}</span>
                      </>
                    )}
                  </button>
                </div>

                {loadingSimilar ? (
                  <div className="similar-loading-state">
                    <span className="inline-spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                    <span>Finding similar resolved complaints...</span>
                  </div>
                ) : similarCases.length > 0 ? (
                  <div className="similar-grid">
                    {similarCases.map((c) => {
                      const matchPct = Math.round((c.similarity || 0.75) * 100);
                      const isHighMatch = matchPct >= 80;
                      return (
                        <div key={c.complaint_id} className="similar-card">
                          <div className="similar-card-top">
                            <span className="similar-case-id">Case #{c.complaint_id}</span>
                            <span className={`similar-match-pill ${isHighMatch ? "high-match" : "mid-match"}`}>
                              {matchPct}% Match
                            </span>
                          </div>

                          <div className="similar-card-sub">
                            <span className="similar-bank" title={c.company || "Bank"}>
                              <IconBuilding size={13} style={{ verticalAlign: "middle", marginRight: 3 }} />
                              {c.company || "Financial Institution"}
                            </span>
                            <span className="similar-date">
                              <IconCalendar size={13} style={{ verticalAlign: "middle", marginRight: 3 }} />
                              {c.date_received || "N/A"}
                            </span>
                          </div>

                          <div className="similar-issue-row">
                            <span className="similar-issue-label">Dispute Issue</span>
                            <p className="similar-issue-text">{c.issue}</p>
                          </div>

                          {c.narrative && (
                            <div className="similar-narrative-preview">
                              "{c.narrative.length > 140 ? c.narrative.slice(0, 140) + "..." : c.narrative}"
                            </div>
                          )}

                          {c.company_response_to_consumer && (
                            <div className="similar-resolution-box">
                              <span className="similar-res-label">Past Outcome</span>
                              <div className="similar-res-badge">
                                {c.company_response_to_consumer}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : hasSearchedSimilar ? (
                  <div className="similar-empty">
                    No historical precedent cases found matching this dispute.
                  </div>
                ) : null}
              </section>

              {/* AI Draft Reply & Human-in-the-Loop Approval */}
              <section className="section-block">
                <div className="section-head-row">
                  <h3>Official Bank Resolution Letter</h3>
                  <button className="draft-ai-btn" disabled={drafting} onClick={generateDraft}>
                    {drafting ? "Drafting with AI..." : replyDraft ? "Regenerate Draft" : "Draft Reply with AI"}
                  </button>
                </div>

                {approvalFeedback && (
                  <div className={`approval-feedback-banner ${approvalFeedback.type}`}>
                    {approvalFeedback.message}
                  </div>
                )}

                {isRejected && (
                  <div className="supervisor-rejection-banner">
                    <div className="rejection-banner-head">
                      <span className="rejection-icon"><IconAlert size={16} /></span>
                      <strong>Revisions Requested by {responseRecord?.rejected_by_name || "Supervisor"}</strong>
                      {responseRecord?.rejected_at && (
                        <span className="rejection-date">{new Date(responseRecord.rejected_at).toLocaleString()}</span>
                      )}
                    </div>
                    <div className="rejection-reason-quote">
                      "{responseRecord?.rejection_reason || "Revisions required."}"
                    </div>
                    <p className="rejection-instruction-note">
                      Please review the feedback above, edit the draft resolution letter below, and re-submit for approval.
                    </p>
                  </div>
                )}

                {replyDraft && (
                  <div className="reply-container">
                    <p className="reply-instruction">
                      {isAgent
                        ? "Review and customize the resolution letter before submitting it for supervisor/admin approval:"
                        : "Review, edit, and formally approve this resolution letter to notify the consumer:"}
                    </p>
                    <textarea
                      className="reply-textarea"
                      rows={9}
                      value={replyDraft}
                      onChange={(e) => {
                        setReplyDraft(e.target.value);
                        if (responseRecord) {
                          setResponseRecord(null);
                        }
                      }}
                    />

                    {/* STATUS AND ACTION BAR */}
                    <div className="reply-actions">
                      {isApproved ? (
                        <div className="approval-status-bar">
                          <span className="approved-badge">
                            <IconCheck size={15} /> Approved by {approverName} ({approverRole})
                          </span>
                          {complaint.consumer_email && (
                            <span className="email-sent-badge">
                              Notification sent to {complaint.consumer_email}
                            </span>
                          )}
                          <button className="secondary small-action-btn" onClick={handleCopy}>
                            {copied ? "✓ Copied!" : "Copy"}
                          </button>
                          <button className="secondary small-action-btn" onClick={handleDownload}>
                            Download .txt
                          </button>
                        </div>
                      ) : (
                        <div className="draft-action-group">
                          {isPending && (
                            <div className="pending-notice-box">
                              <span className="pending-badge">Pending Approval</span>
                              <span className="pending-text">
                                Submitted by {responseRecord?.requested_by_name || "Agent"} ({responseRecord?.requested_by_role || "agent"}).
                              </span>
                            </div>
                          )}

                          {isAgent ? (
                            <div className="agent-approval-controls">
                              <button
                                className="approve-btn request-btn"
                                disabled={approving}
                                onClick={handleRequestApproval}
                              >
                                {approving
                                  ? "Submitting..."
                                  : isRejected
                                  ? "Re-submit for Supervisor Approval"
                                  : isPending
                                  ? "Update & Resubmit Draft"
                                  : "Submit Draft for Supervisor Approval"}
                              </button>
                              <span className="agent-role-hint">
                                As an Agent, you submit drafts for supervisor sign-off.
                              </span>
                            </div>
                          ) : (
                            <div className="supervisor-approval-controls">
                              <button
                                className="approve-btn"
                                disabled={approving}
                                onClick={handleApprove}
                              >
                                {approving
                                  ? "Approving & Disagreeing/Emailing..."
                                  : "✓ Approve Response & Notify Consumer"}
                              </button>
                              <span className="approver-role-hint">
                                Approved responses automatically dispatch an official email notice to the consumer.
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ComplaintDetail;
