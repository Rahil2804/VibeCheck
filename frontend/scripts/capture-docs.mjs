import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const output = join(import.meta.dirname, '..', '..', 'docs', 'screenshots');
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await page.route('http://127.0.0.1:8000/**', (route) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
);
await page.goto('http://127.0.0.1:4173');
await page.locator('.map-token-state, .map-view').first().waitFor({ state: 'attached' });
await page.waitForTimeout(4_000);
await page.screenshot({ path: join(output, 'gta-landing-desktop.png'), fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.reload();
await page.locator('.map-token-state, .map-view').first().waitFor({ state: 'attached' });
await page.waitForTimeout(4_000);
await page.screenshot({ path: join(output, 'gta-mobile-landing.png'), fullPage: true });
await browser.close();
