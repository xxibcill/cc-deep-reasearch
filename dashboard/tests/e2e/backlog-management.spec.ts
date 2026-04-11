import { expect, test } from '@playwright/test'
import type { MockBacklogItem } from './dashboard-mocks'

const mockBacklogItems: MockBacklogItem[] = [
  {
    idea_id: 'item-001',
    idea: 'AI coding assistants in enterprise software development',
    category: 'trend-responsive',
    status: 'backlog',
    risk_level: 'medium',
    priority_score: 7.5,
    latest_score: 72,
    latest_recommendation: 'produce_now',
    source_theme: 'AI & Automation',
    created_at: '2026-04-01T10:00:00Z',
    updated_at: '2026-04-01T10:00:00Z',
  },
  {
    idea_id: 'item-002',
    idea: 'Sustainable packaging alternatives for direct-to-consumer brands',
    category: 'evergreen',
    status: 'selected',
    risk_level: 'low',
    priority_score: 8.2,
    latest_score: 85,
    latest_recommendation: 'produce_now',
    selection_reasoning: 'Strong audience resonance and evergreen topic',
    source_theme: 'Sustainability',
    created_at: '2026-03-28T14:30:00Z',
    updated_at: '2026-04-05T09:15:00Z',
  },
  {
    idea_id: 'item-003',
    idea: 'Remote team collaboration tools comparison guide',
    category: 'authority-building',
    status: 'archived',
    risk_level: 'high',
    priority_score: 5.0,
    source_theme: 'Future of Work',
    created_at: '2026-02-15T08:00:00Z',
    updated_at: '2026-03-20T16:45:00Z',
  },
]

async function setupBacklogMocks(
  page: Parameters<typeof test>[0] extends { page: infer P } ? P : never,
  backlogItems: MockBacklogItem[] = []
) {
  const createItem = (data: Record<string, unknown>): MockBacklogItem => {
    const now = new Date().toISOString()
    return {
      idea_id: Math.random().toString(36).substring(2, 10),
      idea: '',
      category: '',
      audience: '',
      problem: '',
      status: 'backlog',
      risk_level: 'medium',
      created_at: now,
      updated_at: now,
      ...data,
    } as MockBacklogItem
  }

  let items = [...backlogItems]

  // Mock content-gen pipeline routes (used by ContentGenShell)
  await page.route('**/api/content-gen/pipelines', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })

  await page.route('**/api/content-gen/scripts', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })

  await page.route('**/api/content-gen/publish', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    })
  })

  await page.route('**/api/content-gen/strategy', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    })
  })

  // Mock backlog API routes
  await page.route('**/api/content-gen/backlog**', async (route) => {
    const url = new URL(route.request().url())
    const pathName = url.pathname
    const method = route.request().method()

    // GET /api/content-gen/backlog - list items
    if (pathName === '/api/content-gen/backlog' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          path: '/tmp/backlog.yaml',
          items,
        }),
      })
      return
    }

    // POST /api/content-gen/backlog - create item
    if (pathName === '/api/content-gen/backlog' && method === 'POST') {
      const body = route.request().postDataBuffer
        ? JSON.parse(route.request().postDataBuffer().toString())
        : {}
      const newItem = createItem(body)
      items.push(newItem)
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(newItem),
      })
      return
    }

    // PATCH /api/content-gen/backlog/{idea_id} - update item
    const patchMatch = pathName.match(/\/api\/content-gen\/backlog\/([^/]+)$/)
    if (patchMatch && method === 'PATCH') {
      const ideaId = patchMatch[1]
      const body = route.request().postDataBuffer
        ? JSON.parse(route.request().postDataBuffer().toString())
        : {}
      const patchData = body.patch || {}
      const itemIndex = items.findIndex((item) => item.idea_id === ideaId)
      if (itemIndex === -1) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Backlog item not found' }),
        })
        return
      }
      items[itemIndex] = {
        ...items[itemIndex],
        ...patchData,
        updated_at: new Date().toISOString(),
      } as MockBacklogItem
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(items[itemIndex]),
      })
      return
    }

    // POST /api/content-gen/backlog/{idea_id}/select - select item
    const selectMatch = pathName.match(/\/api\/content-gen\/backlog\/([^/]+)\/select$/)
    if (selectMatch && method === 'POST') {
      const ideaId = selectMatch[1]
      const itemIndex = items.findIndex((item) => item.idea_id === ideaId)
      if (itemIndex === -1) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Backlog item not found' }),
        })
        return
      }
      // Clear previous selections
      items = items.map((item) =>
        item.status === 'selected'
          ? { ...item, status: 'backlog', selection_reasoning: '' }
          : item
      ) as typeof items
      // Set this item as selected
      items[itemIndex] = {
        ...items[itemIndex],
        status: 'selected',
        updated_at: new Date().toISOString(),
      } as MockBacklogItem
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(items[itemIndex]),
      })
      return
    }

    // POST /api/content-gen/backlog/{idea_id}/archive - archive item
    const archiveMatch = pathName.match(/\/api\/content-gen\/backlog\/([^/]+)\/archive$/)
    if (archiveMatch && method === 'POST') {
      const ideaId = archiveMatch[1]
      const itemIndex = items.findIndex((item) => item.idea_id === ideaId)
      if (itemIndex === -1) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Backlog item not found' }),
        })
        return
      }
      items[itemIndex] = {
        ...items[itemIndex],
        status: 'archived',
        updated_at: new Date().toISOString(),
      } as MockBacklogItem
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(items[itemIndex]),
      })
      return
    }

    // DELETE /api/content-gen/backlog/{idea_id} - delete item
    const deleteMatch = pathName.match(/\/api\/content-gen\/backlog\/([^/]+)$/)
    if (deleteMatch && method === 'DELETE') {
      const ideaId = deleteMatch[1]
      const itemIndex = items.findIndex((item) => item.idea_id === ideaId)
      if (itemIndex === -1) {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Backlog item not found' }),
        })
        return
      }
      items.splice(itemIndex, 1)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ removed: 1 }),
      })
      return
    }

    await route.fallback()
  })
}

