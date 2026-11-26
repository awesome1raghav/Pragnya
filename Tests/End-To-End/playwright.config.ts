import { defineConfig, devices } from '@playwright/test';

/* Runs against the real stack: the frontend on :8080 and the API on :8000 must already be running
   (see Backend/README.md and Frontend/Web/README.md). Nothing here mocks the API, except the one test
   that deliberately blocks it to check the unreachable state. */
export default defineConfig({
  testDir: './Specs',
  outputDir: '../Test Reports/End-To-End/Artifacts',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: '../Test Reports/End-To-End/Html', open: 'never' }]],
  use: {
    baseURL: process.env.NEXTRON_WEB ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
});
