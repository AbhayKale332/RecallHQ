// Run against `next dev` with Playwright available in NODE_PATH.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ executablePath: process.env.BROWSER_EXECUTABLE });
  try {
    const page = await browser.newPage();
    const base = process.env.FRONTEND_URL || 'http://127.0.0.1:3000';
    let pendingCommand;
    const waitForCommand = async () => {
      const deadline = Date.now() + 10000;
      while (!pendingCommand && Date.now() < deadline) await new Promise((resolve) => setTimeout(resolve, 10));
      assert.ok(pendingCommand, 'Command request was sent');
    };
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/commands')) {
        pendingCommand = route;
        return;
      }
      const data = path.endsWith('/channels') ? [{ id: 'eng', name: 'eng', messages: 0 }] : { items: [], next_cursor: null };
      await route.fulfill({ json: data });
    });
    await page.goto(`${base}/workspace/beacon/channel/eng`);
    const editor = page.locator('.ql-editor');
    await editor.fill('/catchup 2026-09-14 2026-09-18 #eng');
    await editor.press('Enter');
    await page.waitForURL('**/member/recallhq');
    await page.getByRole('status').filter({ hasText: 'RecallHQ is typing' }).waitFor();
    assert.equal(await page.locator('[role="status"] .motion-safe\\:animate-bounce').count(), 3);
    await page.waitForFunction(() => document.querySelector('.ql-editor') !== null);
    // The typing status guarantees the request is pending; wait for its interception too.
    await waitForCommand();
    assert.match(pendingCommand.request().postDataJSON().input, /^\/catchup /);
    await pendingCommand.fulfill({ json: { kind: 'answer', answer: 'Catchup recap for engineering.', sources: [] } });
    await page.getByText('Catchup recap for engineering.', { exact: true }).waitFor();
    await page.getByRole('status').filter({ hasText: 'RecallHQ is typing' }).waitFor({ state: 'hidden' });
    await page.screenshot({ path: '/tmp/recallhq-catchup-dm-desktop.png', fullPage: true });

    await page.getByRole('link', { name: /eng/ }).click();
    await page.waitForURL('**/channel/eng');
    assert.equal(await page.getByText('Catchup recap for engineering.', { exact: true }).count(), 0);
    pendingCommand = null;
    await editor.fill('/ask Test channel reply');
    await editor.press('Enter');
    await page.getByRole('status').filter({ hasText: 'RecallHQ is typing' }).waitFor();
    await waitForCommand();
    await pendingCommand.fulfill({ json: { kind: 'answer', answer: 'Channel answer.', sources: [] } });
    await page.getByText('Channel answer.', { exact: true }).waitFor();
    assert.match(page.url(), /\/channel\/eng$/);
    await page.getByRole('link', { name: 'RecallHQ', exact: true }).click();
    await page.getByText('Catchup recap for engineering.', { exact: true }).waitFor();

    pendingCommand = null;
    await editor.fill('/CATCHUP invalid');
    await editor.press('Enter');
    await page.getByRole('status').filter({ hasText: 'RecallHQ is typing' }).waitFor();
    await waitForCommand();
    await pendingCommand.fulfill({ status: 400, json: { detail: 'Invalid catchup dates' } });
    await page.getByText('Invalid catchup dates', { exact: true }).waitFor();
    await page.getByRole('status').filter({ hasText: 'RecallHQ is typing' }).waitFor({ state: 'hidden' });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('combobox', { name: 'Change conversation' }).selectOption('eng');
    await page.waitForURL('**/channel/eng');
    await page.getByRole('combobox', { name: 'Change conversation' }).selectOption('dm:recallhq');
    await page.waitForURL('**/member/recallhq');
    await page.getByText('Catchup recap for engineering.', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({ path: '/tmp/recallhq-catchup-dm-mobile.png', fullPage: true });
    console.log('PASS: catchup DM routing, typing, reply/error cleanup, channel ask replies, session history, and mobile navigation.');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
