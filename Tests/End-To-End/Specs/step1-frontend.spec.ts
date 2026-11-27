/* Step 1 acceptance: every route loads on real data, navigation and deep links work, the investigation
   workflow runs end to end through the UI, and failure states are honest. Screenshots of each main page
   are written to Tests/Test Reports/End-To-End/Screenshots. */
import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

const API = process.env.NEXTRON_API ?? 'http://localhost:8002/api/v1';
const SHOTS = path.join(__dirname, '..', '..', 'Test Reports', 'End-To-End', 'Screenshots');
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

/* collect uncaught page errors and console errors for each test */
let problems: string[] = [];
test.beforeEach(async ({ page }) => {
  problems = [];
  page.on('pageerror', e => problems.push(`pageerror: ${e.message}`));
  page.on('console', m => {
    if (m.type() !== 'error') return;
    const t = m.text();
    if (/Failed to load resource: the server responded with a status of 404/.test(t)) return; // checked per test where it matters
    problems.push(`console: ${t}`);
  });
});
test.afterEach(() => { expect(problems, problems.join('\n')).toEqual([]); });

async function apiCase(title: string) {
  const res = await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] ${title}`, category: 'MEDIA_MANIPULATION', priority: 'HIGH' }) });
  expect(res.status).toBe(201);
  return (await res.json()).data as { case_id: string; case_number: string };
}

async function pngBytes(page: Page, label: string) {
  const b64 = await page.evaluate(l => {
    const c = document.createElement('canvas'); c.width = 240; c.height = 160;
    const g = c.getContext('2d')!; g.fillStyle = '#20406a'; g.fillRect(0, 0, 240, 160); g.fillStyle = '#e9a23b'; g.fillRect(20, 20, 120, 60);
    g.fillStyle = '#fff'; g.font = '16px sans-serif'; g.fillText(l, 20, 130);
    return c.toDataURL('image/png').split(',')[1];
  }, label);
  return Buffer.from(b64, 'base64');
}

test('the root shows the landing page, which leads into the application', async ({ page }) => {
  const res = await page.goto('/');
  expect(res?.status()).toBe(200);
  expect(new URL(page.url()).pathname).toBe('/');
  await expect(page.getByRole('heading', { level: 1, name: /Seeing isn.t believing/ })).toBeVisible();
  await page.goto('/about');
  await expect(page.getByRole('heading', { level: 1, name: /Seeing isn.t believing/ })).toBeVisible();
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible();
});

const ROUTES: [string, string][] = [
  ['/dashboard', 'Dashboard'], ['/investigations', 'Investigations'], ['/investigations/active', 'Investigations'],
  ['/investigations/completed', 'Investigations'], ['/investigations/archived', 'Investigations'], ['/investigations/new', 'New investigation'],
  ['/evidence', 'Evidence'], ['/sources', 'Sources'], ['/lineage', 'Lineage'], ['/intelligence', 'Intelligence'], ['/graph', 'Evidence graph'],
  ['/reports', 'Reports'], ['/notifications', 'Notifications'], ['/system', 'System'], ['/system/health', 'Health checks'], ['/system/logs', 'Logs'], ['/settings', 'Settings'],
];

test('every application route loads with its heading and no errors', async ({ page }) => {
  for (const [url, heading] of ROUTES) {
    const res = await page.goto(url);
    expect(res?.status(), url).toBe(200);
    await expect(page.getByRole('heading', { level: 1, name: heading }), url).toBeVisible();
    await expect(page.locator('main [role=alert]'), `${url} shows no error`).toHaveCount(0); // (Next.js's route announcer also has role=alert, outside main)
  }
  for (const [url, name] of [['/dashboard', '01-dashboard'], ['/investigations', '02-investigations'], ['/investigations/new', '03-new-investigation'], ['/evidence', '06-evidence'], ['/sources', '08-sources'], ['/lineage', '09-lineage'], ['/intelligence', '07-intelligence'], ['/graph', '10-graph'], ['/reports', '11-reports'], ['/notifications', '12-notifications'], ['/system', '13-system'], ['/settings', '14-settings']] as const) {
    await page.goto(url);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await page.waitForLoadState('networkidle');
    await shot(page, name);
  }
});

test('global navigation has the eleven destinations and keeps the investigation in scoped links', async ({ page }) => {
  const c = await apiCase(`Nav scope ${Date.now()}`);
  await page.goto(`/investigations/${c.case_id}`);
  const nav = page.getByRole('complementary', { name: 'Workspace navigation' });
  const labels = ['Dashboard', 'Investigations', 'Evidence', 'Sources', 'Lineage', 'Intelligence', 'Evidence graph', 'Reports', 'Notifications', 'System', 'Settings'];
  for (const l of labels) await expect(nav.getByRole('link', { name: l, exact: true })).toBeVisible();
  for (const l of ['Evidence', 'Sources', 'Lineage', 'Intelligence', 'Evidence graph', 'Reports']) {
    await expect(nav.getByRole('link', { name: l, exact: true })).toHaveAttribute('href', new RegExp(`\\?case=${c.case_id}$`));
  }
  await nav.getByRole('link', { name: 'Sources', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/sources\\?case=${c.case_id}$`));
  await expect(page.getByRole('group', { name: 'Investigation scope' })).toContainText(c.case_number);
  await page.getByRole('button', { name: 'Show all investigations' }).click();
  await expect(page).toHaveURL(/\/sources$/);
  await expect(page.getByText('Last opened:')).toContainText(c.case_number); // offered, not applied
});

