import { useEffect, useRef, useState } from "react";
import { forgotPassword, login, loginWithGoogle, resetPassword, saveToken, signup, verifyEmail } from "./api";
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

function Login({ onLoggedIn, initialMode = "login", _onClose = null }) {
  const [mode, setMode] = useState(initialMode);
  useEffect(() => {
    if (initialMode) setMode(initialMode);
  }, [initialMode]); // "login", "signup", "forgot", "reset"
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [turnstileToken, setTurnstileToken] = useState("");
  const turnstileRef = useRef(null);
  const widgetIdRef = useRef(null);

  // Progressive feedback for loading states
  useEffect(() => {
    let t1, t2;
    if (loading) {
      t1 = setTimeout(() => {
        setLoadingMessage((prev) => `${prev || "Connecting"} (Please hold on...)`);
      }, 4500);
      t2 = setTimeout(() => {
        setLoadingMessage("Connecting securely, please wait a moment...");
      }, 11000);
    }
    return () => {
      if (t1) clearTimeout(t1);
      if (t2) clearTimeout(t2);
    };
  }, [loading]);

  function resetTurnstile() {
    setTurnstileToken("");
    if (widgetIdRef.current !== null && window.turnstile) {
      try {
        window.turnstile.reset(widgetIdRef.current);
      } catch (e) {
        // ignore
      }
    }
  }

  useEffect(() => {
    if (mode !== "login" && mode !== "signup") return;

    const siteKey =
      import.meta.env.VITE_TURNSTILE_SITE_KEY || "0x4AAAAAAFmhQvy4ckiwTVO5";

    let retryTimer = null;
    let attempts = 0;

    function renderTurnstile() {
      if (!turnstileRef.current) return;

      if (window.turnstile) {
        try {
          if (widgetIdRef.current !== null) {
            try {
              window.turnstile.remove(widgetIdRef.current);
            } catch (e) {
              // ignore
            }
            widgetIdRef.current = null;
          }

          widgetIdRef.current = window.turnstile.render(turnstileRef.current, {
            sitekey: siteKey,
            theme: "light",
            callback: (token) => {
              setTurnstileToken(token);
              setError(null);
            },
            "expired-callback": () => {
              setTurnstileToken("");
            },
            "error-callback": () => {
              console.warn("Turnstile challenge issue.");
            },
          });
        } catch (e) {
          console.error("Turnstile render error:", e);
        }
      } else if (attempts < 50) {
        attempts++;
        retryTimer = setTimeout(renderTurnstile, 100);
      }
    }

    setTurnstileToken("");
    renderTurnstile();

    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      if (widgetIdRef.current !== null && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch (e) {
          // ignore
        }
        widgetIdRef.current = null;
      }
    };
  }, [mode]);

  const passwordChecks = {
    minLength: password.length >= 8,
    hasUpper: /[A-Z]/.test(password),
    hasLower: /[a-z]/.test(password),
    hasDigit: /[0-9]/.test(password),
    hasSpecial: /[^A-Za-z0-9]/.test(password),
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("reset_token") || params.get("token");
    if (token) {
      setResetToken(token);
      setMode("reset");
    }

    const verifyToken = params.get("verify_email");
    if (verifyToken) {
      setLoading(true);
      setLoadingMessage("Verifying email activation link...");
      setError(null);
      setSuccess(null);
      verifyEmail(verifyToken)
        .then((res) => {
          setSuccess(res.message || "Email successfully verified! Your account is active. Please sign in.");
          setMode("login");
          window.history.replaceState({}, document.title, window.location.pathname);
        })
        .catch((err) => {
          setError(err.message || "Email verification failed or link expired.");
        })
        .finally(() => setLoading(false));
    }
  }, []);

  async function handleGoogleSuccess(response) {
    if (!response || !response.credential) {
      console.warn("No credential in Google response:", response);
      return;
    }
    setLoading(true);
    setLoadingMessage("Verifying Google account... Please wait");
    setError(null);
    try {
      console.log("Google callback received credential: YES");
      const data = await loginWithGoogle(response.credential);
      if (!data || !data.access_token) {
        throw new Error("Login failed: missing access token from server.");
      }
      saveToken(data.access_token);
      onLoggedIn(data.user);
    } catch (err) {
      console.error("Google Login Backend Error:", err);
      setError(err.message || "Google Login failed. Please try again or sign in with email.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let retryTimer = null;
    let attempts = 0;

    function renderGoogleBtn() {
      if (mode !== "login" && mode !== "signup") return;

      const googleClientId =
        import.meta.env.VITE_GOOGLE_CLIENT_ID ||
        "639319834126-b1ouen3no25o2elim13idbab182m3tjd.apps.googleusercontent.com";

      if (!window.google || !window.google.accounts || !window.google.accounts.id) {
        if (attempts < 50) {
          attempts++;
          retryTimer = setTimeout(renderGoogleBtn, 100);
        }
        return;
      }

      const btnContainer = document.getElementById("googleBtn");
      if (!btnContainer) {
        if (attempts < 50) {
          attempts++;
          retryTimer = setTimeout(renderGoogleBtn, 50);
        }
        return;
      }

      try {
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          callback: handleGoogleSuccess,
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        // Disable automatic one-tap credential caching so user can always choose accounts
        window.google.accounts.id.disableAutoSelect();

        btnContainer.innerHTML = "";
        const targetWidth = Math.min(380, btnContainer.offsetWidth || 360);
        window.google.accounts.id.renderButton(btnContainer, {
          theme: "outline",
          size: "large",
          width: targetWidth,
          text: "continue_with",
          shape: "rectangular",
          logo_alignment: "left",
        });
      } catch (e) {
        console.error("Google Auth render error:", e);
      }
    }

    renderGoogleBtn();

    return () => {
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [mode]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Client-side validation with specific, real error messages
    if (mode === "signup" && !fullName.trim()) {
      setError("Please enter your full name.");
      return;
    }

    if (mode !== "reset") {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!email.trim() || !emailRegex.test(email.trim())) {
        setError("Please enter a valid email address (e.g. name@bank.com).");
        return;
      }
    }

    if (mode === "reset" && !resetToken.trim()) {
      setError("Please enter the verification reset token.");
      return;
    }

    if (mode === "signup" || mode === "reset") {
      if (!passwordChecks.minLength) {
        setError("Password must be at least 8 characters long.");
        return;
      }
      if (!passwordChecks.hasUpper) {
        setError("Password must contain at least one uppercase letter (A-Z).");
        return;
      }
      if (!passwordChecks.hasLower) {
        setError("Password must contain at least one lowercase letter (a-z).");
        return;
      }
      if (!passwordChecks.hasDigit) {
        setError("Password must contain at least one number (0-9).");
        return;
      }
      if (!passwordChecks.hasSpecial) {
        setError("Password must contain at least one special character (!@#$%^&*...).");
        return;
      }
    }

    if ((mode === "login" || mode === "signup") && !turnstileToken) {
      setError("Please complete the Cloudflare security verification.");
      return;
    }

    setLoading(true);

    try {
      if (mode === "signup") {
        setLoadingMessage("Creating your bank desk account...");
        const res = await signup(email, password, fullName, turnstileToken);

        if (!res.email_sent && res.dev_verification_link) {
          try {
            const htmlContent = `
              <div style="font-family: Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px;">
                <div style="max-width: 520px; margin: 0 auto; background: white; padding: 24px; border-radius: 10px; border: 1px solid #e2e8f0;">
                  <h2 style="color: #0284c7; margin-top: 0;">Bank Complaint AI Desk</h2>
                  <p>Hello <strong>${fullName || "Bank Associate"}</strong>,</p>
                  <p>Thank you for registering. Please click the button below to verify your email address and activate your banking desk account:</p>
                  <p style="text-align: center; margin: 28px 0;">
                    <a href="${res.dev_verification_link}" style="background-color: #0284c7; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                      Confirm Email Address
                    </a>
                  </p>
                  <p style="color: #64748b; font-size: 13px;">This confirmation link will expire in 24 hours.</p>
                </div>
              </div>`;
            await fetch("/api/send-email", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                to_email: email,
                subject: "Confirm Your Account - Bank Complaint AI Desk",
                html: htmlContent,
                text: `Please verify your account: ${res.dev_verification_link}`,
              }),
            });
          } catch (e) {
            console.warn("Client fallback email dispatch:", e);
          }
        }

        setMode("login");
        setPassword("");
        setFullName("");
        setEmail("");
        setSuccess(res.message || "Account created successfully! A confirmation email has been sent to your inbox.");
      } else if (mode === "login") {
        setLoadingMessage("Signing in... Verifying credentials...");
        const result = await login(email, password, turnstileToken);
        saveToken(result.access_token);
        onLoggedIn(result.user);
      } else if (mode === "forgot") {
        setLoadingMessage("Sending password reset instructions...");
        const res = await forgotPassword(email);
        setSuccess(
          res.message || "If this email is registered, a password reset link has been issued. Please check your inbox (and spam folder) to set your new password."
        );
        setEmail("");
      } else if (mode === "reset") {
        setLoadingMessage("Updating and securing your password...");
        const res = await resetPassword(resetToken, password);
        setMode("login");
        setPassword("");
        setResetToken("");
        setSuccess(res.message || "Password updated successfully! You can now sign in with your new password.");
      }
    } catch (err) {
      resetTurnstile();
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      {/* POPUP HEADER / NAVBAR */}
      <div className="auth-popup-header">
        <div className="auth-popup-brand">
          <div className="auth-popup-logo">
            <IconShield size={20} />
          </div>
          <div className="auth-popup-brand-text">
            <span className="auth-popup-title">Bank Complaint Desk</span>
            <span className="auth-popup-subtitle">Enterprise Portal</span>
          </div>
        </div>
      </div>

      {/* AUTH FORM CARD */}
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
                : "Create a new strong password for your account"}
            </p>
          </div>

          {/* Active Loading Overlay with Professional Spinner */}
          {loading && (
            <div className="auth-loading-overlay">
              <div className="auth-spinner-box">
                <div className="auth-spinner-ring"></div>
                <p className="auth-spinner-title">{loadingMessage || "Please wait..."}</p>
                <span className="auth-spinner-sub">Securing your session, please wait</span>
              </div>
            </div>
          )}

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
                  setEmail("");
                  setPassword("");
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
                  setEmail("");
                  setPassword("");
                  setFullName("");
                }}
              >
                Create Account
              </button>
            </div>
          )}

          <form className="auth-form" onSubmit={handleSubmit} autoComplete="off">
            {/* Decoy hidden inputs to prevent aggressive browser autofill */}
            <input type="text" style={{ display: "none" }} tabIndex="-1" aria-hidden="true" autoComplete="off" />
            <input type="password" style={{ display: "none" }} tabIndex="-1" aria-hidden="true" autoComplete="off" />

            {/* Google Authentication Section (Above manual form fields) */}
            {(mode === "login" || mode === "signup") && (
              <div className="oauth-top-section">
                <div className="google-btn-wrapper">
                  <button type="button" className="custom-google-btn" tabIndex="-1" aria-hidden="true">
                    <svg className="google-svg-icon" viewBox="0 0 24 24" width="20" height="20">
                      <path
                        fill="#4285F4"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                      />
                    </svg>
                    <span>Continue with Google</span>
                  </button>
                  <div id="googleBtn" className="google-btn-hidden-overlay"></div>
                </div>
                <div className="auth-divider">
                  <span className="divider-line"></span>
                  <span className="divider-text">Or enter credentials manually</span>
                  <span className="divider-line"></span>
                </div>
              </div>
            )}

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
                  autoComplete="off"
                  name="complaint_desk_fullname"
                  spellCheck="false"
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
                  autoComplete="off"
                  readOnly
                  onFocus={(e) => e.target.removeAttribute("readonly")}
                  name="clean_email_field"
                  id="clean_email_field"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck="false"
                />
              </div>
            )}

            {mode === "reset" && !resetToken && (
              <div className="auth-field">
                <label>Verification Reset Token</label>
                <input
                  className="auth-input"
                  type="text"
                  required
                  placeholder="Paste token received in email"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  autoComplete="off"
                  name="complaint_desk_token"
                  spellCheck="false"
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
                    autoComplete="new-password"
                    readOnly
                    onFocus={(e) => e.target.removeAttribute("readonly")}
                    name="clean_password_field"
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

                {(mode === "signup" || mode === "reset") && password.length > 0 && (
                  <div className="password-rules-box">
                    <div className="password-rules-header">Password Requirements:</div>
                    <div className="password-rules-list">
                      <div className={`rule-row ${passwordChecks.minLength ? "rule-met" : "rule-unmet"}`}>
                        <span className="rule-badge">{passwordChecks.minLength ? "✓" : "✕"}</span>
                        <span className="rule-text">At least 8 characters</span>
                      </div>
                      <div className={`rule-row ${passwordChecks.hasUpper ? "rule-met" : "rule-unmet"}`}>
                        <span className="rule-badge">{passwordChecks.hasUpper ? "✓" : "✕"}</span>
                        <span className="rule-text">At least one uppercase letter (A-Z)</span>
                      </div>
                      <div className={`rule-row ${passwordChecks.hasLower ? "rule-met" : "rule-unmet"}`}>
                        <span className="rule-badge">{passwordChecks.hasLower ? "✓" : "✕"}</span>
                        <span className="rule-text">At least one lowercase letter (a-z)</span>
                      </div>
                      <div className={`rule-row ${passwordChecks.hasDigit ? "rule-met" : "rule-unmet"}`}>
                        <span className="rule-badge">{passwordChecks.hasDigit ? "✓" : "✕"}</span>
                        <span className="rule-text">At least one number (0-9)</span>
                      </div>
                      <div className={`rule-row ${passwordChecks.hasSpecial ? "rule-met" : "rule-unmet"}`}>
                        <span className="rule-badge">{passwordChecks.hasSpecial ? "✓" : "✕"}</span>
                        <span className="rule-text">At least one special character (!@#$%^&*)</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {(mode === "login" || mode === "signup") && (
              <div className="turnstile-container">
                <div ref={turnstileRef} className="turnstile-slot"></div>
              </div>
            )}

            {success && <div className="auth-message auth-success">{success}</div>}
            {error && <div className="auth-message auth-error">{error}</div>}

            <button type="submit" className="auth-submit-btn" disabled={loading}>
              {loading ? (
                <span className="btn-loading-content">
                  <span className="btn-spinner-icon"></span>
                  <span>{loadingMessage || "Processing..."}</span>
                </span>
              ) : mode === "signup" ? (
                "Create Account"
              ) : mode === "login" ? (
                "Sign In"
              ) : mode === "forgot" ? (
                "Send Reset Link"
              ) : (
                "Save New Password"
              )}
            </button>
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
                    setEmail("");
                    setPassword("");
                    setFullName("");
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
                    setEmail("");
                    setPassword("");
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
                  setEmail("");
                  setPassword("");
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
