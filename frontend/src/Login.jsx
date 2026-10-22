import { useEffect, useState } from "react";
import { forgotPassword, login,loginWithGoogle, resetPassword, saveToken, signup } from "./api";
import { IconShield } from "./Icons";
import "./Login.css";

function EyeIcon({ off }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  };
  if (off) {
    return (
      <svg {...common}>
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function Login({ onLoggedIn }) {
  const [mode, setMode] = useState("login"); // "login", "signup", "forgot", "reset"
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("reset_token") || params.get("token");
    if (token) {
      setResetToken(token);
      setMode("reset");
    }
  }, []);

  async function handleGoogleSuccess(response){
    setLoading(true);
    setError(null);
    try{
      const data=await loginWithGoogle(response.credential);
      saveToken(data.access_token);
      onLoggedIn(data.user);
    }
    catch(err){
      setError(err.message||"Google Login failed")
    }
    finally{
      setLoading(false);
    }
  }

  useEffect(() => {
    function renderGoogleBtn() {
      if (!window.google || (mode !== "login" && mode !== "signup")) return;
      try {
        window.google.accounts.id.initialize({
          client_id: "639319834126-b1ouen3no25o2elim13idbab182m3tjd.apps.googleusercontent.com",
          callback: handleGoogleSuccess,
        });

        const btnContainer = document.getElementById("googleBtn");
        if (btnContainer) {
          const targetWidth = Math.min(380, btnContainer.offsetWidth || 360);
          window.google.accounts.id.renderButton(btnContainer, {
            theme: "outline",
            size: "large",
            width: targetWidth,
            text: "continue_with",
            shape: "rectangular",
            logo_alignment: "left",
          });
        }
      } catch (e) {
        console.error("Google Auth render error:", e);
      }
    }

    if (window.google) {
      renderGoogleBtn();
    } else {
      const timer = setInterval(() => {
        if (window.google) {
          clearInterval(timer);
          renderGoogleBtn();
        }
      }, 100);
      return () => clearInterval(timer);
    }
  }, [mode]);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      if (mode === "signup") {
        await signup(email, password, fullName);
        setMode("login");
        setPassword("");
        setFullName("");
        setSuccess("Account created successfully. Please sign in.");
      } else if (mode === "login") {
        const result = await login(email, password);
        saveToken(result.access_token);
        onLoggedIn(result.user);
      } else if (mode === "forgot") {
        const res = await forgotPassword(email);
        setSuccess(res.message);
        if (res.dev_reset_token) {
          setResetToken(res.dev_reset_token);
          setMode("reset");
        }
      } else if (mode === "reset") {
        const res = await resetPassword(resetToken, password);
        setMode("login");
        setPassword("");
        setSuccess(res.message);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      {/* LEFT BRANDING PANEL */}
      <div className="auth-brand-side">
        <div className="brand-inner">
          <div className="bank-emblem">
            <div className="emblem-icon">
              <IconShield size={24} />
            </div>
            <div className="emblem-text">
              <span className="bank-name">Bank Complaint AI Desk</span>
              <span className="bank-sub">Federal Compliance & Resolution System</span>
            </div>
          </div>

          <h2 className="brand-headline">
            Intelligent Complaint Intelligence & Regulatory Compliance
          </h2>
          <p className="brand-subtext">
            Enterprise compliance platform powered by advanced semantic retrieval, dynamic chunking of 12 CFR federal banking regulations, and automated complaint resolution workflows.
          </p>

          <div className="pillar-list">
            <div className="pillar-item">
              <span className="pillar-bullet"></span>
              <div className="pillar-info">
                <span className="pillar-title">Automated Issue Classification</span>
                <span className="pillar-desc">Categorizes complaints and synthesizes executive summaries instantly.</span>
              </div>
            </div>
            <div className="pillar-item">
              <span className="pillar-bullet"></span>
              <div className="pillar-info">
                <span className="pillar-title">Multi-Regulation RAG (12 CFR)</span>
                <span className="pillar-desc">Exact legal citations and answers across Regulation E, F, V, and Z.</span>
              </div>
            </div>
            <div className="pillar-item">
              <span className="pillar-bullet"></span>
              <div className="pillar-info">
                <span className="pillar-title">Similar Precedents & AI Reply Drafting</span>
                <span className="pillar-desc">Finds resolved cases and drafts official response letters for review.</span>
              </div>
            </div>
            <div className="pillar-item">
              <span className="pillar-bullet"></span>
              <div className="pillar-info">
                <span className="pillar-title">Operational Spikes & Baseline Analytics</span>
                <span className="pillar-desc">Anomaly detection comparing rolling-window traffic with historical averages.</span>
              </div>
            </div>
          </div>

          <div className="trust-footer">
            <div className="trust-item">
              <span className="trust-val">12 CFR</span>
              <span className="trust-lbl">Reg E, F, V, Z</span>
            </div>
            <div className="trust-sep"></div>
            <div className="trust-item">
              <span className="trust-val">Multi-RAG</span>
              <span className="trust-lbl">Compliance Search</span>
            </div>
            <div className="trust-sep"></div>
            <div className="trust-item">
              <span className="trust-val">RBAC</span>
              <span className="trust-lbl">Agent / Super / Admin</span>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT AUTH CARD PANEL */}
      <div className="auth-form-side">
        <div className="auth-card-modern">
          <div className="auth-card-head">
            <h3 className="auth-card-title">
              {mode === "login"
                ? "Sign In"
                : mode === "signup"
                ? "Create Account"
                : mode === "forgot"
                ? "Reset Your Password"
                : "Set New Password"}
            </h3>
            <p className="auth-card-sub">
              {mode === "login"
                ? "Enter your credentials to access your account"
                : mode === "signup"
                ? "Fill in your details to create an account"
                : mode === "forgot"
                ? "Enter your email to receive a password reset link"
                : "Enter your verification token and your new password"}
            </p>
          </div>

          {/* Mode Switcher Tabs - Only Sign In and Register */}
          {(mode === "login" || mode === "signup") && (
            <div className="auth-mode-tabs">
              <button
                type="button"
                className={`mode-tab ${mode === "login" ? "active" : ""}`}
                onClick={() => {
                  setMode("login");
                  setError(null);
                  setSuccess(null);
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`mode-tab ${mode === "signup" ? "active" : ""}`}
                onClick={() => {
                  setMode("signup");
                  setError(null);
                  setSuccess(null);
                }}
              >
                Create Account
              </button>
            </div>
          )}

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "signup" && (
              <div className="auth-field">
                <label>Full Name</label>
                <input
                  className="auth-input"
                  type="text"
                  required
                  placeholder="e.g. Piyush Agrawal"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
            )}

            {mode !== "reset" && (
              <div className="auth-field">
                <label>Email Address</label>
                <input
                  className="auth-input"
                  type="email"
                  required
                  placeholder="name@bank.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            )}

            {mode === "reset" && (
              <div className="auth-field">
                <label>Verification Reset Token</label>
                <input
                  className="auth-input"
                  type="text"
                  required
                  placeholder="Paste token received in email"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                />
              </div>
            )}

            {mode !== "forgot" && (
              <div className="auth-field">
                <div className="auth-label-row">
                  <label>{mode === "reset" ? "New Password" : "Password"}</label>
                  {mode === "login" && (
                    <button
                      type="button"
                      className="forgot-link"
                      onClick={() => {
                        setMode("forgot");
                        setError(null);
                        setSuccess(null);
                      }}
                    >
                      Forgot Password?
                    </button>
                  )}
                </div>
                <div className="auth-password">
                  <input
                    className="auth-input"
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    <EyeIcon off={showPassword} />
                  </button>
                </div>
              </div>
            )}

            {success && <div className="auth-message auth-success">{success}</div>}
            {error && <div className="auth-message auth-error">{error}</div>}

            <button type="submit" className="auth-submit-btn" disabled={loading}>
              {loading
                ? "Processing..."
                : mode === "signup"
                ? "Create Account"
                : mode === "login"
                ? "Sign In"
                : mode === "forgot"
                ? "Send Reset Link"
                : "Save New Password"}
            </button>
            {/* Google Authentication Section */}
            {(mode === "login" || mode === "signup") && (
              <div className="oauth-section">
                <div className="auth-divider">
                  <span className="divider-line"></span>
                  <span className="divider-text">Or continue with</span>
                  <span className="divider-line"></span>
                </div>
                <div className="google-btn-wrapper">
                  <div id="googleBtn"></div>
                </div>
              </div>
            )}
          </form>

          {mode === "login" && (
            <div className="auth-switch">
              <p>
                Don't have an account?{" "}
                <button
                  type="button"
                  className="auth-link"
                  onClick={() => {
                    setMode("signup");
                    setError(null);
                    setSuccess(null);
                  }}
                >
                  Create account
                </button>
              </p>
            </div>
          )}

          {mode === "signup" && (
            <div className="auth-switch">
              <p>
                Already have an account?{" "}
                <button
                  type="button"
                  className="auth-link"
                  onClick={() => {
                    setMode("login");
                    setError(null);
                    setSuccess(null);
                  }}
                >
                  Sign in
                </button>
              </p>
            </div>
          )}

          {(mode === "forgot" || mode === "reset") && (
            <div className="auth-switch">
              <button
                type="button"
                className="auth-link"
                onClick={() => {
                  setMode("login");
                  setError(null);
                  setSuccess(null);
                }}
              >
                ← Back to Sign In
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Login;
