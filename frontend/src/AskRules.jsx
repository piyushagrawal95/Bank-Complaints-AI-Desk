import { useState } from "react";
import { askRule } from "./api";
import "./AskRules.css";

const QUICK_QUESTIONS = [
  "How many business days does a bank have to investigate an unauthorized error?",
  "At what times is a debt collector prohibited from calling consumers?",
  "What are consumer rights regarding credit reporting dispute investigations?",
  "What is the timeline for resolving credit card billing errors under Truth in Lending?",
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
              <span>{text}</span>
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
