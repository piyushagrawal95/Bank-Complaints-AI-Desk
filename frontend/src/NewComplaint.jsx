import { useState, useRef } from "react";
import { createComplaint, extractComplaintFile } from "./api";
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

    try {
      const res = await extractComplaintFile(file);
      if (res && res.extracted) {
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

      {createdComplaint ? (
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
                <span className="upload-icon-graphic">📄</span>
                <h4>Intelligent Document Ingestion</h4>
                <p>
                  Upload a <strong>PDF, Word (.docx), Excel (.xlsx/.xls), CSV, or TXT</strong> dispute document to automatically extract the narrative, bank entity, and consumer email address.
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
                  {extracting ? "Extracting Data..." : "📁 Browse / Upload Dispute File"}
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
