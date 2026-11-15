/* End-to-end browser test of the five-minute management demo. Must start from an empty database.
   Usage: node e2e/demo.e2e.cjs   (expects the app at BASE, default http://127.0.0.1:8000) */
const { chromium } = require('playwright')
const path = require('path'), assert = require('assert'), fs = require('fs')
const BASE = process.env.BASE || 'http://127.0.0.1:8000'
const SHOTS = path.join(__dirname, '..', 'docs', 'screenshots')
const results = []

;(async () => {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 }, deviceScaleFactor: 2 })
  const errors = []
  page.on('pageerror', e => errors.push(String(e)))
  page.on('console', m => { if (m.type() === 'error' && !/status of 4\d\d/.test(m.text())) errors.push(m.text()) })
  const shot = n => page.screenshot({ path: path.join(SHOTS, n + '.png'), fullPage: n.endsWith('full') })
  const step = async (name, fn) => {
    try { await fn(); results.push(['PASS', name]); console.log('PASS', name) }
    catch (e) { results.push(['FAIL', name]); console.log('FAIL', name, '\n   ', e.message.split('\n')[0]); await shot('FAILURE').catch(() => {}); throw e }
  }
  const tab = t => page.locator('.tabs button', { hasText: t }).click()
  const nav = t => page.locator('.side button.nav', { hasText: t }).click()
  const as = async u => { await page.selectOption('[data-testid=user-select]', u); await page.waitForTimeout(400) }
  const ok = t => page.locator('.banner.ok', { hasText: t }).first().waitFor({ timeout: 15000 })

  try {
    await step('1. Create project from mock Salesforce opportunity', async () => {
      await page.goto(BASE + '/#/projects'); await page.locator('[data-testid=user-select]').waitFor(); await as('tcoord')
      await page.locator('tr', { hasText: 'Northfield Cold Storage' }).getByRole('button', { name: 'Create project' }).click()
      await page.locator('h1', { hasText: 'Northfield Cold Storage' }).waitFor()
      assert.match(await page.locator('h1').innerText(), /^PS-\d{4}-\d{4}/)
    })
    await step('2. Import Revit-derived model (4 walls, bays derived from columns)', async () => {
      await page.click('[data-testid=import-sample]'); await ok('Model imported')
      await page.locator('.banner.ok', { hasText: '4 added' }).waitFor()
      await shot('01-project-overview-full')
    })
    await step('3. 3D viewer renders; geometry derived from model', async () => {
      await tab('Model'); await page.locator('[data-testid=viewer] canvas').waitFor(); await page.waitForTimeout(1200)
      const colours = await page.evaluate(() => {
        const c = document.querySelector('[data-testid=viewer] canvas'); const g = c.getContext('webgl2') || c.getContext('webgl')
        const w = c.width, h = c.height, b = new Uint8Array(4 * w * h); g.readPixels(0, 0, w, h, g.RGBA, g.UNSIGNED_BYTE, b)
        const set = new Set(); for (let i = 0; i < w * h; i += 97) set.add(b[i * 4] + ',' + b[i * 4 + 1] + ',' + b[i * 4 + 2])
        return set.size
      })
      assert.ok(colours > 50, 'viewer canvas appears blank (' + colours + ' colours)')
      assert.equal(await page.locator('tbody tr', { hasText: 'South elevation' }).first().locator('td').nth(4).innerText(), '8.00')
      await shot('02-model-3d-before-calc')
    })
    await step('4. Deterministic calculation: default layout is checked and FAILS honestly', async () => {
      await tab('Engineering'); await page.click('[data-testid=calc-all]'); await ok('All walls calculated')
      await page.locator('h3', { hasText: 'Calculation trace' }).waitFor()
      assert.ok(await page.locator('.pill.bad', { hasText: 'FAIL' }).count() > 0, 'expected the un-optimised default layout to fail at least one check')
      assert.equal(await page.locator('.banner.warn', { hasText: 'Not for engineering reliance' }).count(), 1)
      await shot('03-engineering-initial-fail-full')
    })
    await step('4b. Coordinator enters current-practice layout on South wall (12 girt lines, heavy Z254): PASSES', async () => {
      await page.locator('tr.click', { hasText: 'South elevation' }).first().click()
      await page.locator('label', { hasText: 'Girt section' }).locator('select').selectOption({ label: 'Z254x76x2.67' })
      await page.fill('[data-testid=f-nspans]', '12')
      await page.click('[data-testid=calc-wall]'); await ok('Calculation complete')
      assert.equal(await page.locator('.card').first().locator('tbody tr').first().locator('.pill').first().innerText(), 'PASS')
    })
    await step('5. Optimise support spacing and girt size on every wall, apply, re-check', async () => {
      await tab('Optimisation')
      for (const w of ['South elevation', 'East elevation', 'North elevation', 'West elevation']) {
        await page.locator('tr.click', { hasText: w }).first().click()
        await page.click('[data-testid=opt-run]'); await ok('Optimisation complete')
        await page.click('[data-testid=opt-apply]'); await ok('Layout applied')
      }
      await page.locator('tr.click', { hasText: 'South elevation' }).first().click(); await page.waitForTimeout(600)
      const rows = page.locator('.card').first().locator('tbody tr')
      for (let i = 0; i < 4; i++) assert.equal(await rows.nth(i).locator('.pill').first().innerText(), 'PASS')
      await shot('04-optimisation-full')
    })
    await step('6. Viewer reflects optimised layout; elevation view; passing trace', async () => {
      await tab('Model'); await page.waitForTimeout(1200); await shot('05-model-3d-optimised')
      await page.locator('.viewer .hud button', { hasText: 'Elevation' }).click(); await page.waitForTimeout(800); await shot('06-model-elevation')
      await tab('Engineering'); await page.locator('h3', { hasText: 'Calculation trace' }).waitFor(); await shot('07-engineering-pass-trace-full')
    })
    await step('7. Coordinator submits; cannot approve (role enforced)', async () => {
      await tab('Review & reports'); await page.locator('.banner.ok', { hasText: 'pass every check' }).waitFor()
      await page.click('[data-testid=review-submit]'); await ok('Submitted for engineering review')
      assert.ok(await page.locator('[data-testid=approve-demo]').isDisabled())
    })
    await step('8. Engineer: reliance approval BLOCKED by unverified data; demonstration approval recorded', async () => {
      await as('eng.review'); await tab('Review & reports')
      await page.fill('[data-testid=review-comment]', 'Checked method and trace. Product strengths are demo values - demonstration only.')
      await page.click('[data-testid=approve-reliance]')
      await page.locator('.banner.bad', { hasText: 'cannot approve for engineering reliance' }).waitFor()
      await shot('08-review-reliance-blocked-full')
      await page.click('[data-testid=approve-demo]'); await ok('demonstration only')
      await page.locator('.pill', { hasText: 'APPROVED DEMO' }).first().waitFor()
    })
    await step('9. Generate PDF report and verify the download is a real PDF', async () => {
      await page.click('[data-testid=report-gen]'); await ok('Report generated')
      const href = await page.locator('a[href*="/download"]').first().getAttribute('href')
      const buf = await (await page.request.get(BASE + href)).body()
      assert.equal(buf.slice(0, 4).toString(), '%PDF'); assert.ok(buf.length > 20000)
      fs.writeFileSync(path.join(SHOTS, '..', 'sample_calc_report.pdf'), buf)
      await shot('09-review-approved-report-full')
    })
    await step('10. Mock Forma Docs publish, mock SAP handoff staged (not transmitted), mock Salesforce sync', async () => {
      await tab('Integrations')
      await page.click('[data-testid=forma-publish]'); await ok('Published to the mock document folder')
      await page.click('[data-testid=sap-stage]'); await ok('Handoff staged')
      await page.locator('.pill', { hasText: 'STAGED NOT TRANSMITTED' }).waitFor()
      await page.click('[data-testid=sf-sync]'); await ok('Status written')
      await page.locator('.pill', { hasText: 'Handoff staged' }).first().waitFor()
      await shot('10-integrations-mock-full')
    })
    await step('11. Record measured preparation hours; audit chain intact', async () => {
      await tab('Overview'); await page.fill('[data-testid=f-baseline]', '16'); await page.fill('[data-testid=f-actual]', '11')
      await page.getByRole('button', { name: 'Save parameters' }).click(); await ok('Saved')
      await tab('Audit'); await page.locator('.banner.ok', { hasText: 'Hash chain intact' }).waitFor(); await shot('11-audit')
    })
    await step('12. Executive dashboard shows computed KPIs', async () => {
      await nav('Executive dashboard'); await page.locator('.kpi').first().waitFor()
      const txt = await page.locator('.kpis').innerText()
      assert.match(txt, /4 \/ 4/); assert.match(txt, /31\.3%/); assert.match(txt, /Intact/)
      assert.match(txt, /1 wall\(s\) whose prior layout already passed/); assert.match(txt, /3 failing layout\(s\) corrected/)
      await shot('12-dashboard-full')
    })
    await step('13. Library and validation pages', async () => {
      await nav('Engineering library'); await page.locator('h2', { hasText: 'IMP panel products' }).waitFor(); await shot('13-library-full')
      await nav('Validation'); await page.locator('.kpi').first().waitFor()
      assert.match(await page.locator('.kpis').innerText(), /7 \/ 7/); await shot('14-validation-full')
    })
    await step('14. Read-only manager cannot change anything', async () => {
      await as('manager'); await nav('Projects'); await page.locator('tr.click').first().click(); await tab('Engineering')
      await page.locator('[data-testid=calc-all]').waitFor()
      assert.ok(await page.locator('[data-testid=calc-all]').isDisabled())
    })
    await step('15. No browser console errors during the run', async () => { assert.deepEqual(errors, []) })
  } catch { process.exitCode = 1 }
  await browser.close()
  console.log(`\n${results.filter(r => r[0] === 'PASS').length} passed, ${results.filter(r => r[0] === 'FAIL').length} failed`)
})()
