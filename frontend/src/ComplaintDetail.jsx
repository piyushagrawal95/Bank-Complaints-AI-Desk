import { useEffect, useState } from "react";
import {
  analyzeComplaint,
  approveComplaintResponse,
  draftReply,
  getComplaint,
  getSimilarComplaints,
} from "./api";
import { IconCalendar, IconCheck, IconCopy, IconFileText, IconSparkles } from "./Icons";
import "./ComplaintDetail.css";

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

function renderResponseBadge(resp = "") {
  const r = (resp || "").toLowerCase();
  if (r.includes("monetary relief") && !r.includes("non-monetary")) {
    return <span className="response-pill resp-monetary">💰 Monetary Relief</span>;
  }
  if (r.includes("non-monetary")) {
    return <span className="response-pill resp-nonmonetary">⚖️ Non-monetary</span>;
  }
  if (r.includes("explanation")) {
    return <span className="response-pill resp-explanation">📄 Closed w/ Explanation</span>;
  }
  if (r.includes("progress")) {
    return <span className="response-pill resp-progress">⏳ In Progress</span>;
  }
  return <span className="response-pill resp-default">{resp || "Under Review"}</span>;
}

function ComplaintDetail({ id, currentUser, onClose }) {
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedId, setCopiedId] = useState(false);

  // AI Classification
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  // Similar Complaints
  const [similarCases, setSimilarCases] = useState([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);

  // AI Draft Reply & Human Approval Record
  const [replyDraft, setReplyDraft] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [responseRecord, setResponseRecord] = useState(null);
  const [approving, setApproving] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setReplyDraft("");
    setResponseRecord(null);

    getComplaint(id)
      .then((result) => {
        if (cancelled) return;
        setComplaint(result);
        // Do not pre-load analysis so each user sees "Analyze with AI" interactively on open
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
    try {
      const res = await getSimilarComplaints(id);
      setSimilarCases(res.similar || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSimilar(false);
    }
  }

  async function generateDraft() {
    setDrafting(true);
    try {
      const res = await draftReply(id);
      setReplyDraft(res.draft);
      setResponseRecord(null); // Newly drafted requires review & approval
    } catch (err) {
      alert("Error generating reply draft: " + err.message);
    } finally {
      setDrafting(false);
    }
  }

  async function handleApprove() {
    if (!replyDraft || replyDraft.trim().length < 10) {
      alert("Cannot approve an empty response draft.");
      return;
    }
    setApproving(true);
    try {
      const record = await approveComplaintResponse(id, replyDraft);
      setResponseRecord(record);
    } catch (err) {
      alert("Error approving response: " + err.message);
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

  const approverRole = (
    responseRecord?.approved_by_role ||
    currentUser?.role ||
    "agent"
  ).toUpperCase();

  const approverName =
    responseRecord?.approved_by_name ||
    currentUser?.full_name ||
    currentUser?.email ||
    "User";

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
              <span className="case-id-tag">CFPB Federal Record</span>
              <h2>Complaint #{id}</h2>
              <button
                type="button"
                className="copy-case-id-btn"
                onClick={() => {
                  navigator.clipboard.writeText(String(id));
                  setCopiedId(true);
                  setTimeout(() => setCopiedId(false), 2000);
                }}
                title="Copy Case ID to clipboard"
              >
                {copiedId ? "✓ Copied" : "📋 Copy ID"}
              </button>
            </div>
            <div className="detail-head-actions">
              <span className="date-received-pill">
                <IconCalendar size={13} /> Filed {formatDate(complaint?.date_received)}
              </span>
              <button className="modal-close-btn" onClick={onClose} title="Close (Esc)">
                ✕ Close <span className="esc-key">Esc</span>
              </button>
            </div>
          </div>

          {loading && (
            <div className="detail-loading-state">
              <div className="inline-spinner"></div>
              <span>Fetching complaint dossier & regulatory records...</span>
            </div>
          )}

          {error && <div className="error">Could not load complaint: {error}</div>}

          {complaint && (
            <div className="detail-body">
              {/* 4-Card Executive Metadata Grid */}
              <div className="case-overview-grid">
                <div className="case-info-card">
                  <div className="case-card-header">
                    <span className="case-card-icon card-icon-product">💳</span>
                    <span className="case-card-title">Product & Category</span>
                  </div>
                  <div className="case-card-value">{complaint.product}</div>
                  {complaint.sub_product && (
                    <div className="case-card-sub">{complaint.sub_product}</div>
                  )}
                </div>

                <div className="case-info-card">
                  <div className="case-card-header">
                    <span className="case-card-icon card-icon-issue">⚠️</span>
                    <span className="case-card-title">Reported Issue</span>
                  </div>
                  <div className="case-card-value">{complaint.issue}</div>
                  {complaint.sub_issue && (
                    <div className="case-card-sub">{complaint.sub_issue}</div>
                  )}
                </div>

                <div className="case-info-card">
                  <div className="case-card-header">
                    <span className="case-card-icon card-icon-company">🏛️</span>
                    <span className="case-card-title">Financial Institution</span>
                  </div>
                  <div className="case-card-value">{complaint.company}</div>
                  <div className="case-card-sub">
                    Jurisdiction: <strong>{complaint.state || "Federal"}</strong>
                    {complaint.zip_code ? ` · ZIP ${complaint.zip_code}` : ""}
                  </div>
                </div>

                <div className="case-info-card">
                  <div className="case-card-header">
                    <span className="case-card-icon card-icon-status">📋</span>
                    <span className="case-card-title">Resolution & Compliance</span>
                  </div>
                  <div className="case-card-value">
                    {renderResponseBadge(complaint.company_response_to_consumer)}
                  </div>
                  <div className="case-card-sub">
                    {complaint.timely_response ? (
                      <span className="timely-pill-detail timely-yes">✓ Timely Response SLA</span>
                    ) : (
                      <span className="timely-pill-detail timely-no">✕ Delayed SLA</span>
                    )}
                    {complaint.submitted_via ? ` · Via ${complaint.submitted_via}` : ""}
                  </div>
                </div>
              </div>

              {/* Customer Written Narrative */}
              <section className="section-block">
                <div className="section-head-row">
                  <div className="narrative-head-left">
                    <h3>Customer Written Statement</h3>
                    <span className="narrative-badge">Consumer Factual Testimony</span>
                  </div>
                  <span className="word-count-badge">
                    {complaint.narrative ? `${complaint.narrative.trim().split(/\s+/).length} Words` : "No narrative"}
                  </span>
                </div>
                <div className="narrative-card">
                  <div className="quote-mark">“</div>
                  <p className="narrative-text">
                    {complaint.narrative || "No customer written story provided in this public federal record."}
                  </p>
                </div>
              </section>

              {/* AI Categorization & Summary */}
              <section className="section-block ai-summary-section">
                <div className="section-head-row">
                  <div className="ai-head-title-group">
                    <span className="ai-icon-sparkle">✨</span>
                    <h3>AI Categorization & Legal Synthesis</h3>
                    <span className="ai-engine-pill">Groq LLaMA-3.3 70B · 12 CFR Multi-RAG</span>
                  </div>
                  {analysis && (
                    <button
                      className="refresh-ai-btn"
                      disabled={analyzing}
                      onClick={() => runAnalysis(true)}
                      title="Re-run AI analysis with fresh regulatory insights"
                    >
                      {analyzing ? "Re-analyzing..." : "↻ Refresh AI"}
                    </button>
                  )}
                </div>

                {analysis ? (
                  <div className="analysis-box-modern">
                    <div className="analysis-badge-row">
                      <span className="badge category-badge-modern">🏷️ {analysis.category}</span>
                      <span className="analysis-basis-modern">
                        ✓ {analysis.basis === "metadata"
                          ? "Evaluated against product taxonomy"
                          : "Synthesized from customer statement"}
                      </span>
                      <span className="compliance-verified-pill">Federal Compliance Verified</span>
                    </div>
                    <p className="summary-text-modern">{analysis.summary}</p>
                  </div>
                ) : (
                  <div className="ai-unrun-box">
                    <div className="ai-unrun-copy">
                      <h4>Automated Legal Taxonomy & Executive Summary</h4>
                      <p>Run immediate classification and summary synthesis against 12 CFR federal banking compliance regulations.</p>
                    </div>
                    <button
                      className="ai-trigger-btn"
                      disabled={analyzing}
                      onClick={() => runAnalysis(false)}
                    >
                      {analyzing ? (
                        <span className="btn-loading-content">
                          <span className="inline-spinner white-spinner"></span> Synthesizing Case Analysis...
                        </span>
                      ) : (
                        <><IconSparkles size={16} /> Analyze Complaint with AI</>
                      )}
                    </button>
                  </div>
                )}
                {analyzeError && <div className="error">{analyzeError}</div>}
              </section>

              {/* Similar Past Complaints (Precedents) */}
              <section className="section-block">
                <div className="section-head-row">
                  <div className="section-title-with-desc">
                    <h3>Similar Precedents & Resolved Cases</h3>
                    <span className="section-subtitle">Vector semantic search matching historic resolutions</span>
                  </div>
                  <button
                    className="find-similar-btn"
                    disabled={loadingSimilar}
                    onClick={loadSimilarCases}
                  >
                    {loadingSimilar ? "Searching Precedents..." : similarCases.length ? "↻ Re-fetch Precedents" : "🔍 Find Precedent Cases"}
                  </button>
                </div>

                {similarCases.length > 0 && (
                  <div className="similar-grid-modern">
                    {similarCases.map((sc) => {
                      const matchPct = Math.round(sc.similarity * 100);
                      return (
                        <div key={sc.complaint_id} className="similar-card-modern">
                          <div className="similar-head-modern">
                            <span className="similar-id">Case #{sc.complaint_id}</span>
                            <div
                              className="match-meter-pill"
                              style={{
                                background: matchPct >= 80 ? "#dcfce7" : "#e0f2fe",
                                color: matchPct >= 80 ? "#166534" : "#0369a1",
                              }}
                            >
                              <span className="match-pct">{matchPct}% Match</span>
                            </div>
                          </div>
                          <div className="match-bar-track">
                            <div className="match-bar-fill" style={{ width: `${matchPct}%` }}></div>
                          </div>
                          <div className="similar-meta-modern">
                            <strong>{sc.product}</strong> · {sc.issue}
                          </div>
                          <div className="similar-resolution-box">
                            <span className="resolution-label">Resolution Precedent:</span>
                            <span className="resolution-text">{sc.company_response_to_consumer || "Closed with explanation"}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* AI Draft Reply & Human-in-the-Loop Approval Studio */}
              <section className="section-block">
                <div className="section-head-row">
                  <div className="section-title-with-desc">
                    <h3>AI Official Response Draft Studio</h3>
                    <span className="section-subtitle">Human-in-the-loop regulatory reply drafting and sign-off</span>
                  </div>
                  <button className="draft-ai-btn" disabled={drafting} onClick={generateDraft}>
                    {drafting ? "Drafting with AI..." : replyDraft ? "↻ Regenerate Draft" : "✍️ Draft Official Response with AI"}
                  </button>
                </div>

                {replyDraft && (
                  <div className="reply-container-modern">
                    <div className="reply-paper-header">
                      <div className="letterhead-text">
                        <span className="letterhead-bank">BANK COMPLAINT RESOLUTION DESK</span>
                        <span className="letterhead-sub">OFFICIAL CONSUMER DISCLOSURE & RESPONSE LETTER</span>
                      </div>
                      <div className="reply-metrics">
                        <span>{replyDraft.trim().split(/\s+/).length} Words</span>
                        <span>·</span>
                        <span>{replyDraft.length} Characters</span>
                      </div>
                    </div>

                    <textarea
                      className="reply-textarea-modern"
                      rows={10}
                      value={replyDraft}
                      onChange={(e) => {
                        setReplyDraft(e.target.value);
                        if (responseRecord) {
                          setResponseRecord(null); // modifications invalidate prior approval
                        }
                      }}
                      placeholder="Official response text..."
                    />

                    <div className="reply-actions-bar">
                      {!responseRecord ? (
                        <div className="reply-unapproved-actions">
                          <span className="pending-review-hint">
                            ⚠️ Review and edit the draft above. Once approved, the response is certified for dispatch.
                          </span>
                          <button
                            className="approve-btn-modern"
                            disabled={approving}
                            onClick={handleApprove}
                          >
                            {approving ? "Certifying Approval..." : "✓ Approve & Certify Response"}
                          </button>
                        </div>
                      ) : (
                        <div className="approval-status-bar-modern">
                          <div className="approved-seal-box">
                            <span className="approved-badge-modern">
                              <IconCheck size={16} /> Certified & Approved by {approverName} ({approverRole})
                            </span>
                            <span className="approved-timestamp">
                              Audit Record ID: #{id} · Legally Certified
                            </span>
                          </div>

                          <div className="approved-cta-btns">
                            <button className="secondary small-action-btn" onClick={handleCopy}>
                              {copied ? "✓ Copied to Clipboard!" : "📋 Copy Response"}
                            </button>
                            <button className="secondary small-action-btn" onClick={handleDownload}>
                              📥 Download .txt Letter
                            </button>
                          </div>
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
