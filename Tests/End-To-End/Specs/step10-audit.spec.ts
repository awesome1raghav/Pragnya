/* Step 10 UI/UX audit: every route at desktop (1440×900) and phone (390×844) width, with a full-page screenshot and
   measured checks. Hard checks fail the test: console errors, horizontal overflow, controls without an accessible
   name, images without alt text, not exactly one h1. Soft checks are reported in ui-audit.json: tap targets under
   24 px on the phone, text under 11 px. Screenshots: Tests/Test Reports/End-To-End/UI Audit/. */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const API = process.env.NEXTRON_API ?? 'http://localhost:8000/api/v1';
const OUT = path.join(__dirname, '..', '..', 'Test Reports', 'End-To-End', 'UI Audit');
const WIDTHS = { desktop: { width: 1440, height: 900 }, phone: { width: 390, height: 844 } } as const;
const STATIC = ['/', '/about', '/dashboard', '/investigations', '/investigations/new', '/evidence', '/sources', '/lineage', '/intelligence',
  '/graph', '/reports', '/notifications', '/system', '/system/health', '/system/logs', '/settings'];
const CASE_TABS = ['', '/evidence', '/evidence/add', '/analysis', '/analysis/image', '/timeline', '/graph', '/review', '/report', '/events'];
const EVIDENCE_TOOLS = ['', '/preview', '/metadata', '/integrity', '/timeline', '/analysis'];

type Finding = { route: string; width: string; check: string; detail: string };

async function measure(page: Page) {
  return page.evaluate(() => {
    const out: { check: string; detail: string; hard: boolean }[] = [];
    const vw = document.documentElement.clientWidth;
    const sw = document.scrollingElement!.scrollWidth;
    if (sw > vw + 1) {
      const wide = [...document.querySelectorAll<HTMLElement>('body *')].filter(el => { const r = el.getBoundingClientRect(); return r.right > vw + 1 && r.width > 0 && getComputedStyle(el).position !== 'fixed'; })
        .filter(el => !el.parentElement || el.parentElement.getBoundingClientRect().right <= vw + 1).slice(0, 3)
        .map(el => `${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} (${Math.round(el.getBoundingClientRect().right)}px)`);
      out.push({ check: 'horizontal-overflow', detail: `page ${sw}px wide in a ${vw}px viewport: ${wide.join(', ')}`, hard: true });
    }
    const visible = (el: Element) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const name = (el: Element) => (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title') || ((el as HTMLElement).innerText ?? el.textContent) || el.querySelector('img[alt]')?.getAttribute('alt') || '').trim();
    for (const el of document.querySelectorAll('button, a[href], [role=button]')) {
      if (visible(el) && !name(el)) out.push({ check: 'unnamed-control', detail: el.outerHTML.slice(0, 140), hard: true });
    }
    for (const el of document.querySelectorAll('input:not([type=hidden]), select, textarea')) {
      const id = el.id; const labelled = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.closest('label') || (id && document.querySelector(`label[for="${id}"]`));
      if (visible(el) && !labelled) out.push({ check: 'unlabelled-field', detail: el.outerHTML.slice(0, 140), hard: true });
    }
    for (const img of document.querySelectorAll('img')) if (!img.hasAttribute('alt')) out.push({ check: 'img-without-alt', detail: img.outerHTML.slice(0, 140), hard: true });
    const h1 = [...document.querySelectorAll('h1')].filter(visible).length;
    if (h1 !== 1) out.push({ check: 'h1-count', detail: `${h1} visible h1 elements`, hard: true });
    if (vw < 500) {
      const small = [...document.querySelectorAll('button, a[href], input, select, [role=button]')].filter(visible)
        .filter(el => { const r = (el.closest('label') ?? el).getBoundingClientRect(); return r.width < 24 || r.height < 24; });  // a control inside a label is hit through the label
      if (small.length) out.push({ check: 'small-tap-target', detail: `${small.length}: ${small.slice(0, 4).map(el => `${el.tagName.toLowerCase()} "${name(el).slice(0, 24)}" ${Math.round(el.getBoundingClientRect().width)}×${Math.round(el.getBoundingClientRect().height)}`).join('; ')}`, hard: false });
    }
    const tiny = [...document.querySelectorAll('body *')].filter(el => el.childNodes.length && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent!.trim()) && visible(el) && parseFloat(getComputedStyle(el).fontSize) < 11);
    if (tiny.length) out.push({ check: 'tiny-text', detail: `${tiny.length} elements under 11px, e.g. "${(tiny[0].textContent ?? "").trim().slice(0, 30)}" ${getComputedStyle(tiny[0]).fontSize}`, hard: false });
    return out;
  });
}

