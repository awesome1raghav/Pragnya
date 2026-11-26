/* Step 8 end-to-end, "multi-tab reconnect and reconciliation":
   - two tabs on Settings: a save in one appears in the other through live events; a save based on an old version is
     refused and the form shows what is stored;
   - a tab whose live connection drops says it is reconnecting, resumes with ?after=<last sequence>, and shows what
     changed while it was disconnected;
   - global search reaches sources and reviews. Preferences are restored afterwards. */
import { expect, test, type Page, type WebSocketRoute } from '@playwright/test';

const API = process.env.NEXTRON_API ?? 'http://localhost:8000/api/v1';

let problems: string[] = [];
const watch = (page: Page) => {
  page.on('pageerror', e => problems.push(`pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error' && !/status of (404|409|422)|WebSocket/.test(m.text())) problems.push(`console: ${m.text()}`); });
};
test.beforeEach(() => { problems = []; });
test.afterEach(async () => {
  const cur = (await (await fetch(`${API}/preferences`)).json()).data;  // leave the stored preferences as defaults
  if (cur.version > 0) await fetch(`${API}/preferences`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version: cur.version, preferences: {
    notifications: { runs_completed: true, runs_partial: true, runs_failed: true, runs_cancelled: true, sources: true, reports: true },
    analysis: { auto_analyze_on_upload: null }, reports: { default_download: 'pdf' } } }) });
  expect(problems, problems.join('\n')).toEqual([]);
});

test('two tabs stay in step on Settings, and a stale save is refused', async ({ context }) => {
  const a = await context.newPage(), b = await context.newPage();
  watch(a); watch(b);
  await a.goto('/settings'); await b.goto('/settings');
  const box = (p: Page) => p.getByRole('region', { name: 'Preferences' }).getByRole('checkbox', { name: 'An analysis run completed' });
  await expect(box(a)).toBeChecked(); await expect(box(b)).toBeChecked();

  await box(a).uncheck();
  await a.getByRole('button', { name: 'Save preferences' }).click();
  await expect(a.getByRole('region', { name: 'Preferences' })).toContainText(/version \d+/);
  await expect(box(b)).not.toBeChecked({ timeout: 15_000 });  // arrived in the other tab through preferences.updated

  // B starts an edit; A saves something else first; B's save is refused and B shows the stored document
  await b.getByRole('combobox', { name: 'Default report download' }).selectOption('json');
  await a.getByRole('checkbox', { name: 'A run failed' }).uncheck();
  await a.getByRole('button', { name: 'Save preferences' }).click();
  await expect(b.getByRole('region', { name: 'Preferences' })).toContainText('changed in another tab', { timeout: 15_000 });
  await b.getByRole('button', { name: 'Save preferences' }).click();
  await expect(b.getByRole('region', { name: 'Preferences' }).getByRole('alert')).toContainText('saved preferences first');
  await expect(b.getByRole('checkbox', { name: 'A run failed' })).not.toBeChecked();
  await expect(b.getByRole('combobox', { name: 'Default report download' })).toHaveValue('pdf');
});

test('a dropped live connection reconnects, resumes after its last event and shows what it missed', async ({ page }) => {
  watch(page);
  const sockets: WebSocketRoute[] = [];
  const urls: string[] = [];
  await page.routeWebSocket(/\/ws\/events/, ws => { urls.push(ws.url()); sockets.push(ws); ws.connectToServer(); });
  await page.goto('/investigations');
  await expect(page.getByRole('link', { name: /System status: System ready/ })).toBeVisible();
  await expect.poll(() => sockets.length).toBeGreaterThan(0);
  await page.waitForTimeout(1000);  // React dev mode mounts effects twice: the provider's first socket is closed at once
  const before = sockets.length;

  await sockets[before - 1].close({ code: 1012, reason: 'test: connection dropped' });
  await expect(page.getByRole('link', { name: /System status: Reconnecting/ })).toBeVisible();
  const title = `[E2E] Missed while offline ${Date.now()}`;
  await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) });

  await expect.poll(() => sockets.length, { timeout: 15_000 }).toBeGreaterThan(before);
  expect(urls.at(-1)).toMatch(/after=\d+/);  // resumed from the last event it processed, so the missed event is replayed
  await expect(page.getByRole('link', { name: /System status: System ready/ })).toBeVisible();
  await expect(page.getByText(title)).toBeVisible({ timeout: 15_000 });  // the list refetched because of the replayed event
});

test('global search reaches sources and reviews', async ({ page }) => {
  watch(page);
  const c = (await (await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] Search ${Date.now()}` }) })).json()).data;
  const tag = `quay${Date.now()}`;
  await fetch(`${API}/cases/${c.case_id}/sources`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: `https://www.youtube.com/watch?v=${tag}` }) });
  await page.goto('/dashboard');
  await page.getByRole('button', { name: /or run a command/ }).click();
  await page.getByRole('dialog').getByRole('combobox').fill(tag);
  await expect(page.getByRole('dialog')).toContainText('Sources');
  await expect(page.getByRole('dialog')).toContainText('Searched case, evidence, source, finding, report, review');
  await page.getByRole('dialog').getByRole('option', { name: new RegExp(tag) }).first().click();
  await expect(page).toHaveURL(new RegExp(`/sources\\?case=${c.case_id}`));
});
