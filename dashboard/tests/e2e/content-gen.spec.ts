import { expect, test } from '@playwright/test'

test('content studio quick actions open shared form dialogs', async ({ page }) => {
  await page.goto('/content-gen')

  await expect(page.getByRole('heading', { name: 'Content Studio' })).toBeVisible()

  await page.getByRole('button', { name: 'New Pipeline' }).click()
  await expect(page.getByRole('heading', { name: 'New Pipeline' })).toBeVisible()
  await expect(page.getByLabel('Theme')).toBeVisible()
  await page.getByRole('button', { name: 'Close dialog' }).click()

  await page.getByRole('button', { name: 'Quick Script' }).click()
  await expect(page.getByRole('heading', { name: 'Quick Script' })).toBeVisible()
  await expect(page.getByLabel('LLM route')).toBeVisible()
  await expect(page.getByLabel('Markdown draft')).toBeVisible()
})
