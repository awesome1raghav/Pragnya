import { expect, test } from '@playwright/test';

const API = process.env.NEXTRON_API ?? 'http://localhost:8001/api/v1';

test('sources keeps local image search as the default', async ({ page }) => {
  const created = await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: `[E2E] visual search ${Date.now()}` }) });
  expect(created.status).toBe(201);
  const caseId = (await created.json()).data.case_id;
  await page.goto(`/sources?case=${caseId}`);
  const panel = page.getByRole('region', { name: 'Visual search' });
  await expect(panel.getByText('Choose an image or screenshot.')).toBeVisible();
  await expect(panel.getByRole('combobox', { name: 'Search in' })).toHaveValue('local');
  const input = panel.locator('input[type=file]');
  const png = await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
    canvas.getContext('2d')!.fillRect(0, 0, 256, 256);
    return canvas.toDataURL('image/png').split(',')[1];
  });
  await input.setInputFiles({ name: 'screenshot.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') });
  await expect(panel.getByText('Ready to search indexed case images.')).toBeVisible();
  await panel.getByRole('button', { name: 'Search images' }).click();
  await expect(page.getByRole('region', { name: 'Visual search results' })).toContainText('Selected investigation', { timeout: 45_000 });
  await expect(page.getByRole('region', { name: 'Visual search results' })).toContainText('No matches found');
});

test('web mode requires consent and displays unverified provider links', async ({ page }) => {
  const created = await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: `[E2E] visual web UI ${Date.now()}` }) });
  const caseId = (await created.json()).data.case_id;
  await page.route('**/api/v1/visual-search/status', async route => {
    const response = await route.fetch();
    const body = await response.json();
    body.data.web.configured = true; // UI contract fixture; no external search is made.
    await route.fulfill({ response, json: body });
  });
  await page.route('**/api/v1/visual-search/thumbnails/*', route => route.fulfill({
    contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/hL8AAAAASUVORK5CYII=', 'base64'),
  }));
  let sent = false;
  await page.route('**/api/v1/cases/*/visual-search', async route => {
    const request = route.request();
    const data = request.postData() ?? '';
    expect(data).toContain('allow_external');
    expect(data).toContain('true');
    sent = true;
    await route.fulfill({ json: { success: true, data: { provider: 'serpapi_google_lens', scope: 'web',
      query_sha256: 'a'.repeat(64), matches: [{ page_url: 'https://example.org/story', image_url: 'https://example.org/image.jpg',
        title: 'Example source', match_type: 'VISUAL_MATCH', score: null, score_kind: null, thumbnail_token: 'preview-token' }],
      limitations: ['Check this lead yourself.'] }, meta: {} } });
  });
  await page.goto(`/sources?case=${caseId}`);
  const panel = page.getByRole('region', { name: 'Visual search' });
  await panel.getByRole('combobox', { name: 'Search in' }).selectOption('web');
  const png = await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
    return canvas.toDataURL('image/png').split(',')[1];
  });
  await panel.locator('input[type=file]').setInputFiles({ name: 'frame.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') });
  await expect(panel.getByRole('button', { name: 'Search images' })).toBeDisabled();
  await panel.getByRole('checkbox', { name: /I consent to sending/ }).check();
  await panel.getByRole('button', { name: 'Search images' }).click();
  await expect(page.getByRole('region', { name: 'Visual search results' }).getByRole('link', { name: /Open page/ })).toHaveAttribute('href', 'https://example.org/story');
  const preview = page.getByRole('img', { name: 'Web visual match preview' });
  await expect(preview).toHaveAttribute('src', /visual-search\/thumbnails\/preview-token$/);
  await expect.poll(() => preview.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  expect(sent).toBe(true);
});
