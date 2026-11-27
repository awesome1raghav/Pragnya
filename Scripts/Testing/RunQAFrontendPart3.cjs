/* Browser route inventory for the isolated QA case. No Source Finder actions. */
const { chromium } = require('../../Tests/End-To-End/node_modules/@playwright/test');
const fs = require('fs');
const path = require('path');
const qa = path.resolve(__dirname, '../../Tests/QA-Audit');
const state = JSON.parse(fs.readFileSync(path.join(qa, 'QA-State.json')));
const id = state.case_id;
const eid = state.evidence['IMG-01'].id;
const routes = ['/', '/dashboard', '/investigations', '/investigations/new', `/investigations/${id}`, `/investigations/${id}/evidence`, `/investigations/${id}/analysis`, `/investigations/${id}/timeline`, `/investigations/${id}/graph`, `/investigations/${id}/review`, `/investigations/${id}/report`, `/investigations/${id}/events`, `/evidence?case=${id}`, `/evidence/${eid}`, `/evidence/${eid}/metadata`, `/evidence/${eid}/analysis`, `/sources?case=${id}`, `/lineage?case=${id}`, `/intelligence?case=${id}`, `/graph?case=${id}`, `/reports?case=${id}`, '/notifications', '/system', '/settings'];
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const results = [];
  for (const route of routes) {
    const errors = [], failed = [];
    const onConsole = m => { if (m.type() === 'error') errors.push(m.text().slice(0, 250)); };
    const onFailed = r => failed.push(`${r.method()} ${r.url()} ${r.failure()?.errorText}`.slice(0, 250));
    page.on('console', onConsole); page.on('requestfailed', onFailed);
    const start = Date.now();
    try {
      const response = await page.goto('http://localhost:8090' + route, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(900);
      results.push({ route, actual_url: page.url(), status: response?.status(), title: await page.title(), heading: await page.locator('h1').allTextContents(), buttons: await page.getByRole('button').count(), links: await page.getByRole('link').count(), inputs: await page.locator('input,textarea,select').count(), console_errors: errors, request_failures: failed, load_ms: Date.now()-start });
    } catch (e) { results.push({ route, error: String(e).slice(0,300), load_ms: Date.now()-start }); }
    page.off('console', onConsole); page.off('requestfailed', onFailed);
  }
  await browser.close();
  fs.writeFileSync(path.join(qa, '03-Frontend-Route-Inventory.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify({ routes: results.length, status200: results.filter(r=>r.status===200).length, errors: results.filter(r=>r.error||r.console_errors?.length||r.request_failures?.length).map(r=>r.route) }));
})().catch(e=>{ console.error(e); process.exit(1); });
