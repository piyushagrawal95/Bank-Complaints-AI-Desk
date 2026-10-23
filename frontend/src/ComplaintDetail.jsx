import { useEffect, useState } from "react";
import {
  analyzeComplaint,
  approveComplaintResponse,
  draftReply,
  getComplaint,
  getSimilarComplaints,
} from "./api";
import { IconCheck, IconSparkles } from "./Icons";
import "./ComplaintDetail.css";

function ComplaintDetail({ id, currentUser, onClose }) {
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
          <div className="detail-metadata">
            <span><strong>Product:</strong> {complaint.product}</span>
            <span><strong>Issue:</strong> {complaint.issue}</span>
            <span><strong>Company:</strong> {complaint.company}</span>
            <span><strong>Date:</strong> {complaint.date_received}</span>
            <span><strong>State:</strong> {complaint.state || "N/A"}</span>
          </div>

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
            {analyzeError && <div className="error">{analyzeError}</div>}
          </section>

          {/* Similar Past Complaints */}
          <section className="section-block">
            <div className="section-head-row">
              <h3>Similar Past Complaints</h3>
              <button
                className="find-similar-btn"
                disabled={loadingSimilar}
                onClick={loadSimilarCases}
              >
                {loadingSimilar ? "Searching..." : similarCases.length ? "↻ Re-fetch Similar Cases" : "🔍 Find Similar Cases"}
              </button>
            </div>

            {similarCases.length > 0 && (
              <div className="similar-grid">
                {similarCases.map((sc) => (
                  <div key={sc.complaint_id} className="similar-item">
                    <div className="similar-head">
                      <strong>#{sc.complaint_id}</strong>
                      <span className="similarity-tag">{Math.round(sc.similarity * 100)}% Match</span>
                    </div>
                    <div className="similar-meta">{sc.product} · {sc.issue}</div>
                    <div className="similar-response">
                      <strong>Resolution:</strong> {sc.company_response_to_consumer || "Closed with explanation"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* AI Draft Reply & Approval */}
          <section className="section-block">
            <div className="section-head-row">
              <h3>AI Response Draft</h3>
              <button className="draft-ai-btn" disabled={drafting} onClick={generateDraft}>
                {drafting ? "Drafting with AI..." : replyDraft ? "↻ Regenerate Draft" : "✍️ Draft Reply with AI"}
              </button>
            </div>

            {replyDraft && (
              <div className="reply-container">
                <p className="reply-instruction">
                  Review and edit the draft response letter before approving it to send to the consumer:
                </p>
                <textarea
                  className="reply-textarea"
                  rows={9}
                  value={replyDraft}
                  onChange={(e) => {
                    setReplyDraft(e.target.value);
                    if (responseRecord) {
                      setResponseRecord(null); // modifications invalidate prior approval
                    }
                  }}
                />

                <div className="reply-actions">
                  {!responseRecord ? (
                    <button
                      className="approve-btn"
                      disabled={approving}
                      onClick={handleApprove}
                      style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
                    >
                      {approving ? "Saving Approval..." : "Approve Response"}
                    </button>
                  ) : (
                    <div className="approval-status-bar">
                      <span className="approved-badge">
                        <IconCheck size={15} /> Approved by {approverName} ({approverRole})
                      </span>

                      <button className="secondary small-action-btn" onClick={handleCopy}>
                        {copied ? "✓ Copied!" : "📋 Copy"}
                      </button>
                      <button className="secondary small-action-btn" onClick={handleDownload}>
                        📥 Download .txt
                      </button>
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
