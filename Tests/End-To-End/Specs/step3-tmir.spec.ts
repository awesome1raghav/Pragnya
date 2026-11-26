/* Step 3 end-to-end: T-MIR runs in a real worker process (it must be running, see Backend/README.md).
   Upload → the run is queued → the worker plans and executes it → the browser sees it through live events
   (no reload) → every module is explained → a second run reuses the completed work → a notification exists. */
import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

const API = process.env.NEXTRON_API ?? 'http://localhost:8000/api/v1';
const SHOTS = path.join(__dirname, '..', '..', 'Test Reports', 'End-To-End', 'Screenshots');
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

let problems: string[] = [];
test.beforeEach(async ({ page }) => {
  problems = [];
  page.on('pageerror', e => problems.push(`pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error' && !/status of 404/.test(m.text())) problems.push(`console: ${m.text()}`); });
});
test.afterEach(() => { expect(problems, problems.join('\n')).toEqual([]); });

async function pngBytes(page: Page) {
  const b64 = await page.evaluate(() => {
    const c = document.createElement('canvas'); c.width = 96; c.height = 64;
    const g = c.getContext('2d')!; g.fillStyle = '#365'; g.fillRect(0, 0, 96, 64); g.fillStyle = '#fc3'; g.fillRect(10, 10, 30, 20);
    return c.toDataURL('image/png').split(',')[1];
  });
  return Buffer.from(b64, 'base64');
}

test('a worker is registered before the run tests start', async () => {
  const w = await (await fetch(`${API}/system/workers`)).json();
  expect(w.data.alive, 'start one with: .venv\\Scripts\\python.exe -m Backend.App.Workers.Worker').toBeGreaterThan(0);
});

test('upload → worker runs T-MIR → live module states, reuse on re-run, notification', async ({ page }) => {
  const c = (await (await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] T-MIR still ${Date.now()}` }) })).json()).data;
  await page.goto(`/investigations/${c.case_id}/evidence/add`);
  await expect(page.getByRole('heading', { level: 1, name: 'Add evidence' })).toBeVisible();
  await expect(page.getByText(/MB per file/)).toBeVisible();  // the uploader is mounted and has read the storage limit
  await page.locator('input[type=file]').setInputFiles({ name: 'tmir-still.png', mimeType: 'image/png', buffer: await pngBytes(page) });
  await page.getByRole('button', { name: /Upload and preserve 1 file/ }).click();
  const queue = page.getByRole('region', { name: 'Upload queue' });
  await expect(queue).toContainText(/analysis JOB-\d+ queued/);

  await queue.getByRole('link', { name: /JOB-\d+/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Analysis' })).toBeVisible();
  const modules = page.getByRole('region', { name: 'Modules for this evidence' });
  // arrives through the WebSocket: the page is not reloaded
  await expect(modules.getByRole('row', { name: /^NEX-MET / })).toContainText('Completed');
  await expect(modules.getByRole('row', { name: /^NEX-VID / })).toContainText('does not apply to this media');
  await expect(modules.getByRole('row', { name: /^NEX-AUD / })).toContainText('Skipped');
  await expect(modules.getByRole('row', { name: /^NEX-IMG / })).toContainText('Partial');  // engine ran; no detector installed
  await expect(modules.getByRole('row', { name: /^NEX-FPM / })).toContainText('not built yet');
  await expect(page.getByRole('region', { name: 'Findings' })).toContainText('Container and embedded metadata recorded');
  const runs = page.getByRole('region', { name: 'Runs for this evidence' });
  await expect(runs).toContainText('Partially completed');
  await expect(page.getByRole('region', { name: 'Case-level modules of the latest run' })).toContainText('NEX-EGC');
  await shot(page, '19-evidence-analysis');

  await page.getByRole('link', { name: 'Metadata', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Extraction record' })).toContainText('pillow');

  // a second run: NEX-MET's inputs are unchanged, so its result is reused, not recomputed
  await page.getByRole('link', { name: 'Analysis', exact: true }).click();
  await page.getByRole('button', { name: 'Run analysis' }).click();
  await expect(runs.getByRole('listitem')).toHaveCount(2);
  await expect(runs.getByRole('listitem').first()).toContainText('Partially completed');

  await page.goto(`/investigations/${c.case_id}/analysis`);
  const plan = page.getByRole('region', { name: 'Latest run plan' });
  await expect(plan.getByRole('row', { name: /^NEX-MET / })).toContainText('result reused');
  await plan.getByRole('row', { name: /^NEX-MET / }).getByRole('button', { name: 'Result of NEX-MET' }).click();
  await expect(plan).toContainText('"schema_version": "1.0"');
  await shot(page, '20-case-analysis');

  await page.goto('/notifications');
  await expect(page.locator('main')).toContainText(/JOB-\d+ completed partially/);
  await shot(page, '21-notifications');

  await page.goto('/system');
  await expect(page.getByRole('region', { name: 'Workers and job queue' })).toContainText('heartbeating');
  await expect(page.getByRole('region', { name: 'Workers and job queue' })).toContainText('connected');
  await shot(page, '22-system-workers');
});

test('retrying a partial run from the job monitor queues a new job that the worker finishes', async ({ page }) => {
  const jobs = (await (await fetch(`${API}/jobs?state=PARTIALLY_COMPLETED&page_size=1`)).json()).data;
  expect(jobs.length, 'the previous test leaves a partially completed run').toBe(1);
  const before = (await (await fetch(`${API}/jobs?page_size=1`)).json()).pagination.total_items;
  await page.goto('/dashboard');
  await expect(page.getByRole('link', { name: /System status: System ready/ })).toBeVisible();
  await page.getByRole('button', { name: 'Open the job monitor' }).click();
  const drawer = page.getByRole('dialog', { name: 'Job monitor' });
  await drawer.getByRole('button', { name: `Retry ${jobs[0].job_number}` }).click();
  await expect(page.getByRole('status').filter({ hasText: /Queued JOB-\d+; completed work is reused/ })).toBeVisible();
  const after = (await (await fetch(`${API}/jobs?page_size=1`)).json());
  expect(after.pagination.total_items).toBe(before + 1);
  const retried = after.data[0];
  expect(retried.parameters.retry_of).toBe(jobs[0].job_id);
  // the worker picks it up; the drawer follows through live events
  await expect(drawer.getByRole('region', { name: 'Recent jobs' })).toContainText(retried.job_number);
  await shot(page, '16-job-monitor');
});