test('every route at desktop and phone width', async ({ browser }) => {
  test.setTimeout(900_000);
  fs.mkdirSync(OUT, { recursive: true });
  const c = (await (await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] UI audit ${Date.now()}`, description: 'Audit case with one analysed photo' }) })).json()).data;
  const ctx0 = await browser.newContext();
  const p0 = await ctx0.newPage();
  await p0.goto('/dashboard');
  const png = await p0.evaluate(() => { const cv = document.createElement('canvas'); cv.width = 480; cv.height = 320; const g = cv.getContext('2d')!; const gr = g.createLinearGradient(0, 0, 480, 320); gr.addColorStop(0, '#1d3557'); gr.addColorStop(1, '#e9a23b'); g.fillStyle = gr; g.fillRect(0, 0, 480, 320); g.fillStyle = '#f1faee'; g.fillRect(140, 90, 200, 140); return cv.toDataURL('image/png').split(',')[1]; });
  await ctx0.close();
  const form = new FormData();
  form.append('file', new Blob([Buffer.from(png, 'base64')], { type: 'image/png' }), 'audit.png');
  const ev = (await (await fetch(`${API}/cases/${c.case_id}/evidence`, { method: 'POST', body: form })).json()).data;
  await expect.poll(async () => (await (await fetch(`${API}/jobs/${ev.analysis_job.job_id}`)).json()).data.state, { timeout: 120_000 }).not.toMatch(/QUEUED|RUNNING/);

  const routes = [...STATIC, ...CASE_TABS.map(t => `/investigations/${c.case_id}${t}`), ...EVIDENCE_TOOLS.map(t => `/evidence/${ev.evidence_id}${t}`)];
  const findings: Finding[] = [];
  for (const [label, viewport] of Object.entries(WIDTHS)) {
    const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, isMobile: label === 'phone', hasTouch: label === 'phone' });
    const page = await ctx.newPage();
    let errors: string[] = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error' && !/status of (404|409|422)/.test(m.text())) errors.push(m.text()); });
    for (const route of routes) {
      errors = [];
      await page.goto(route);
      await page.waitForLoadState('networkidle').catch(() => {});
      await page.waitForTimeout(600);  // let entrance animations settle before measuring
      const name = route.replace(c.case_id, 'CASE').replace(ev.evidence_id, 'EVD').replace(/\//g, '_') || '_root';
      await page.screenshot({ path: path.join(OUT, `${label}${name}.png`), fullPage: true });
      for (const f of await measure(page)) findings.push({ route: route.replace(c.case_id, ':caseId').replace(ev.evidence_id, ':evidenceId'), width: label, check: f.check, detail: f.detail });
      for (const e of errors) findings.push({ route, width: label, check: 'console-error', detail: e.slice(0, 200) });
    }
    await ctx.close();
  }
  fs.writeFileSync(path.join(OUT, 'ui-audit.json'), JSON.stringify({ routes: routes.length, widths: Object.keys(WIDTHS), findings }, null, 2));
  const hard = findings.filter(f => !['small-tap-target', 'tiny-text'].includes(f.check));
  expect(hard, JSON.stringify(hard, null, 2)).toEqual([]);
});

/* Interactions the page-load audit cannot see: switching a form's mode re-renders its fields, and React reports
   controlled/uncontrolled swaps only then. Any console error fails the test. */
test('switching form modes raises no console errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && !/status of (404|409|422)/.test(m.text())) errors.push(m.text()); });
  const c = (await (await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: `[E2E] Form modes ${Date.now()}` }) })).json()).data;

  await page.goto(`/sources?case=${c.case_id}`);
  const vs = page.getByRole('region', { name: 'Visual search' });
  const mode = vs.getByRole('combobox').filter({ has: page.locator('option[value=url]') });
  await expect(mode).toBeVisible();
  for (const v of ['url', 'file', 'url', 'file']) {
    await mode.selectOption(v);
    await expect(vs.locator(v === 'url' ? 'input[type=url]' : 'input[type=file]')).toBeVisible();
  }
  await vs.locator('input[type=file]').setInputFiles({ name: 'q.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64') });
  await mode.selectOption('url');
  await vs.locator('input[type=url]').fill('https://example.org/image.jpg');
  await mode.selectOption('file');

  await page.goto('/settings');
  await page.getByRole('combobox', { name: 'Automatic analysis' }).selectOption('off');
  await page.getByRole('combobox', { name: 'Automatic analysis' }).selectOption('server');
  await page.getByRole('combobox', { name: 'Default report download' }).selectOption('json');
  await page.getByRole('combobox', { name: 'Default report download' }).selectOption('pdf');

  await page.goto('/investigations');
  await page.getByRole('textbox', { name: /Search investigations/ }).fill('form modes');
  await page.getByRole('textbox', { name: /Search investigations/ }).fill('');
  expect(errors, errors.join('\n')).toEqual([]);
});
