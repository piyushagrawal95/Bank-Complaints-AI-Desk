import { useEffect, useState } from "react";
import { IconCheck, IconRefresh, IconWifiOff } from "./Icons";
import "./OfflineNotice.css";

export default function OfflineNotice() {
  const [isOffline, setIsOffline] = useState(() => (typeof navigator !== "undefined" ? !navigator.onLine : false));
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [justRestored, setJustRestored] = useState(false);

  useEffect(() => {
    function handleOffline() {
      setIsOffline(true);
      setJustRestored(false);
    }

    function handleOnline() {
      setIsOffline(false);
      setJustRestored(true);
      const timer = setTimeout(() => {
        setJustRestored(false);
      }, 3500);
      return () => clearTimeout(timer);
    }

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  const handleRetry = () => {
    setIsReconnecting(true);
    // Smooth visual feedback before reload
    setTimeout(() => {
      window.location.reload();
    }, 350);
  };

  if (!isOffline && !justRestored) {
    return null;
  }

  return (
    <>
      <div className={`offline-top-stripe ${justRestored ? "stripe-restored" : ""}`} />
      <aside className="offline-notice-wrapper" role="alert" aria-live="assertive">
        {justRestored ? (
          <div className="offline-notice-card restored-card">
            <div className="offline-notice-icon-circle success-circle">
              <IconCheck size={20} />
            </div>
            <div className="offline-notice-content">
              <h4 className="offline-notice-title" style={{ color: "#166534" }}>
                Connection Restored
              </h4>
              <p className="offline-notice-desc">
                Your internet connection is back online.
              </p>
            </div>
          </div>
        ) : (
          <div className="offline-notice-card">
            <div className="offline-notice-icon-circle danger-circle">
              <IconWifiOff size={22} />
            </div>
            <div className="offline-notice-content">
              <div className="offline-notice-header">
                <span className="offline-status-badge">No Connection</span>
                <h4 className="offline-notice-title">You are not connected to Internet</h4>
              </div>
              <p className="offline-notice-desc">
                Please check your Wi-Fi, Ethernet, or mobile data and try again.
              </p>
            </div>
            <div className="offline-notice-actions">
              <button
                type="button"
                className="offline-retry-btn"
                onClick={handleRetry}
                disabled={isReconnecting}
                title="Reload and retry connection"
              >
                <IconRefresh size={16} className={isReconnecting ? "offline-spin" : ""} />
                <span>{isReconnecting ? "Reconnecting..." : "Retry"}</span>
              </button>
            </div>
          </div>
        )}
      </aside>
    </>
  );
}
