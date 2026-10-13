// With next start on port 3000: node scripts/check-docs-site.cjs.
// Uses installed Chrome and Next's bundled WebSocket client, without test dependencies.
const assert = require('node:assert/strict');
const { writeFileSync, mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const { spawn } = require('node:child_process');
const WebSocket = require('next/dist/compiled/ws');
const base = process.env.SITE_CHECK_URL || 'http://localhost:3000';
const profile = mkdtempSync(join(tmpdir(), 'recallhq-docs-check-'));
const chrome = spawn(
  'google-chrome',
  ['--headless', '--no-sandbox', '--disable-gpu', '--remote-debugging-port=9234', `--user-data-dir=${profile}`, 'about:blank'],
  { stdio: 'ignore' },
);
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let socket,
  sequence = 0;
const pending = new Map();
async function until(fn, label, attempts = 100) {
  for (let i = 0; i < attempts; i++) {
    if (await fn()) return;
    await pause(100);
  }
  throw new Error(`Timed out: ${label}`);
}
function call(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}
async function visit(path) {
  await call('Page.navigate', { url: `${base}${path}` });
  await until(
    async () =>
      await evaluate(
        `document.readyState === "complete" && location.href.replace(new RegExp('/$'), '') === ${JSON.stringify(`${base}${path}`.replace(/\/$/, ''))} && !!document.querySelector("main")`,
      ),
    path,
  );
  await pause(700);
}
async function screenshot(name) {
  const result = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(join(tmpdir(), `recallhq-${name}.png`), Buffer.from(result.data, 'base64'));
}
const source = {
  id: 'synthetic:eng:20260915-01',
  channel: 'eng',
  author_name: 'Priya Shah',
  text: 'Reporting joins and dedupe rules are cleaner with Postgres.',
  created_at: '2026-09-15T09:12:00+05:30',
};
async function mock(payload, status = 200, delay = 0) {
  await evaluate(
    `window.__originalFetch ||= window.fetch; window.__requests = []; window.fetch = async (url, options) => { if (!String(url).endsWith('/commands')) return window.__originalFetch(url, options); window.__requests.push({url, ...options}); await new Promise(resolve => setTimeout(resolve, ${delay})); return new Response(${JSON.stringify(JSON.stringify(payload))}, {status: ${status}, headers: {'Content-Type':'application/json'}}); };`,
  );
}
async function run() {
  await evaluate('document.querySelector("form").requestSubmit()');
}
async function output(text) {
  await until(async () => (await evaluate('document.querySelector("section[aria-busy]").innerText')).includes(text), text);
}
async function tab(name) {
  await evaluate(`Array.from(document.querySelectorAll("button")).find(button => button.textContent === "/${name}").click()`);
  await pause(100);
}
(async () => {
  await until(async () => {
    try {
      return (await fetch('http://127.0.0.1:9234/json/list')).ok;
    } catch {
      return false;
    }
  }, 'Chrome');
  const targets = await (await fetch('http://127.0.0.1:9234/json/list')).json();
  socket = new WebSocket(targets.find((target) => target.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve) => socket.once('open', resolve));
  socket.on('message', (raw) => {
    const data = JSON.parse(String(raw));
    if (!data.id) return;
    const request = pending.get(data.id);
    pending.delete(data.id);
    data.error ? request.reject(new Error(data.error.message)) : request.resolve(data.result);
  });
  await call('Page.enable');
  for (const path of [
    '/',
    '/docs',
    '/docs/installation',
    '/docs/quickstart',
    '/docs/commands',
    '/docs/permissions',
    '/docs/troubleshooting',
    '/playground',
  ])
    assert.equal((await fetch(`${base}${path}`)).status, 200, path);
  assert.equal((await fetch(`${base}/docs/missing`)).status, 404);
  assert.equal(
    (await fetch(`${base}/demo`, { redirect: 'manual' })).headers.get('location'),
    `${new URL(base).pathname.replace(/\/$/, '')}/workspace/beacon/channel/eng`,
  );
  for (const width of [1440, 390]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height: 1000, deviceScaleFactor: 1, mobile: width === 390 });
    for (const [path, label] of [
      ['/', 'home'],
      ['/docs/commands', 'docs'],
      ['/playground', 'playground'],
    ]) {
      await visit(path);
      assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true, `${label} overflow at ${width}`);
      await screenshot(`${label}-${width}`);
    }
  }
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await visit('/playground');
  await tab('search');
  await until(
    async () =>
      await evaluate(
        'Array.from(document.querySelectorAll("button")).some(button => button.textContent === "/search" && button.getAttribute("aria-pressed") === "true")',
      ),
    'playground hydration',
  );
  await tab('ask');
  await mock({ kind: 'answer', answer: 'Postgres makes reporting joins cleaner.', sources: [source] }, 200, 500);
  await run();
  await output('Finding the conversation');
  assert.equal(await evaluate('document.querySelector("button[type=submit]").disabled'), true);
  await output('Postgres makes reporting joins cleaner.');
  const request = await evaluate('window.__requests[0]');
  assert.equal(request.credentials, 'omit');
  assert.equal(JSON.parse(request.body).input, '/ask Why did the team switch from MongoDB to Postgres for the pilot?');
  assert.ok(await evaluate('Array.from(document.links).some(link => link.href.includes("synthetic%3Aeng%3A20260915-01"))'));
  await screenshot('playground-answer');
  await mock({ kind: 'search', hits: [] });
  await tab('search');
  await run();
  await output('No matching messages');
  await mock({ kind: 'answer', answer: 'Recap complete.', sources: [source] });
  await tab('catchup');
  await run();
  await output('Recap complete.');
  assert.equal(JSON.parse(await evaluate('window.__requests[0].body')).input, '/catchup 2026-09-14 2026-09-18 #eng');
  await evaluate(
    'const input = document.querySelector("#end-date"); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(input,"2026-11-18"); input.dispatchEvent(new Event("input",{bubbles:true})); input.dispatchEvent(new Event("change",{bubbles:true}));',
  );
  await until(async () => await evaluate('document.querySelector("button[type=submit]").disabled'), 'invalid dates');
  await tab('ask');
  await mock({ detail: 'limit' }, 429);
  await run();
  await output('public demo limit');
  await mock({ detail: 'Service unavailable' }, 503);
  await run();
  await output('Service unavailable');
  if (process.env.SITE_CHECK_LIVE === '1') {
    await evaluate('window.fetch = window.__originalFetch');
    await tab('search');
    await run();
    await until(
      async () => await evaluate('document.querySelector("section[aria-busy]").getAttribute("aria-busy") === "false"'),
      'live API request',
      900,
    );
    assert.ok(
      await evaluate('Array.from(document.links).some(link => link.href.includes("synthetic%3A"))'),
      'Live API should return synthetic source links',
    );
    await screenshot('playground-live');
    console.log('Passed: live browser request to public API with synthetic source links.');
  }
  console.log(
    'Passed: routes, 404, demo redirect, desktop/mobile overflow, command payloads, citations, loading, empty results, invalid dates, rate limits, retry.',
  );
  console.log('Screenshots: /tmp/recallhq-{home,docs,playground}-{1440,390}.png and /tmp/recallhq-playground-answer.png');
})()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    if (socket) socket.close();
    chrome.kill();
    await pause(300);
    rmSync(profile, { recursive: true, force: true });
  });
