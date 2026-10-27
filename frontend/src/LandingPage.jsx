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
              <span className="brand-edition">Enterprise Edition</span>
            </div>
          </div>

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
            <span>AI-Powered Banking Compliance & Dispute Intelligence Operating System</span>
          </div>

          <h1 className="hero-title">
            Intelligent Complaint Intelligence & <br />
            <span className="hero-gradient-text">Regulatory Compliance</span> for Banks
          </h1>

          <p className="hero-subtitle">
            Automate dispute triage, accelerate compliance investigations under
            federal regulations, and equip compliance teams with instant RAG
            citations, universal file ingestion, and audited resolution drafting.
          </p>

          <div className="hero-actions">
            <button
              className="hero-btn-primary"
              onClick={() => onOpenAuth("login")}
            >
              Get Started →
            </button>
            <button
              className="hero-btn-secondary"
              onClick={() => onOpenAuth("signup")}
            >
              Create Account
            </button>
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
              Queries federal rulebooks across official banking regulations with exact section citations and page numbers for compliance officers.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon-wrapper feat-amber">
              <IconSparkles size={24} />
            </div>
            <h3 className="feature-heading">AI Categorization & 2-Sentence Briefs</h3>
            <p className="feature-text">
              Instantly maps customer grievances into standardized banking taxonomy classes with cached executive summaries served in sub-second speeds.
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
              Real-time anomaly detection tracks rolling time-series counts against historical baselines, triggering operational alerts when complaint spikes occur.
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
