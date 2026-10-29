import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("React ErrorBoundary caught error:", error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const isNetwork =
        this.state.error?.message?.toLowerCase().includes("fetch") ||
        this.state.error?.message?.toLowerCase().includes("network") ||
        this.state.error?.message?.toLowerCase().includes("connect");

      return (
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#f8fafc",
            padding: "20px",
            fontFamily: "system-ui, -apple-system, sans-serif",
          }}
        >
          <div
            style={{
              maxWidth: "480px",
              width: "100%",
              background: "#ffffff",
              padding: "36px 28px",
              borderRadius: "16px",
              boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
              textAlign: "center",
              border: "1px solid #e2e8f0",
            }}
          >
            <div
              style={{
                width: "56px",
                height: "56px",
                background: "#fee2e2",
                color: "#dc2626",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "26px",
                margin: "0 auto 16px",
              }}
            >
              ⚠️
            </div>
            <h2 style={{ fontSize: "20px", color: "#0f172a", margin: "0 0 8px", fontWeight: "700" }}>
              {isNetwork ? "Connection Unavailable" : "Something Went Wrong"}
            </h2>
            <p style={{ color: "#64748b", fontSize: "14px", lineHeight: "1.5", margin: "0 0 20px" }}>
              {this.state.error?.message ||
                "An unexpected rendering error occurred. Please verify your connection or reload the application."}
            </p>
            <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
              <button
                type="button"
                onClick={this.handleReload}
                style={{
                  background: "#0284c7",
                  color: "#ffffff",
                  border: "none",
                  padding: "10px 22px",
                  borderRadius: "8px",
                  fontWeight: "600",
                  fontSize: "14px",
                  cursor: "pointer",
                  boxShadow: "0 2px 6px rgba(2, 132, 199, 0.25)",
                }}
              >
                🔄 Reload Application
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
