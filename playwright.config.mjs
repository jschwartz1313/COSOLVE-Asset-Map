import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:8002",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile-chromium",
      use: { ...devices["iPhone 13"], browserName: "chromium" },
    },
  ],
  webServer: {
    command: `${process.env.CI ? "python" : ".venv/bin/python"} manage.py runserver 127.0.0.1:8002 --noreload`,
    url: "http://127.0.0.1:8002/health/",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
