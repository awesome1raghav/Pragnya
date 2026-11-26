/* Step 4 end-to-end: the media engines run in the real worker on an uploaded photo with a pasted region.
   The browser shows the engine's findings with the measured region marked on the image, its heatmaps (served
   from the artifact API, hash in the header), the provenance outcome, and the case's Image tab. */
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

/* a noisy photo-like JPEG with a clean pasted block (x 40–65 %, y 33–60 %) */
async function splicedJpeg(page: Page) {
  const b64 = await page.evaluate(() => {
    const c = document.createElement('canvas'); c.width = 400; c.height = 300;
    const g = c.getContext('2d')!; const img = g.createImageData(400, 300);
    let seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
    for (let y = 0; y < 300; y++) for (let x = 0; x < 400; x++) {
      const i = (y * 400 + x) * 4; const pasted = x >= 160 && x < 260 && y >= 100 && y < 180;
      const v = pasted ? 150 + (rnd() - 0.5) * 3 : 60 + x * 0.32 + (rnd() - 0.5) * 42;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    return c.toDataURL('image/jpeg', 0.92).split(',')[1];
  });
  return Buffer.from(b64, 'base64');
}

test('image engines: findings, measured region, heatmaps, provenance, case image tab', async ({ page }) => {
  const c = (await (await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] Engines ${Date.now()}` }) })).json()).data;
  await page.goto(`/investigations/${c.case_id}/evidence/add`);
  await expect(page.getByRole('heading', { level: 1, name: 'Add evidence' })).toBeVisible();
  await expect(page.getByText(/MB per file/)).toBeVisible();
  await page.locator('input[type=file]').setInputFiles({ name: 'harbour-spliced.jpg', mimeType: 'image/jpeg', buffer: await splicedJpeg(page) });
  await page.getByRole('button', { name: /Upload and preserve 1 file/ }).click();
  const queue = page.getByRole('region', { name: 'Upload queue' });
  await queue.getByRole('link', { name: /JOB-\d+/ }).click();

  const modules = page.getByRole('region', { name: 'Modules for this evidence' });
  await expect(modules.getByRole('row', { name: /^NEX-IMG / })).toContainText('Partial');
  await expect(modules.getByRole('row', { name: /^NEX-IMG / })).toContainText('No evaluated synthetic-image detector is installed');
  await expect(modules.getByRole('row', { name: /^NEX-PRV / })).toContainText('Completed');

  const findings = page.getByRole('region', { name: 'Findings' });
  const noise = findings.locator('[data-finding="NOISE_LEVEL_INCONSISTENCY"]');
  await expect(noise).toContainText('Region with a different noise level');
  await expect(noise).toContainText(/region x \d+% y \d+%/);
  await expect(noise.getByRole('img', { name: /with the measured region marked/ })).toBeVisible();
  const heatmap = noise.getByRole('img', { name: /NEX-IMG noise/ });
  await expect(heatmap).toBeVisible();
  expect(await heatmap.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);  // the artifact really loaded
  await expect(findings.locator('[data-finding="NO_CONTENT_CREDENTIALS"]')).toContainText('No content credentials');
  await expect(findings.locator('[data-finding="JPEG_QUANTIZATION"]')).toContainText('IJG quality');
  await expect(findings).toContainText('not a probability');
  await shot(page, '23-evidence-engine-findings');

  // the artifact API serves the heatmap with its recorded hash
  const src = await heatmap.getAttribute('src');
  const res = await fetch(src!);
  expect(res.headers.get('x-artifact-sha256')).toMatch(/^[0-9a-f]{64}$/);
  expect(res.headers.get('x-content-type-options')).toBe('nosniff');

  await page.goto(`/investigations/${c.case_id}/analysis/image`);
  const result = page.getByRole('region', { name: /NEX-IMG result for EVD-\d+/ });
  await expect(result).toContainText('Partial');
  await expect(result).toContainText('Region with a different noise level');
  await expect(result).toContainText(/Tools: .*pillow \d/);
  await page.goto(`/investigations/${c.case_id}/analysis/provenance`);
  await expect(page.getByRole('region', { name: /NEX-PRV result for EVD-\d+/ })).toContainText('No content credentials');
  await page.goto(`/investigations/${c.case_id}/analysis/video`);
  await expect(page.locator('main')).toContainText('No evidence NEX-VID applies to');
  await shot(page, '24-case-image-analysis');
});