test('create an investigation, upload evidence, inspect metadata, verify integrity, follow custody', async ({ page }) => {
  const title = `[E2E] harbour still ${Date.now()}`;
  await page.goto('/investigations/new');
  await page.getByRole('button', { name: 'Create investigation' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'A title is required' })).toBeVisible();
  await page.getByPlaceholder('e.g. Viral clip of the harbour fire').fill(title);
  await page.getByRole('textbox', { name: /Objectives/ }).fill('Establish whether the still was edited');
  await page.getByRole('combobox', { name: /Category/ }).selectOption('MEDIA_MANIPULATION');
  await page.getByRole('button', { name: 'Create investigation' }).click();
  await expect(page).toHaveURL(/\/investigations\/[0-9a-f-]{36}\/evidence\/add$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Add evidence' })).toBeVisible();

  const png = await pngBytes(page, 'e2e');
  await page.locator('input[type=file]').setInputFiles({ name: 'harbour-still.png', mimeType: 'image/png', buffer: png });
  await page.getByRole('button', { name: /Upload and preserve 1 file/ }).click();
  const queue = page.getByRole('region', { name: 'Upload queue' });
  await expect(queue).toContainText('matches the hash computed in this browser');
  await expect(queue).toContainText(/analysis JOB-\d+ queued/);  // metadata is extracted by the worker (T-MIR), not in the upload
  await shot(page, '05-add-evidence-done');

  await queue.getByRole('link', { name: /EVD-\d+/ }).click();
  await expect(page).toHaveURL(/\/evidence\/[0-9a-f-]{36}$/);
  await expect(page.getByRole('img', { name: /Preserved original harbour-still.png/ })).toBeVisible();
  await shot(page, '06b-evidence-overview');

  await page.getByRole('link', { name: 'Metadata', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Metadata' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Extraction record' })).toContainText('pillow');
  await expect(page.locator('main')).toContainText('240');

  await page.getByRole('link', { name: 'Integrity', exact: true }).click();
  await expect(page.getByText('Not re-verified since preservation.')).toBeVisible();
  await page.getByRole('button', { name: 'Verify integrity now' }).click();
  await expect(page.getByRole('region', { name: 'Latest verification' })).toContainText('Stored bytes match the recorded SHA-256');
  await shot(page, '06c-evidence-integrity');

  await page.getByRole('link', { name: 'Custody timeline' }).click();
  for (const step of ['Evidence received', 'SHA-256 computed on the server', 'Original preserved, read-only', 'Metadata extracted', 'Integrity verified: bytes match']) {
    await expect(page.locator('main')).toContainText(step);
  }

  // refresh and deep link keep the same record; back and forward work
  await page.reload();
  await expect(page.locator('main')).toContainText('Integrity verified: bytes match');
  await page.goBack();
  await expect(page.getByRole('heading', { level: 1, name: 'Integrity' })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading', { level: 1, name: 'Custody timeline' })).toBeVisible();

  // the investigation workspace reflects the upload
  await page.getByRole('link', { name: /CASE-\d+ · \[E2E\] harbour still/ }).first().click();
  await expect(page.getByRole('region', { name: 'Evidence overview' })).toContainText('harbour-still.png');
  await expect(page.locator('header').getByText('Collecting evidence').first()).toBeVisible();
  await shot(page, '04-investigation-workspace');
});