test.describe('Backlog Management', () => {
  test('dedicated backlog page shows empty state when no items', async ({ page }) => {
    await setupBacklogMocks(page, [])

    await page.goto('/content-gen/backlog')

    await expect(page.getByText('No backlog items yet')).toBeVisible()
  })

  test('dedicated backlog page renders backlog items with idea text', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Wait for items to load
    await expect(page.getByText('3 items')).toBeVisible()

    // Verify items are rendered by idea text
    await expect(page.getByText('AI coding assistants in enterprise software development')).toBeVisible()
    await expect(page.getByText('Sustainable packaging alternatives for direct-to-consumer brands')).toBeVisible()
  })

  test('select action marks item as selected and disables its button', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Find the select button for item-001 (which is in backlog status)
    const selectButton = page.locator('button[title="Select item"]').first()
    await expect(selectButton).toBeEnabled()

    await selectButton.click()

    // Wait for the API call to complete
    await page.waitForResponse('**/api/content-gen/backlog/item-001/select')

    // The button should now be disabled because item-001 is now selected
    await expect(selectButton).toBeDisabled()
  })

  test('archive action removes item from default view', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Initial count should be 3
    await expect(page.getByText('3 items')).toBeVisible()

    // Find and click the archive button for item-001
    const archiveButton = page.locator('button[title="Archive item"]').first()
    await archiveButton.click()

    // Wait for the API call to complete
    await page.waitForResponse('**/api/content-gen/backlog/item-001/archive')

    // Count should now be 2 since item-001 was archived and filtered out
    await expect(page.getByText('2 items')).toBeVisible()
  })

  test('delete action removes item from list', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Initial count should be 3
    await expect(page.getByText('3 items')).toBeVisible()

    // Find and click the delete button for item-001
    const deleteButton = page.locator('button[title="Delete item"]').first()
    await deleteButton.click()

    // Wait for the API call to complete
    await page.waitForResponse('**/api/content-gen/backlog/item-001')

    // Count should now be 2
    await expect(page.getByText('2 items')).toBeVisible()
  })

  test('status filter filters the item list', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Initial count shows 3 items (backlog status items)
    await expect(page.getByText('3 items')).toBeVisible()

    // Filter by "selected" status
    const statusFilter = page.locator('select').first()
    await statusFilter.selectOption('selected')

    // Should only show the selected item (item-002)
    await expect(page.getByText('Sustainable packaging alternatives')).toBeVisible()
    // And should not show the backlog item
    await expect(page.getByText('AI coding assistants')).not.toBeVisible()
  })
})

test.describe('Backlog Management - Navigation', () => {
  test('backlog tab in content studio shell navigates to dedicated backlog page', async ({ page }) => {
    await setupBacklogMocks(page, [])

    await page.goto('/content-gen')

    // Click the backlog tab
    await page.getByRole('button', { name: 'Backlog' }).click()

    // Should navigate to the dedicated backlog page
    await expect(page).toHaveURL(/\/content-gen\/backlog/)
    await expect(page.getByText('No backlog items yet')).toBeVisible()
  })
})
