import { defineConfig, devices } from "@playwright/test";

// Runs against the REAL FastAPI app (in-memory storage, synthetic fixture, no network).
export default defineConfig({
  testDir: "e2e-real",
  workers: 1,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:8765", ...devices["Pixel 7"] },
  webServer: {
    command: "npm run build && cd ../.. && uv run python scripts/serve_e2e.py",
    url: "http://127.0.0.1:8765/api/v1/health",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