test('investigator notes save and archive / reopen follow the lifecycle', async ({ page }) => {
  const c = await apiCase(`Lifecycle ${Date.now()}`);
  await page.goto(`/investigations/${c.case_id}`);
  const notes = page.getByRole('region', { name: 'Investigator notes' });
  await notes.getByRole('button', { name: 'Edit' }).click();
  await notes.getByRole('textbox', { name: 'Investigator notes' }).fill('Called the uploader; original phone unavailable.');
  await notes.getByRole('button', { name: 'Save notes' }).click();
  await expect(notes).toContainText('Called the uploader');

  await page.getByRole('button', { name: 'Archive' }).click();
  await page.getByRole('dialog', { name: 'Archive this investigation' }).getByRole('textbox').fill('duplicate report');
  await page.getByRole('button', { name: 'Archive investigation' }).click();
  await expect(page.locator('header').getByText('Archived', { exact: true }).first()).toBeVisible();
  await expect(notes.getByRole('button', { name: 'Edit' })).toHaveCount(0); // read-only while archived
  await page.getByRole('button', { name: 'Reopen' }).click();
  await expect(page.locator('header').getByText('Open', { exact: true }).first()).toBeVisible();

  await page.getByRole('link', { name: 'Events', exact: true }).click();
  for (const e of ['Investigation created', 'Investigation details updated', 'Investigation archived', 'Investigation reopened']) await expect(page.locator('main')).toContainText(e);
});

test('search finds investigations and evidence through the API', async ({ page }) => {
  const c = await apiCase(`Searchable ${Date.now()}`);
  await page.goto('/dashboard');
  await expect(page.getByRole('link', { name: /System status: System ready/ })).toBeVisible(); // hydrated and talking to the API
  await page.keyboard.press('Control+K');
  const dialog = page.getByRole('dialog', { name: 'Search and commands' });
  await dialog.getByRole('combobox', { name: 'Search' }).fill(c.case_number);
  await expect(dialog.getByRole('option', { name: /Searchable/ })).toBeVisible();
  await expect(dialog).toContainText('Searched case, evidence, source, finding, report, review');  // Step 8: every stored type
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(new RegExp(`/investigations/${c.case_id}$`));
});

test('unknown and malformed addresses answer honestly', async ({ page }) => {
  await page.goto('/investigations/00000000-0000-4000-8000-000000000000');
  await expect(page.getByText('No investigation at this address')).toBeVisible();
  expect((await page.goto('/investigations/not-a-uuid'))?.status()).toBe(404); // malformed IDs never reach the API
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  expect((await page.goto('/evidence/EV-0149'))?.status()).toBe(404);
  await page.goto('/evidence/00000000-0000-4000-8000-000000000000');
  await expect(page.getByText('No evidence at this address')).toBeVisible();
  const c = await apiCase(`Branch check ${Date.now()}`);
  expect((await page.goto(`/investigations/${c.case_id}/analysis/spectral`))?.status()).toBe(404);
  expect((await page.goto(`/investigations/${c.case_id}/analysis/video`))?.status()).toBe(200);
  await expect(page.locator('main')).toContainText('No evidence NEX-VID applies to');  // a real, empty engine view
  expect((await page.goto('/reports/anything'))?.status()).toBe(404);
  expect((await page.goto('/no-such-page'))?.status()).toBe(404);
});

test('when the API is unreachable the UI says so and shows no data', async ({ page }) => {
  await page.route(`${API}/**`, r => r.abort('connectionrefused'));
  await page.goto('/dashboard');
  await expect(page.getByRole('alert').filter({ hasText: 'The NEXTRON API is unreachable' }).first()).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'API unreachable' })).toBeVisible();
  await shot(page, '15-api-unreachable');
  await page.goto('/investigations');
  await expect(page.getByRole('alert').filter({ hasText: 'unreachable' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: /CASE-\d{4}/ })).toHaveCount(0);
  problems = problems.filter(p => !/ERR_CONNECTION_REFUSED|Failed to load resource/.test(p)); // the blocked requests themselves
});

test('job monitor lists real jobs from the Job API', async ({ page }) => {
  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Open the job monitor' }).click();
  const drawer = page.getByRole('dialog', { name: 'Job monitor' });
  await expect(drawer.getByRole('region', { name: 'Recent jobs' })).toContainText(/JOB-\d+ · Investigation run/);
  await expect(drawer).toContainText(/worker(s)? running/);
  await shot(page, '16-job-monitor');
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
});
