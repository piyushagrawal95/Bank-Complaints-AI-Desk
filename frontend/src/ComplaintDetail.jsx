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

  function handlePrintLetter() {
    if (!replyDraft) return;
    const printWindow = window.open("", "_blank", "width=850,height=900");
    if (!printWindow) {
      alert("Please allow popups to print the official resolution letter.");
      return;
    }
    const dateFormatted = new Date().toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    const institution = complaint?.company || "Financial Institution";
    const escapeHtml = (str) => (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Official Resolution Notice - Complaint #${id}</title>
  <style>
    @page { size: A4; margin: 18mm 20mm; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; color: #0f172a; margin: 0; padding: 32px; line-height: 1.6; }
    .header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #1e3a8a; padding-bottom: 18px; margin-bottom: 24px; }
    .brand-title { font-size: 22px; font-weight: 800; color: #1e3a8a; margin: 0; letter-spacing: -0.3px; }
    .brand-sub { font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 4px; }
    .badge-approved { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase; display: inline-block; }
    .meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 24px; font-size: 13px; }
    .meta-row { display: flex; justify-content: space-between; }
    .meta-label { color: #64748b; font-weight: 600; }
    .meta-val { color: #0f172a; font-weight: 600; }
    .section-title { font-size: 13.5px; font-weight: 700; color: #1e293b; text-transform: uppercase; letter-spacing: 0.6px; margin: 0 0 10px; }
    .letter-body { background: #ffffff; border-left: 3px solid #2563eb; padding: 16px 20px; font-size: 13.5px; line-height: 1.75; color: #1e293b; white-space: pre-wrap; margin-bottom: 32px; }
    .signature-row { display: flex; justify-content: space-between; margin-top: 40px; padding-top: 16px; }
    .sign-box { width: 220px; border-top: 1px solid #cbd5e1; padding-top: 6px; }
    .sign-name { font-weight: 700; font-size: 13px; color: #0f172a; }
    .sign-role { font-size: 11.5px; color: #64748b; }
    .legal-disclaimer { font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 36px; line-height: 1.5; }
    .no-print-bar { margin-bottom: 24px; display: flex; justify-content: flex-end; gap: 10px; }
    .btn-print { background: #1d4ed8; color: #ffffff; border: none; padding: 9px 18px; border-radius: 6px; font-weight: 600; font-size: 13px; cursor: pointer; }
    .btn-print:hover { background: #1e40af; }
    @media print {
      .no-print-bar { display: none !important; }
      body { padding: 0; }
    }
  </style>
</head>
<body>
  <div class="no-print-bar">
    <button class="btn-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
  </div>
  <div class="header">
    <div>
      <h1 class="brand-title">${escapeHtml(institution)}</h1>
      <div class="brand-sub">Consumer Dispute Resolution &bull; Regulatory Compliance Operations</div>
    </div>
    <div style="text-align: right;">
      <div class="badge-approved">&#10003; Formally Approved</div>
      <div style="font-size: 11px; color: #64748b; margin-top: 5px;">Date: ${dateFormatted}</div>
    </div>
  </div>

  <div class="meta-grid">
    <div class="meta-row"><span class="meta-label">Complaint Reference:</span> <span class="meta-val">#${id}</span></div>
    <div class="meta-row"><span class="meta-label">Product / Service:</span> <span class="meta-val">${escapeHtml(complaint?.product || "N/A")}</span></div>
    <div class="meta-row"><span class="meta-label">Dispute Issue:</span> <span class="meta-val">${escapeHtml(complaint?.issue || "N/A")}</span></div>
    <div class="meta-row"><span class="meta-label">Customer Delivery Email:</span> <span class="meta-val">${escapeHtml(complaint?.consumer_email || "Not specified")}</span></div>
  </div>

  <div class="section-title">Official Determination &amp; Resolution Statement:</div>
  <div class="letter-body">${escapeHtml(replyDraft)}</div>

  <div class="signature-row">
    <div class="sign-box">
      <div class="sign-name">${escapeHtml(approverName)}</div>
      <div class="sign-role">${escapeHtml(approverRole)} &bull; Regulatory Compliance</div>
    </div>
    <div class="sign-box" style="text-align: right;">
      <div class="sign-name">Bank Complaint AI Desk</div>
      <div class="sign-role">Official Audit Record &bull; Ref #${id}</div>
    </div>
  </div>

  <div class="legal-disclaimer">
    <strong>Regulatory Notice:</strong> This document constitutes the formal written determination issued pursuant to federal consumer financial protection statutes, including the Electronic Fund Transfer Act (Regulation E, 12 CFR Part 1005) and Truth in Lending Act (Regulation Z, 12 CFR Part 1026). Records of this investigation are retained for statutory examination by the Consumer Financial Protection Bureau (CFPB).
  </div>
</body>
</html>`;
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
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
                          <button className="primary small-action-btn" onClick={handlePrintLetter} title="Print formal letterhead resolution notice or save as PDF">
                            🖨️ Print / PDF Letter
                          </button>
                          <button className="secondary small-action-btn" onClick={handleDownload} title="Download raw plaintext response">
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
