/* Step 3 end-to-end: T-MIR runs in a real worker process (it must be running, see Backend/README.md).
   Upload → the run is queued → the worker plans and executes it → the browser sees it through live events
   (no reload) → every module is explained → a second run reuses the completed work → a notification exists. */
import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { execFileSync } from 'node:child_process';

const API = process.env.NEXTRON_API ?? 'http://localhost:8002/api/v1';
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

  const uploadedJob = (await queue.getByRole('link', { name: /JOB-\d+/ }).innerText()).trim();
  await queue.getByRole('link', { name: uploadedJob }).click();
  await expect(page.getByRole('heading', { level: 1, name: /^Analysis of EVD-\d+/ })).toBeAttached();
  await page.getByRole('button', { name: /Execution record/ }).click();  // the viewer keeps the execution tables one level down
  const modules = page.getByRole('region', { name: 'Modules for this evidence' });
  // arrives through the WebSocket: the page is not reloaded
  await expect(modules.getByRole('row', { name: /^NEX-MET / })).toContainText('Completed');
  await expect(modules.getByRole('row', { name: /^NEX-VID / })).toContainText('does not apply to this media');
  await expect(modules.getByRole('row', { name: /^NEX-AUD / })).toContainText('Skipped');
  await expect(modules.getByRole('row', { name: /^NEX-IMG / })).toContainText('Completed');  // measurement methods + detector
  await expect(modules.getByRole('row', { name: /^NEX-FPM / })).toContainText('Completed');  // fingerprints (Step 5)
  await expect(page.getByRole('region', { name: 'Findings' })).toContainText('Container and embedded metadata recorded');
  const runs = page.getByRole('region', { name: 'Runs for this evidence' });
  await expect(runs).toContainText(/Completed · 12 of 12 modules finished/)  // every module runs since Step 7 (EGC, REC built);
  await expect(page.getByRole('region', { name: 'Case-level modules of the latest run' })).toContainText('NEX-EGC');
  await shot(page, '19-evidence-analysis');

  await page.getByRole('link', { name: 'Metadata', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Extraction record' })).toContainText('pillow');

  // a second run: NEX-MET's inputs are unchanged, so its result is reused, not recomputed
  await page.getByRole('link', { name: 'Analysis', exact: true }).click();
  await page.getByRole('button', { name: /Execution record/ }).click();  // collapsed again on a fresh visit
  await page.getByRole('button', { name: 'Run analysis' }).click();
  await expect(runs.getByRole('listitem')).toHaveCount(2);
  await expect(runs.getByRole('listitem').first()).toContainText(/Completed/);

  await page.goto(`/investigations/${c.case_id}/analysis`);
  const plan = page.getByRole('region', { name: 'Latest run plan' });
  await expect(plan.getByRole('row', { name: /^NEX-MET / })).toContainText('result reused');
  await plan.getByRole('row', { name: /^NEX-MET / }).getByRole('button', { name: 'Result of NEX-MET' }).click();
  await expect(plan).toContainText('"schema_version": "1.0"');
  await shot(page, '20-case-analysis');

  await page.goto('/notifications');
  await page.getByRole('button', { name: /^Analysis/ }).click();  // run outcomes are not 'needs action'
  const grouped = page.getByRole('button', { name: /× completed/ });
  if (await grouped.count()) await grouped.first().click();  // consecutive completed runs are collapsed into one line
  await expect(page.locator('main')).toContainText(`${uploadedJob} completed`);
  await shot(page, '21-notifications');

  await page.goto('/system');
  await expect(page.getByRole('region', { name: 'Workers and job queue' })).toContainText('heartbeating');
  await expect(page.getByRole('region', { name: 'Workers and job queue' })).toContainText('connected');
  await shot(page, '22-system-workers');
});

/* A run that ends PARTIALLY_COMPLETED on any stack: a short video, because no evaluated video detector is installed
   (NEX-VID reports DETECTOR_NOT_INSTALLED). Made here with ffmpeg (FFMPEG_PATH or ffmpeg on PATH). */
async function partialRun(): Promise<{ job_id: string; job_number: string }> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'nextron-e2e-'));
  const clip = path.join(dir, 'clip.mp4');
  execFileSync(process.env.FFMPEG_PATH ?? 'ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=160x120:rate=10:duration=1',
    '-pix_fmt', 'yuv420p', '-c:v', 'libx264', clip]);
  const c = (await (await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] Retry ${Date.now()}` }) })).json()).data;
  const form = new FormData();
  form.append('file', new Blob([fs.readFileSync(clip)], { type: 'video/mp4' }), 'clip.mp4');
  const job = (await (await fetch(`${API}/cases/${c.case_id}/evidence`, { method: 'POST', body: form })).json()).data.analysis_job;
  fs.rmSync(dir, { recursive: true, force: true });
  await expect.poll(async () => (await (await fetch(`${API}/jobs/${job.job_id}`)).json()).data.state, { timeout: 90_000 }).toBe('PARTIALLY_COMPLETED');
  return job;
}

test('retrying a partial run from the job monitor queues a new job that the worker finishes', async ({ page }) => {
  test.setTimeout(150_000);
  const jobs = [await partialRun()];
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
  // the worker picks it up and reuses completed work; the video detector is still missing, so the retry ends partial too
  // and the drawer, following live events, lists it under "Needs attention"
  await expect.poll(async () => (await (await fetch(`${API}/jobs/${retried.job_id}`)).json()).data.state, { timeout: 60_000 }).toBe('PARTIALLY_COMPLETED');
  await expect(drawer.getByRole('region', { name: 'Jobs requiring attention' })).toContainText(retried.job_number);
  await shot(page, '16-job-monitor');
});
