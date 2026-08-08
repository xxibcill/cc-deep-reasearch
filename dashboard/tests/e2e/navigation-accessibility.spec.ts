import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { mockDashboardApis } from './dashboard-mocks';

test.describe('Global navigation accessibility @a11y', () => {
  test.beforeEach(async ({ page }) => {
    await mockDashboardApis(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('puts the skip link first and removes closed navigation from the tab order', async ({ page }) => {
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();

    const menuButton = page.getByRole('button', { name: 'Open main navigation' });
    await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toHaveCount(0);

    await menuButton.focus();
    await menuButton.press('Enter');
    const navigation = page.getByRole('navigation', { name: 'Primary navigation' });
    await expect(navigation).toBeVisible();
    await expect(navigation.getByRole('link', { name: 'Knowledge' })).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(navigation).toHaveCount(0);
    await expect(menuButton).toBeFocused();
  });

  test('traps command-palette focus, exposes its purpose, and restores focus', async ({ page }) => {
    const trigger = page.getByRole('button', { name: 'Open command palette' }).first();
    await trigger.click();

    const dialog = page.getByRole('dialog', { name: 'Command palette' });
    const search = dialog.getByRole('combobox', { name: 'Search commands' });
    await expect(dialog).toBeVisible();
    await expect(search).toBeFocused();
    await expect(dialog.getByRole('option', { name: /Go to Radar/ })).toBeVisible();
    await expect(dialog.getByRole('option', { name: /Go to Knowledge/ })).toBeVisible();

    await page.keyboard.press('Shift+Tab');
    await expect(dialog.getByRole('option').last()).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(search).toBeFocused();

    const radarOption = dialog.getByRole('option', { name: /Go to Radar/ });
    await radarOption.focus();
    await radarOption.press('Enter');
    await expect(page).toHaveURL(/\/radar$/);
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();

    await trigger.click();
    const reopenedDialog = page.getByRole('dialog', { name: 'Command palette' });
    const results = await new AxeBuilder({ page })
      .include('[role="dialog"]')
      .withTags(['wcag2a', 'wcag2aa'])
      .disableRules(['color-contrast'])
      .analyze();
    expect(results.violations).toEqual([]);

    await page.keyboard.press('Escape');
    await expect(reopenedDialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });
});
