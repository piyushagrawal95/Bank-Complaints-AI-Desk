import { useState } from "react";
import { askRule } from "./api";
import "./AskRules.css";

const QUICK_QUESTIONS = [
  { text: "How many business days does a bank have to investigate an unauthorized error?", reg: "Reg E" },
  { text: "At what times is a debt collector prohibited from calling consumers?", reg: "Reg F" },
  { text: "What are consumer rights regarding credit reporting dispute investigations?", reg: "Reg V" },
  { text: "What is the timeline for resolving credit card billing errors under Truth in Lending?", reg: "Reg Z" },
];

function AskRules() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleAsk(qToAsk) {
    const q = qToAsk || question;
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

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

  return (
    <div className="rules-container">
      <div className="rules-header">
        <div className="rules-title-row">
          <span className="rules-badge">Federal RAG Compliance</span>
          <h2>Ask Banking Regulations (12 CFR)</h2>
        </div>
        <p className="rules-subtitle">
          Submit compliance questions against 4 official federal rulebooks: <strong>Regulation E</strong> (EFT), <strong>Regulation F</strong> (Debt Collection), <strong>Regulation V</strong> (Credit Reports), and <strong>Regulation Z</strong> (Truth in Lending). Answers are mathematically synthesized strictly from verified legal citations.
        </p>
      </div>

      <div className="quick-prompts">
        <span className="quick-label">Reference Inquiries by Regulation:</span>
        <div className="quick-chips">
          {QUICK_QUESTIONS.map((item, idx) => (
            <button
              key={idx}
              type="button"
              className="quick-chip"
              onClick={() => handleQuickClick(item.text)}
              disabled={loading}
            >
              <span className="chip-tag">{item.reg}</span>
              <span>{item.text}</span>
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
          <p className="info">Searching official federal banking regulations (12 CFR)...</p>
        </div>
      )}

      {error && <div className="error">Error retrieving compliance rule: {error}</div>}

      {result && (
        <div className="result-card">
          <div className="result-meta">
            <span className="grounded-badge">✓ Grounded Compliance Answer</span>
            <span className="model-tag">Model: {result.model} ({result.provider})</span>
          </div>

          <div className="answer-text">{result.answer}</div>
        </div>
      )}
    </div>
  );
}

export default AskRules;
