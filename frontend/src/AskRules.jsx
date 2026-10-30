import { useState } from "react";
import { askRule } from "./api";
import { IconCheck, IconCopy, IconRules } from "./Icons";
import "./AskRules.css";

const QUICK_QUESTIONS = [
  "How many business days does a bank have to investigate an unauthorized error?",
  "At what times is a debt collector prohibited from calling consumers?",
  "What are consumer rights regarding credit reporting dispute investigations?",
  "What is the timeline for resolving credit card billing errors under Truth in Lending?",
];

function renderFormattedInline(text) {
  if (!text) return null;
  // Splits on **bold** tokens
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function FormattedComplianceAnswer({ answer }) {
  if (!answer) return null;

  const rawLines = answer.split("\n").map((l) => l.trim()).filter(Boolean);
  const blocks = [];
  let currentBullets = [];

  const flushBullets = () => {
    if (currentBullets.length > 0) {
      blocks.push({ type: "bullets", items: [...currentBullets] });
      currentBullets = [];
    }
  };

  rawLines.forEach((line) => {
    // 1. Detect if line is a Heading (Markdown ###, bold section title, or bulleted category header)
    const isMarkdownHeading = /^#{1,4}\s+/.test(line);
    const isBoldHeaderLine = /^(\*{2})[^*:]+:\*{2}\s*$/.test(line) || /^(\*{2})[^*]+\*{2}\s*:?\s*$/.test(line);
    const isBulletHeader = /^([•\-*]|\d+\.)\s*\*\*([^*]+)\*\*:\s*$/.test(line);
    const isCategoryHeader =
      /^([•\-*]|\d+\.)\s*(Core Summary|Core Timeline|Timeline & Deadlines|Bank['’]s Obligations|Consumer Rights|Exceptions|Regulatory Requirements|Key Provisions|Mandatory Disclosures|Dispute Procedures)\b/i.test(
        line
      ) && !line.includes(". ");

    const isHeading =
      isMarkdownHeading ||
      isBoldHeaderLine ||
      isBulletHeader ||
      isCategoryHeader ||
      (line.endsWith(":") && line.length < 60 && !/^([•\-*]|\d+\.)\s+/.test(line));

    if (isHeading) {
      flushBullets();
      // Clean up markdown hashes, bullet symbols, bold markers, and trailing colons from heading text
      const cleanHeading = line
        .replace(/^#{1,4}\s+/, "")
        .replace(/^([•\-*]|\d+\.)\s*/, "")
        .replace(/^\*\*|\*\*$/g, "")
        .replace(/\*\*:/, "")
        .replace(/:$/, "")
        .trim();
      blocks.push({ type: "heading", text: cleanHeading });
    } else {
      // 2. Detect bullet points
      const isBullet = /^([•\-*]|\d+\.)\s+/.test(line);
      if (isBullet) {
        const cleanText = line.replace(/^([•\-*]|\d+\.)\s+/, "");
        currentBullets.push(cleanText);
      } else {
        flushBullets();
        blocks.push({ type: "paragraph", text: line });
      }
    }
  });
  flushBullets();

  return (
    <div className="compliance-answer-body">
      {blocks.map((block, idx) => {
        if (block.type === "heading") {
          return (
            <h4 key={idx} className="answer-section-heading">
              {block.text}
            </h4>
          );
        }

        if (block.type === "bullets") {
          return (
            <ul key={idx} className="compliance-bullets">
              {block.items.map((bullet, bIdx) => (
                <li key={bIdx} className="compliance-bullet-item">
                  <div className="bullet-icon-wrapper">
                    <span className="bullet-dot"></span>
                  </div>
                  <div className="bullet-body">{renderFormattedInline(bullet)}</div>
                </li>
              ))}
            </ul>
          );
        }

        // First paragraph as executive summary if more blocks follow
        const isExecutiveSummary = idx === 0 && blocks.length > 1;
        if (isExecutiveSummary) {
          const cleanIntro = block.text.replace(
            /^(\*\*Core Summary:\*\*|\*\*Summary:\*\*|Core Summary:|Summary:)\s*/i,
            ""
          );
          return (
            <div key={idx} className="answer-summary-box">
              <div className="summary-badge-title">
                <span className="summary-icon"><IconRules size={14} /></span> Key Regulatory Mandate
              </div>
              <p className="summary-text-lead">{renderFormattedInline(cleanIntro)}</p>
            </div>
          );
        }

        return (
          <p key={idx} className="answer-paragraph">
            {renderFormattedInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}

function detectRegulations(text, citations = []) {
  const regs = new Set();
  const lower = (text || "").toLowerCase();
  if (lower.includes("regulation e") || lower.includes("1005")) regs.add("Regulation E");
  if (lower.includes("regulation z") || lower.includes("1026")) regs.add("Regulation Z");
  if (lower.includes("regulation f") || lower.includes("1006")) regs.add("Regulation F");
  if (lower.includes("regulation v") || lower.includes("fcra") || lower.includes("1022")) regs.add("Regulation V");

  (citations || []).forEach((c) => {
    if (c.regulation) {
      if (c.regulation.toLowerCase().includes("e")) regs.add("Regulation E");
      else if (c.regulation.toLowerCase().includes("z")) regs.add("Regulation Z");
      else if (c.regulation.toLowerCase().includes("f")) regs.add("Regulation F");
      else if (c.regulation.toLowerCase().includes("v")) regs.add("Regulation V");
      else regs.add(c.regulation);
    }
  });

  return Array.from(regs);
}

function AskRules() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingSecs, setLoadingSecs] = useState(0);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [showCitations, setShowCitations] = useState(false);

  useEffect(() => {
    let interval = null;
    if (loading) {
      setLoadingSecs(0);
      interval = setInterval(() => setLoadingSecs((s) => s + 1), 1000);
    } else {
      setLoadingSecs(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loading]);

  async function handleAsk(qToAsk) {
    const q = qToAsk || question;
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setCopied(false);
    setShowCitations(false);

    try {
      const data = await askRule(q.trim());
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleQuickClick(q) {
    setQuestion(q);
    handleAsk(q);
  }

  function copyAnswerToClipboard() {
    if (!result || !result.answer) return;
    navigator.clipboard.writeText(result.answer).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const detectedRegs = result ? detectRegulations(result.answer, result.citations) : [];

  return (
    <div className="rules-container">
      <div className="rules-header">
        <div className="rules-title-row">
          <span className="rules-badge">Compliance Intelligence</span>
          <h2>Ask Regulatory Compliance Questions</h2>
        </div>
        <p className="rules-subtitle">
          Submit compliance and dispute resolution questions. Answers are mathematically synthesized strictly from verified legal citations and banking standards.
        </p>
      </div>

      <div className="quick-prompts">
        <span className="quick-label">Suggested Questions:</span>
        <div className="quick-chips">
          {QUICK_QUESTIONS.map((text, idx) => (
            <button
              key={idx}
              type="button"
              className="quick-chip"
              onClick={() => handleQuickClick(text)}
              disabled={loading}
            >
              <span className="chip-arrow">›</span>
              <span className="chip-text">{text}</span>
            </button>
          ))}
        </div>
      </div>

      <form
        className="rules-form"
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk();
        }}
      >
        <div className="input-group">
          <input
            type="text"
            className="rules-input"
            placeholder="Type your compliance question here (e.g. Can debt collector call at 6 AM?)..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="rules-submit" disabled={loading || !question.trim()}>
            {loading ? "Searching Regulations..." : "Ask Rule"}
          </button>
        </div>
      </form>

      {loading && (
        <div className="loading-card">
          <div className="loading-pulse"></div>
          <p className="info">
            {loadingSecs < 4
              ? "Searching official banking regulations..."
              : loadingSecs < 12
              ? `Finding answers in rulebooks (${loadingSecs}s)...`
              : `Finalizing answer (${loadingSecs}s)... please wait`}
          </p>
        </div>
      )}

      {error && (
        <div className="server-error-banner">
          <div className="server-error-left">
            <span className="server-error-icon">⚠️</span>
            <div>
              <div className="server-error-title">Unable to Retrieve Rules</div>
              <div className="server-error-msg">{error}</div>
              <div className="server-error-sub">
                Please wait a moment and click retry to try again.
              </div>
            </div>
          </div>
          <button
            type="button"
            className="btn-retry-modern"
            onClick={() => handleAsk()}
          >
            🔄 Try Again
          </button>
        </div>
      )}

      {result && (
        <div className="result-card">
          <div className="result-meta">
            <div className="meta-left">
              <span className="grounded-badge">✓ Grounded Compliance Answer</span>
              {detectedRegs.map((reg, idx) => (
                <span key={idx} className="reg-detected-badge">
                  {reg}
                </span>
              ))}
            </div>
            <div className="meta-actions">
              <button
                type="button"
                className={`copy-answer-btn ${copied ? "copied" : ""}`}
                onClick={copyAnswerToClipboard}
                title="Copy answer text to clipboard"
              >
                {copied ? (
                  <>
                    <IconCheck size={14} />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <IconCopy size={14} />
                    <span>Copy Answer</span>
                  </>
                )}
              </button>
            </div>
          </div>

          <FormattedComplianceAnswer answer={result.answer} />

          {result.citations && result.citations.length > 0 && (
            <div className="citations-wrapper">
              <button
                type="button"
                className="citations-toggle-btn"
                onClick={() => setShowCitations(!showCitations)}
              >
                <span>{showCitations ? "▼ Hide" : "▶ View"} Official Legal Excerpts ({result.citations.length})</span>
              </button>

              {showCitations && (
                <div className="citations-section">
                  <div className="citations-grid">
                    {result.citations.map((c, idx) => (
                      <div key={idx} className="citation-card">
                        <div className="citation-top">
                          <span className={`reg-tag badge-${(c.regulation || "").toLowerCase().replace(/\s+/g, "-")}`}>
                            {c.regulation}
                          </span>
                          <span className="similarity-badge">
                            {(c.similarity * 100).toFixed(1)}% match
                          </span>
                        </div>
                        <div className="citation-section">{c.section}</div>
                        <div className="citation-page">Page {c.page_number}</div>
                        <p className="citation-excerpt">"{c.excerpt}"</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AskRules;
