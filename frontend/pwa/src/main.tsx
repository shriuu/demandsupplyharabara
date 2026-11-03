import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

async function start() {
  // Dev and e2e only: an in-memory API. Dropped from production builds.
  if (import.meta.env.VITE_MOCK_API === "1") {
    const { installMockFetch } = await import("./mock/handlers");
    installMockFetch();
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void start();
