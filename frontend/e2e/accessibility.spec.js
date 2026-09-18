import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('landing and lens workspace have no serious accessibility violations', async ({ page }) => {
  await page.route('http://127.0.0.1:8000/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
  );
  await page.goto('/');
  const landing = await new AxeBuilder({ page }).analyze();
  expect(landing.violations.filter((item) => ['critical', 'serious'].includes(item.impact))).toEqual([]);
  await page.getByRole('button', { name: /Analysis lens/i }).click();
  const dialog = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
  expect(dialog.violations.filter((item) => ['critical', 'serious'].includes(item.impact))).toEqual([]);
});
