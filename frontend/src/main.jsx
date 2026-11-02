import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import { ErrorBoundary } from "./ErrorBoundary.jsx";
import OfflineNotice from "./OfflineNotice.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ErrorBoundary>
      <OfflineNotice />
      <App />
    </ErrorBoundary>
  </StrictMode>
);
