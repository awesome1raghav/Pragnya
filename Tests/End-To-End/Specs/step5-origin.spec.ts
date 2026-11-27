/* Step 5 end-to-end, with no traffic leaving this machine: an internal address added as a source is blocked by the
   SSRF rules, a platform URL is recorded as needing a connector (no request made), and two versions of one photo
   uploaded to an investigation appear on the Lineage page as a candidate relationship found by fingerprints. */
import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

const API = process.env.NEXTRON_API ?? 'http://localhost:8002/api/v1';
const SHOTS = path.join(__dirname, '..', '..', 'Test Reports', 'End-To-End', 'Screenshots');
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

let problems: string[] = [];
test.beforeEach(async ({ page }) => {
  problems = [];
  page.on('pageerror', e => problems.push(`pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error' && !/status of (404|409|422)/.test(m.text())) problems.push(`console: ${m.text()}`); });
});
test.afterEach(() => { expect(problems, problems.join('\n')).toEqual([]); });

async function newCase(title: string) {
  return (await (await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] ${title} ${Date.now()}` }) })).json()).data;
}

async function photoPair(page: Page) {
  const [full, small] = await page.evaluate(() => {
    const c = document.createElement('canvas'); c.width = 480; c.height = 360;
    const g = c.getContext('2d')!;
    for (let y = 0; y < 360; y += 6) for (let x = 0; x < 480; x += 6) {
      g.fillStyle = `rgb(${120 + 80 * Math.sin(x / 37)},${110 + 70 * Math.cos(y / 23)},${90 + 60 * Math.sin((x + y) / 51)})`; g.fillRect(x, y, 6, 6);
    }
    g.fillStyle = '#c83c28'; g.fillRect(160, 120, 170, 120);
    const s = document.createElement('canvas'); s.width = 240; s.height = 180; s.getContext('2d')!.drawImage(c, 0, 0, 240, 180);
    return [c.toDataURL('image/png').split(',')[1], s.toDataURL('image/jpeg', 0.7).split(',')[1]];
  });
  return [Buffer.from(full, 'base64'), Buffer.from(small, 'base64')];
}

async function uploadVia(page: Page, caseId: string, name: string, mime: string, data: Buffer) {
  await page.goto(`/investigations/${caseId}/evidence/add`);
  await expect(page.getByText(/MB per file/)).toBeVisible();
  await page.locator('input[type=file]').setInputFiles({ name, mimeType: mime, buffer: data });
  await page.getByRole('button', { name: /Upload and preserve 1 file/ }).click();
  await expect(page.getByRole('region', { name: 'Upload queue' })).toContainText(/analysis JOB-\d+ queued/);
}

test('an internal address is blocked and a platform URL needs a connector', async ({ page }) => {
  const c = await newCase('Sources');
  await page.goto(`/sources?case=${c.case_id}`);
  const add = page.getByRole('region', { name: 'Add a source' });
  const list = page.getByRole('region', { name: 'Sources list' });

  await add.getByRole('textbox', { name: 'Source URL' }).fill('http://169.254.169.254/latest/meta-data/');
  await add.getByRole('button', { name: 'Add' }).click();
  const metadata = list.getByRole('listitem', { name: /169\.254\.169\.254/ });
  await expect(metadata).toContainText('Blocked (internal address)');
  await expect(metadata).toContainText('non-public address');

  await add.getByRole('textbox', { name: 'Source URL' }).fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  await add.getByRole('button', { name: 'Add' }).click();
  const yt = list.getByRole('listitem', { name: /youtube\.com/ });
  await expect(yt).toContainText('Needs a platform connector');
  await yt.getByRole('button', { name: /History of SRC-\d+/ }).click();
  await expect(yt).toContainText('no request made');

  await add.getByRole('textbox', { name: 'Source URL' }).fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  await add.getByRole('button', { name: 'Add' }).click();
  await expect(add.getByRole('alert')).toContainText('already a source');
  await expect(page.getByRole('region', { name: 'Connectors' })).toContainText('Not configured');
  await shot(page, '25-sources');
});

test('two versions of one photo appear as a candidate on the Lineage page', async ({ page }) => {
  const c = await newCase('Lineage');
  const [full, small] = await photoPair(page);
  await uploadVia(page, c.case_id, 'original.png', 'image/png', full);
  await uploadVia(page, c.case_id, 'repost.jpg', 'image/jpeg', small);
  await page.goto(`/lineage?case=${c.case_id}`);
  const rels = page.getByRole('region', { name: 'Candidate relationships' });
  await expect(rels.getByRole('row')).toHaveCount(2, { timeout: 60_000 });  // header + one candidate, arriving through live events
  await expect(rels).toContainText(/Same content, varied|Near-duplicate/);
  await expect(rels).toContainText('no stated publication times order them');
  await expect(page.getByRole('note')).toContainText('not proof of common origin');
  await expect(page.getByRole('img', { name: /2 evidence items, 1 candidate relationships/ })).toBeVisible();
  await shot(page, '26-lineage');
});
