import { defineConfig, devices } from "@playwright/test";

// The e2e tests run against the dev server with the in-memory mock API. Never real services.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: { baseURL: "http://localhost:4173", ...devices["Pixel 7"] },
  webServer: {
    command: "npx vite --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: false,
    env: { VITE_MOCK_API: "1" },
  },
});
