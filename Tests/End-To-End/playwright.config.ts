import { defineConfig, devices } from '@playwright/test';

/* Runs against a real but isolated stack: start it with Scripts/Testing/StartE2EStack.ps1 (web :8090, API :8002,
   database nextron_e2e), so the tests never write into the operator's investigations. NEXTRON_WEB and NEXTRON_API
   override the addresses. Nothing here mocks the API, except the tests that deliberately block or fake a response. */
process.env.NEXTRON_API ??= 'http://localhost:8002/api/v1';
export default defineConfig({
  testDir: './Specs',
  outputDir: '../Test Reports/End-To-End/Artifacts',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: '../Test Reports/End-To-End/Html', open: 'never' }]],
  use: {
    baseURL: process.env.NEXTRON_WEB ?? 'http://localhost:8090',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
});
