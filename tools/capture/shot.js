#!/usr/bin/env node
// Headed-browser capture on the virtual screen (:99).
//
//   node shot.js <name> <url> [step ...]
//
// Steps, run in order after the page has loaded:
//   login:argocd        log in to Argo CD (admin / $ARGOCD_PASSWORD), then reopen <url>
//   login:vcenter       log in to the vSphere Client ($VC_USER / $VC_PASSWORD), then reopen <url>
//   click:<selector>    click the first element matching a Playwright selector
//   try-click:<selector>  click it if it is there within 3 s (for a dismissible banner); never fails
//   hover:<selector>    move the mouse over the first matching element and leave it there
//   wait:<text>         wait until the text is visible on the page
//   expect:<text>       require the text to be visible now (5 s grace) and log the element's full text; fails otherwise
//   reload-until-not:<text>   reload (at most 10 times) until the page no longer shows the text; logs the count
//   sleep:<ms>          pause
//
// Saves into ~/captures:
//   <name>.png        whole screen through scrot (browser frame and address bar included)
//   <name>-page.png   Playwright page screenshot (content only)
// Every step and saved file is logged to stdout and appended to ~/captures/tools/shot.log.
// Passwords come from the environment only; nothing secret is logged or written.
// On a failed step a diagnostic <name>-diag.png is saved (password fields emptied first) and the exit code is 1.

const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const OUT = path.join(os.homedir(), 'captures');
const LOG = path.join(__dirname, 'shot.log');
const DISPLAY = process.env.SHOT_DISPLAY || ':99';
const W = 1680, H = 1000;

function log(msg) {
  const line = `${new Date().toISOString()} ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG, line + '\n');
}

function need(name) {
  const v = process.env[name];
  if (!v) { log(`MISSING environment variable ${name}; stopping`); process.exit(2); }
  return v;
}

async function loginArgocd(page, url) {
  const pw = need('ARGOCD_PASSWORD');
  const origin = new URL(url).origin;
  await page.goto(origin + '/login', { waitUntil: 'domcontentloaded' });
  await page.locator('input.argo-field[type="text"], input[name="username"]').first().fill(process.env.ARGOCD_USER || 'admin');
  await page.locator('input[type="password"]').first().fill(pw);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 30000 });
  log('logged in to Argo CD');
  await page.goto(url, { waitUntil: 'domcontentloaded' });
}

async function loginVcenter(page, url) {
  const user = need('VC_USER'), pw = need('VC_PASSWORD');
  await page.locator('#username').waitFor({ timeout: 90000 });
  await page.locator('#username').fill(user);
  await page.locator('#password').fill(pw);
  await page.locator('#submit').click();
  await page.waitForURL(u => u.pathname.startsWith('/ui'), { timeout: 90000 });
  log('logged in to the vSphere Client');
  await page.goto(url, { waitUntil: 'domcontentloaded' });
}

async function blankSecrets(page) {
  // never photograph a filled password field
  await page.evaluate(() => document.querySelectorAll('input[type="password"]').forEach(i => { i.value = ''; })).catch(() => {});
}

function screenShot(file) {
  execFileSync('scrot', ['-o', file], { env: { ...process.env, DISPLAY } });
}

(async () => {
  const [name, url, ...steps] = process.argv.slice(2);
  if (!name || !url) { console.error('usage: shot.js <name> <url> [step ...]'); process.exit(64); }
  log(`capture ${name}: ${url} steps=[${steps.join(' | ')}]`);

  const browser = await chromium.launch({
    headless: false,
    ignoreDefaultArgs: ['--enable-automation'],
    // --test-type hides the "unsupported command-line flag" bar; the address bar stays visible
    args: [`--window-size=${W},${H}`, '--window-position=0,0', '--test-type', '--no-first-run', '--no-default-browser-check'],
    env: { ...process.env, DISPLAY },
  });
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: null });
  // Open the target from a blank tab with window.open: a tab opened that way has the focus on the
  // page, so the address bar shows the URL without the "selected text" highlight of a fresh tab.
  const blank = await context.newPage();
  const [page] = await Promise.all([
    context.waitForEvent('page'),
    blank.evaluate(u => { window.open(u, '_blank'); }, url),
  ]);
  await blank.close();
  let failed = false;
  try {
    await page.waitForLoadState('domcontentloaded', { timeout: 60000 });
    log(`opened ${page.url()}`);
    for (const step of steps) {
      const i = step.indexOf(':');
      const kind = i === -1 ? step : step.slice(0, i);
      const arg = i === -1 ? '' : step.slice(i + 1);
      log(`step ${kind}${kind === 'login' ? ':' + arg : arg ? ': ' + arg : ''}`);
      if (kind === 'login' && arg === 'argocd') await loginArgocd(page, url);
      else if (kind === 'login' && arg === 'vcenter') await loginVcenter(page, url);
      else if (kind === 'click') await page.locator(arg).first().click({ timeout: 30000 });
      else if (kind === 'try-click') {
        const hit = await page.locator(arg).first().click({ timeout: 3000 }).then(() => true, () => false);
        log(`try-click ${hit ? 'clicked' : 'nothing to click'}`);
      } else if (kind === 'hover') await page.locator(arg).first().hover({ timeout: 30000 });
      else if (kind === 'wait') await page.getByText(arg, { exact: false }).first().waitFor({ state: 'visible', timeout: 60000 });
      else if (kind === 'expect') {
        const el = page.getByText(arg, { exact: false }).first();
        await el.waitFor({ state: 'visible', timeout: 5000 });
        log(`expect ok: "${(await el.innerText()).replace(/\s+/g, ' ').trim()}"`);
      } else if (kind === 'reload-until-not') {
        let n = 0;
        while (await page.getByText(arg, { exact: false }).first().isVisible() && n < 10) {
          n += 1;
          await page.reload({ waitUntil: 'load' });
          await page.waitForTimeout(1500);
          log(`reload ${n}: "${arg}" ${await page.getByText(arg, { exact: false }).first().isVisible() ? 'still shown' : 'no longer shown'}`);
        }
        log(`reload-until-not: ${n} reload(s); "${arg}" ${await page.getByText(arg, { exact: false }).first().isVisible() ? 'STILL SHOWN after the limit' : 'not shown'}`);
      } else if (kind === 'sleep') await page.waitForTimeout(Number(arg) || 1000);
      else throw new Error(`unknown step "${step}"`);
    }
    await page.waitForTimeout(Number(process.env.SHOT_SETTLE_MS || 1500));
    await blankSecrets(page);
    const full = path.join(OUT, `${name}.png`), content = path.join(OUT, `${name}-page.png`);
    screenShot(full);
    log(`saved ${full} (screen, title "${await page.title()}", url ${page.url()})`);
    await page.screenshot({ path: content });
    log(`saved ${content} (page)`);
  } catch (e) {
    failed = true;
    log(`FAILED: ${String(e.message).split('\n')[0]}`);
    try {
      await blankSecrets(page);
      const diag = path.join(OUT, `${name}-diag.png`);
      screenShot(diag);
      log(`saved ${diag} (diagnostic, url ${page.url()})`);
    } catch (e2) { log(`no diagnostic screenshot: ${e2.message}`); }
  } finally {
    await browser.close();
  }
  process.exit(failed ? 1 : 0);
})();
