import React from "react";
import {
  IconComplaints,
  IconRules,
  IconShield,
  IconSparkles,
  IconTrends,
  IconUsers,
} from "./Icons";
import "./LandingPage.css";

export default function LandingPage({ onOpenAuth }) {
  return (
    <div className="landing-container">
      {/* NAVIGATION BAR */}
      <header className="landing-navbar">
        <div className="landing-nav-inner">
          <div className="landing-brand">
            <div className="brand-badge-icon">
              <IconShield size={22} />
            </div>
            <div className="brand-text-group">
              <span className="brand-heading">Bank Complaint AI Desk</span>
              <span className="brand-edition">v2.1.0 Enterprise</span>
            </div>
          </div>

          <nav className="landing-nav-links">
            <a href="#features">Features</a>
            <a href="#compliance">Rulebooks</a>
            <a href="#architecture">Architecture</a>
            <a href="#security">Security</a>
          </nav>

          <div className="landing-nav-actions">
            <button
              className="btn-landing-login"
              onClick={() => onOpenAuth("login")}
            >
              Log In
            </button>
            <button
              className="btn-landing-signup"
              onClick={() => onOpenAuth("signup")}
            >
              Sign Up
            </button>
          </div>
        </div>
      </header>

      {/* HERO SECTION */}
      <section className="landing-hero">
        <div className="hero-glow-backdrop"></div>
        <div className="hero-content">
          <div className="hero-pill-tag">
            <IconSparkles size={14} />
            <span>Next-Generation CFPB & Banking Compliance Operating System</span>
          </div>

          <h1 className="hero-title">
            Intelligent Complaint Intelligence & <br />
            <span className="hero-gradient-text">Regulatory Compliance</span> for Banks
          </h1>

          <p className="hero-subtitle">
            Automate dispute triage, accelerate compliance investigations under
            Regulations E, Z, V & F, and equip compliance teams with instant RAG
            citations, universal file ingestion, and audited resolution drafting.
          </p>

          <div className="hero-actions">
            <button
              className="hero-btn-primary"
              onClick={() => onOpenAuth("login")}
            >
              Access Dispute Portal →
            </button>
            <button
              className="hero-btn-secondary"
              onClick={() => onOpenAuth("signup")}
            >
              Create Account
            </button>
          </div>

          {/* STATS STRIP */}
          <div className="hero-stats-grid">
            <div className="stat-card">
              <span className="stat-number">19,090+</span>
              <span className="stat-label">Ingested CFPB Disputes</span>
            </div>
            <div className="stat-card">
              <span className="stat-number">12,824</span>
              <span className="stat-label">Indexed Rulebook Chunks</span>
            </div>
            <div className="stat-card">
              <span className="stat-number">0.82s</span>
              <span className="stat-label">Groq Llama-3.3 Inference</span>
            </div>
            <div className="stat-card">
              <span className="stat-number">91.4%</span>
              <span className="stat-label">CFR Citation Precision</span>
            </div>
          </div>
        </div>
      </section>

      {/* CORE FEATURES SECTION */}
      <section id="features" className="landing-section">
        <div className="section-header">
          <h2 className="section-title">Engineered for High-Stakes Banking Operations</h2>
          <p className="section-desc">
            An integrated operating system uniting vector similarity search, natural language compliance RAG, and statistical anomaly detection.
          </p>
        </div>

        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon-wrapper feat-blue">
              <IconComplaints size={24} />
            </div>
            <h3 className="feature-heading">Universal Complaint Ingestion</h3>
            <p className="feature-text">
              Accepts manual entries or automatically extracts narratives, consumer emails, and bank entities from PDF, Word (.docx), Excel (.xlsx), and CSV files with immediate search indexing.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper feat-purple">
              <IconRules size={24} />
            </div>
            <h3 className="feature-heading">"Ask the Rules" RAG Engine</h3>
            <p className="feature-text">
              Queries federal rulebooks across 12 CFR Part 1005 (Reg E), Part 1026 (Reg Z), Part 1022 (Reg V), and Part 1006 (Reg F) with exact section citations and page numbers.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper feat-amber">
              <IconSparkles size={24} />
            </div>
            <h3 className="feature-heading">AI Categorization & 2-Sentence Briefs</h3>
            <p className="feature-text">
              Instantly maps customer grievances into 8 standardized banking taxonomy classes with cached executive summaries served in under 25 milliseconds.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper feat-green">
              <IconShield size={24} />
            </div>
            <h3 className="feature-heading">Human-in-the-Loop Audit Trail</h3>
            <p className="feature-text">
              Agents draft compliant resolution letters based on precedent cases; Supervisors and Admins formally review, approve, and dispatch automated notification emails to consumers.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper feat-red">
              <IconTrends size={24} />
            </div>
            <h3 className="feature-heading">Volume Surge & Outage Alerts</h3>
            <p className="feature-text">
              Real-time anomaly detection tracks rolling time-series counts against historical baselines, triggering operational alerts when complaint spikes exceed 30%.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper feat-indigo">
              <IconUsers size={24} />
            </div>
            <h3 className="feature-heading">Enterprise RBAC & Scrypt Crypto</h3>
            <p className="feature-text">
              Memory-hard Scrypt password hashing, Google OAuth 2.0 with clock-skew tolerance, Cloudflare Turnstile bot protection, and multi-tier role upgrade workflows.
            </p>
          </div>
        </div>
      </section>

      {/* COMPLIANCE STATUTORY DEADLINES BANNER */}
      <section id="compliance" className="landing-section compliance-strip">
        <div className="compliance-card">
          <div className="compliance-badge">Statutory Protection</div>
          <h2 className="compliance-title">Meeting Non-Negotiable Federal Mandates</h2>
          <div className="compliance-grid">
            <div className="compliance-item">
              <span className="rule-badge">Regulation E (§ 1005.11)</span>
              <h4>10 Business Days</h4>
              <p>Mandatory error investigation or provisional credit with extension up to 45 calendar days for electronic fund transfers.</p>
            </div>
            <div className="compliance-item">
              <span className="rule-badge">Regulation Z (§ 1026.13)</span>
              <h4>30 Days / 2 Cycles</h4>
              <p>Strict billing error acknowledgment within 30 days and dispute resolution within 2 complete billing cycles for credit cards.</p>
            </div>
            <div className="compliance-item">
              <span className="rule-badge">Regulation V (§ 611)</span>
              <h4>30 Calendar Days</h4>
              <p>Mandatory completion of direct consumer credit reporting disputes with credit bureaus and furnishers.</p>
            </div>
            <div className="compliance-item">
              <span className="rule-badge">Regulation F (§ 1006.6)</span>
              <h4>Strict Contact Windows</h4>
              <p>Debt collection communication limited between 8:00 AM and 9:00 PM local time with harassment prevention boundaries.</p>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="footer-left">
            <div className="brand-text-group">
              <span className="brand-heading">Bank Complaint AI Desk</span>
              <p className="footer-tagline">
                AI-Powered Complaint Intelligence & Regulatory Compliance System
              </p>
            </div>
          </div>
          <div className="footer-right">
            <button className="footer-btn" onClick={() => onOpenAuth("login")}>
              Agent Login
            </button>
            <button className="footer-btn" onClick={() => onOpenAuth("signup")}>
              Register
            </button>
          </div>
        </div>
        <div className="footer-bottom">
          <span>&copy; {new Date().getFullYear()} Bank Complaint AI Desk. All rights reserved.</span>
          <span>Lead Engineer: Piyush Agrawal</span>
        </div>
      </footer>
    </div>
  );
}
