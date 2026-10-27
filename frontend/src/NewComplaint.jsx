import { useState, useRef } from "react";
import { createComplaint, createComplaintsBatch, extractComplaintFile } from "./api";
import { IconCheck, IconComplaints, IconSparkles } from "./Icons";
import "./NewComplaint.css";

const STANDARD_PRODUCTS = [
  "Checking or savings account",
  "Credit card or prepaid card",
  "Credit reporting, credit repair services, or other personal consumer reports",
  "Debt collection",
  "Money transfer, virtual currency, or money service",
  "Mortgage",
  "Payday loan, title loan, or personal loan",
  "Student loan",
  "Vehicle loan or lease",
];

const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
  "DC", "PR"
];

const INITIAL_FORM = {
  product: "Checking or savings account",
  sub_product: "",
  issue: "",
  sub_issue: "",
  company: "JPMorgan Chase & Co.",
  state: "NY",
  zip_code: "",
  consumer_email: "",
  narrative: "",
  date_received: new Date().toISOString().split("T")[0],
};

export default function NewComplaint({ onViewComplaint, onGoToComplaints }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [extracting, setExtracting] = useState(false);
  const [extractSuccess, setExtractSuccess] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [createdComplaint, setCreatedComplaint] = useState(null);

  // Batch Multi-Record Ingestion states
  const [batchData, setBatchData] = useState(null);
  const [batchSuccess, setBatchSuccess] = useState(null);
  const [batchSaving, setBatchSaving] = useState(false);

  const fileInputRef = useRef(null);

  function handleChange(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setExtracting(true);
    setError(null);
    setExtractSuccess(null);
    setBatchData(null);
    setBatchSuccess(null);
    setCreatedComplaint(null);

    try {
      const res = await extractComplaintFile(file);
      if (res && res.is_batch && res.records && res.records.length > 1) {
        setBatchData({
          filename: file.name,
          count: res.count,
          records: res.records,
        });
      } else if (res && res.extracted) {
        const ext = res.extracted;
        setForm((prev) => ({
          ...prev,
          product: ext.product || prev.product,
          sub_product: ext.sub_product || prev.sub_product,
          issue: ext.issue || prev.issue,
          sub_issue: ext.sub_issue || prev.sub_issue,
          company: ext.company || prev.company,
          state: ext.state || prev.state,
          zip_code: ext.zip_code || prev.zip_code,
          consumer_email: ext.consumer_email || prev.consumer_email,
          narrative: ext.narrative || prev.narrative,
          date_received: ext.date_received || prev.date_received,
        }));

        setExtractSuccess({
          filename: file.name,
          hasEmail: Boolean(ext.consumer_email),
          email: ext.consumer_email,
        });
      }
    } catch (err) {
      setError(`Extraction error: ${err.message}`);
    } finally {
      setExtracting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleBatchSubmit() {
    if (!batchData || !batchData.records) return;
    setBatchSaving(true);
    setError(null);

    try {
      const res = await createComplaintsBatch(batchData.records);
      setBatchSuccess({
        filename: batchData.filename,
        count: res.count,
        complaints: res.complaints || [],
      });
      setBatchData(null);
    } catch (err) {
      setError(err.message || "Failed to batch ingest complaints.");
    } finally {
      setBatchSaving(false);
    }
  }

  function handleSelectBatchSingleRecord(rec) {
    setForm({
      product: rec.product || "Checking or savings account",
      sub_product: rec.sub_product || "",
      issue: rec.issue || "",
      sub_issue: rec.sub_issue || "",
      company: rec.company || "JPMorgan Chase & Co.",
      state: rec.state || "NY",
      zip_code: rec.zip_code || "",
      consumer_email: rec.consumer_email || "",
      narrative: rec.narrative || "",
      date_received: rec.date_received || new Date().toISOString().split("T")[0],
    });
    setBatchData(null);
    setExtractSuccess({
      filename: batchData.filename,
      hasEmail: Boolean(rec.consumer_email),
      email: rec.consumer_email,
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.issue.trim()) {
      setError("Please specify the primary complaint issue.");
      return;
    }
    if (!form.company.trim()) {
      setError("Please specify the bank or financial institution company name.");
      return;
    }
    if (!form.narrative.trim() || form.narrative.trim().length < 10) {
      setError("Please enter a detailed complaint narrative (at least 10 characters).");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const res = await createComplaint(form);
      setCreatedComplaint(res.complaint);
    } catch (err) {
      setError(err.message || "Failed to create complaint.");
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    setForm(INITIAL_FORM);
    setExtractSuccess(null);
    setCreatedComplaint(null);
    setBatchData(null);
    setBatchSuccess(null);
    setError(null);
  }

  return (
    <div className="new-complaint-wrapper">
      <div className="new-complaint-header">
        <div className="title-row">
          <div className="icon-badge">
            <IconComplaints size={22} />
          </div>
          <div>
            <h2>Record New Bank Dispute</h2>
            <p className="subtitle">
              Universal ingestion via direct manual entry or automatic data extraction from PDF, Word, Excel, and CSV files.
            </p>
          </div>
        </div>
      </div>

      {/* BATCH SUCCESS CARD */}
      {batchSuccess ? (
        <div className="success-banner-card">
          <div className="success-icon-ring">
            <IconCheck size={32} />
          </div>
          <h3>Batch Ingestion Completed Successfully!</h3>
          <p className="success-lead">
            <strong>{batchSuccess.count} complaint records</strong> from <strong>{batchSuccess.filename}</strong> have been indexed and saved in the database.
          </p>

          <div className="batch-preview-table-card">
            <table className="batch-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Bank / Entity</th>
                  <th>Product Vertical</th>
                  <th>Primary Issue</th>
                  <th>Consumer Email</th>
                </tr>
              </thead>
              <tbody>
                {batchSuccess.complaints.map((c, i) => (
                  <tr key={c.complaint_id || i}>
                    <td><strong className="complaint-id-link">#{c.complaint_id}</strong></td>
                    <td>{c.company}</td>
                    <td>{c.product}</td>
                    <td>{c.issue}</td>
                    <td>{c.consumer_email || "Not specified"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="success-actions" style={{ marginTop: "24px" }}>
            <button className="btn-primary" onClick={onGoToComplaints}>
              Go to Complaints Explorer
            </button>
            <button className="btn-outline" onClick={handleReset}>
              + Ingest Another File
            </button>
          </div>
        </div>
      ) : batchData ? (
        /* MULTI-RECORD BATCH PREVIEW CARD */
        <div className="batch-detect-card">
          <div className="batch-detect-header">
            <div className="batch-badge">Multi-Record File Detected</div>
            <h3>{batchData.count} Individual Complaints Found in "{batchData.filename}"</h3>
            <p className="batch-sub">
              The uploaded file contains multiple dispute records. You can ingest all records in bulk into the database or choose to edit the first record in the standard form.
            </p>
          </div>

          <div className="batch-preview-table-card">
            <table className="batch-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Bank / Entity</th>
                  <th>Product Vertical</th>
                  <th>Dispute Issue</th>
                  <th>Consumer Email</th>
                </tr>
              </thead>
              <tbody>
                {batchData.records.map((rec, idx) => (
                  <tr key={idx}>
                    <td><strong>{idx + 1}</strong></td>
                    <td>{rec.company}</td>
                    <td>{rec.product}</td>
                    <td>{rec.issue}</td>
                    <td>{rec.consumer_email || "Not specified"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {error && <div className="form-error-banner">{error}</div>}

          <div className="batch-actions-row">
            <button
              className="btn-primary"
              disabled={batchSaving}
              onClick={handleBatchSubmit}
            >
              {batchSaving ? "Ingesting All Records..." : `Ingest All ${batchData.count} Complaints into Database`}
            </button>
            <button
              className="btn-secondary"
              disabled={batchSaving}
              onClick={() => handleSelectBatchSingleRecord(batchData.records[0])}
            >
              Edit First Record in Form
            </button>
            <button
              className="btn-outline"
              disabled={batchSaving}
              onClick={handleReset}
            >
              Cancel / Choose Another File
            </button>
          </div>
        </div>
      ) : createdComplaint ? (
        /* SINGLE COMPLAINT SUCCESS CARD */
        <div className="success-banner-card">
          <div className="success-icon-ring">
            <IconCheck size={32} />
          </div>
          <h3>Complaint Recorded Successfully!</h3>
          <p className="success-lead">
            Complaint reference <strong>#{createdComplaint.complaint_id}</strong> has been assigned and indexed in the PostgreSQL database.
          </p>

          <div className="success-meta-box">
            <div className="meta-item">
              <span className="lbl">Product:</span>
              <span className="val">{createdComplaint.product}</span>
            </div>
            <div className="meta-item">
              <span className="lbl">Bank / Company:</span>
              <span className="val">{createdComplaint.company}</span>
            </div>
            <div className="meta-item">
              <span className="lbl">Consumer Email:</span>
              <span className="val email-highlight">
                {createdComplaint.consumer_email || "None specified"}
              </span>
            </div>
            <div className="meta-item">
              <span className="lbl">Date Received:</span>
              <span className="val">{createdComplaint.date_received}</span>
            </div>
          </div>

          <div className="success-actions">
            <button
              className="btn-primary"
              onClick={() => onViewComplaint(createdComplaint.complaint_id)}
            >
              <IconSparkles size={16} /> Open in AI Desk & Draft Response
            </button>
            <button className="btn-secondary" onClick={onGoToComplaints}>
              Go to Complaints Explorer
            </button>
            <button className="btn-outline" onClick={handleReset}>
              + Record Another Dispute
            </button>
          </div>
        </div>
      ) : (
        <div className="new-complaint-body">
          {/* FILE UPLOAD DROPZONE */}
          <div className="upload-dropzone-card">
            <div className="dropzone-inner">
              <div className="upload-prompt-text">
                <div className="upload-icon-graphic">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                  </svg>
                </div>
                <h4>Intelligent Document Ingestion</h4>
                <p>
                  Upload a <strong>PDF, Word (.docx), Excel (.xlsx/.xls), CSV, or TXT</strong> dispute document to automatically extract the narrative, bank entity, and consumer email address. Multi-record files will automatically trigger batch ingestion.
                </p>
              </div>

              <div className="upload-controls">
                <input
                  ref={fileInputRef}
                  type="file"
                  id="complaint-file-upload"
                  accept=".pdf,.docx,.xlsx,.xls,.csv,.txt"
                  style={{ display: "none" }}
                  onChange={handleFileUpload}
                  disabled={extracting}
                />
                <button
                  type="button"
                  className="btn-upload"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={extracting}
                >
                  {extracting ? "Extracting Data..." : "Browse / Upload Dispute File"}
                </button>
              </div>
            </div>

            {extractSuccess && (
              <div className="extract-banner">
                <span className="extract-icon">✓</span>
                <div>
                  <strong>Successfully parsed "{extractSuccess.filename}"</strong>
                  <p>
                    Complaint attributes pre-filled below.
                    {extractSuccess.hasEmail ? (
                      <> Consumer email auto-populated: <code className="email-code">{extractSuccess.email}</code></>
                    ) : (
                      " No email found in document; you can enter it manually below."
                    )}
                  </p>
                </div>
              </div>
            )}
          </div>

          {error && <div className="form-error-banner">{error}</div>}

          {/* COMPLAINT FORM */}
          <form className="complaint-form" onSubmit={handleSubmit}>
            <div className="form-grid-2">
              <div className="form-group">
                <label>Product Vertical *</label>
                <select
                  value={form.product}
                  onChange={(e) => handleChange("product", e.target.value)}
                  required
                >
                  {STANDARD_PRODUCTS.map((prod) => (
                    <option key={prod} value={prod}>
                      {prod}
                    </option>
                  ))}
                  <option value="Other financial service">Other financial service</option>
                </select>
              </div>

              <div className="form-group">
                <label>Sub-Product (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. General-purpose credit card, Checking"
                  value={form.sub_product}
                  onChange={(e) => handleChange("sub_product", e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Primary Dispute Issue *</label>
                <input
                  type="text"
                  placeholder="e.g. Problem with unauthorized transaction"
                  value={form.issue}
                  onChange={(e) => handleChange("issue", e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label>Sub-Issue (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Card charged twice for single purchase"
                  value={form.sub_issue}
                  onChange={(e) => handleChange("sub_issue", e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Financial Institution / Bank *</label>
                <input
                  type="text"
                  placeholder="e.g. JPMorgan Chase & Co., Wells Fargo"
                  value={form.company}
                  onChange={(e) => handleChange("company", e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="highlight-label">
                  Consumer Email Address (For Resolution Notices)
                </label>
                <input
                  type="email"
                  placeholder="customer@example.com"
                  value={form.consumer_email}
                  onChange={(e) => handleChange("consumer_email", e.target.value)}
                  className="email-input-field"
                />
                <span className="field-hint">
                  Auto-populated if found in uploaded file. Official resolution letters will be dispatched to this email upon supervisor approval.
                </span>
              </div>

              <div className="form-group form-group-sm">
                <label>State</label>
                <select
                  value={form.state}
                  onChange={(e) => handleChange("state", e.target.value)}
                >
                  {US_STATES.map((st) => (
                    <option key={st} value={st}>
                      {st}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group form-group-sm">
                <label>ZIP Code</label>
                <input
                  type="text"
                  placeholder="e.g. 10001"
                  value={form.zip_code}
                  onChange={(e) => handleChange("zip_code", e.target.value)}
                  maxLength={10}
                />
              </div>

              <div className="form-group">
                <label>Date Received</label>
                <input
                  type="date"
                  value={form.date_received}
                  onChange={(e) => handleChange("date_received", e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="form-group narrative-group">
              <div className="label-with-counter">
                <label>Customer Grievance Narrative / Dispute Details *</label>
                <span className="char-count">{form.narrative.length} characters</span>
              </div>
              <textarea
                rows={8}
                placeholder="Paste or review the customer's complete narrative description of the dispute, unauthorized charges, dates, and amounts..."
                value={form.narrative}
                onChange={(e) => handleChange("narrative", e.target.value)}
                required
              />
            </div>

            <div className="form-footer">
              <button
                type="submit"
                className="btn-submit-complaint"
                disabled={saving}
              >
                {saving ? "Ingesting & Indexing Dispute..." : "Save & Ingest Complaint"}
              </button>
              <button
                type="button"
                className="btn-cancel"
                onClick={handleReset}
                disabled={saving}
              >
                Reset Form
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
