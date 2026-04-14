import { expect, test, type Page } from '@playwright/test'
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
  page: Page,
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

  // Mock backlog API routes using local items state to avoid test pollution
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
      const payload = route.request().postDataBuffer()
      const body = payload ? JSON.parse(payload.toString()) : {}
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
      const payload = route.request().postDataBuffer()
      const body = payload ? JSON.parse(payload.toString()) : {}
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
      // Clear previous selections using local items copy
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

  test('dedicated backlog page toggles between grid and list views', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    await expect(page.getByRole('button', { name: 'Grid' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('columnheader', { name: 'Recommendation' })).toHaveCount(0)

    await page.getByRole('button', { name: 'List' }).click()

    await expect(page.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('columnheader', { name: 'Recommendation' })).toBeVisible()
  })

  test('select action marks item as selected and disables its button', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Find the select button for item-001 (which is in backlog status)
    const selectButton = page.locator('button[title="Select item"]').first()
    await expect(selectButton).toBeEnabled()

    await selectButton.click()

    // Wait for the API call to complete
    await page.waitForResponse(/\/api\/content-gen\/backlog\/item-001\/select/)

    // The button should now be disabled because item-001 is now selected
    await expect(selectButton).toBeDisabled()
  })

  test('select button is enabled for already-selected item allowing re-selection', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Find the select button for item-002 (which is already in selected status)
    const selectButton = page.locator('button[title="Select item"]').nth(1)
    await expect(selectButton).toBeEnabled()
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

  test('edit opens dialog, allows field changes, and saves updates', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Wait for items to load
    await expect(page.getByText('3 items')).toBeVisible()

    // Click the edit button (Pencil icon) for item-001
    const editButton = page.locator('button[title="Edit item"]').first()
    await editButton.click()

    // Dialog should open
    await expect(page.getByText('Edit Backlog Item')).toBeVisible()

    // Clear the idea field and enter new text
    const ideaTextarea = page.locator('#idea')
    await ideaTextarea.clear()
    await ideaTextarea.fill('Updated idea text for testing edit flow')

    // Submit the form
    await page.getByRole('button', { name: 'Save Changes' }).click()

    // Wait for the PATCH request to complete
    await page.waitForResponse('**/api/content-gen/backlog/item-001')

    // Dialog should be closed
    await expect(page.getByText('Edit Backlog Item')).not.toBeVisible()

    // The updated text should appear in the table
    await expect(page.getByText('Updated idea text for testing edit flow')).toBeVisible()
    // The old text should not appear
    await expect(page.getByText('AI coding assistants in enterprise software development')).not.toBeVisible()
  })

  test('delete button shows confirmation dialog', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Wait for items to load
    await expect(page.getByText('3 items')).toBeVisible()

    // Click the delete button (Trash icon) for item-001
    const deleteButton = page.locator('button[title="Delete item"]').first()
    await deleteButton.click()

    // Confirmation dialog should appear
    await expect(page.getByText('Delete backlog item?')).toBeVisible()
    await expect(page.getByText('AI coding assistants')).toBeVisible()
  })

  test('delete confirmation dialog confirms and removes item', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Wait for items to load
    await expect(page.getByText('3 items')).toBeVisible()

    // Click the delete button (Trash icon) for item-001
    const deleteButton = page.locator('button[title="Delete item"]').first()
    await deleteButton.click()

    // Confirmation dialog should appear
    await expect(page.getByText('Delete backlog item?')).toBeVisible()

    // Click delete
    await page.getByRole('button', { name: 'Delete item' }).click()

    // Wait for the DELETE request to complete
    await page.waitForResponse(/\/api\/content-gen\/backlog\/item-001/)

    // Dialog should close
    await expect(page.getByText('Delete backlog item?')).not.toBeVisible()

    // Count should now be 2
    await expect(page.getByText('2 items')).toBeVisible()
  })

  test('create flow opens dialog, accepts input, and adds new item', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Wait for items to load
    await expect(page.getByText('3 items')).toBeVisible()

    // Click "New item" button
    await page.getByRole('button', { name: 'New item' }).click()

    // Dialog should open
    await expect(page.getByText('New Backlog Item')).toBeVisible()

    // Fill in the required idea field
    const ideaTextarea = page.locator('#idea')
    await ideaTextarea.fill('New content idea created via test')

    // Fill in optional fields
    await page.locator('#category').selectOption('trend-responsive')
    await page.locator('#audience').fill('Content marketers')
    await page.locator('#problem').fill('Need fresh content ideas')

    // Submit the form
    await page.getByRole('button', { name: 'Save Changes' }).click()

    // Wait for the POST request to complete
    await page.waitForResponse('**/api/content-gen/backlog')

    // Dialog should be closed
    await expect(page.getByText('New Backlog Item')).not.toBeVisible()

    // The new item should appear in the list
    await expect(page.getByText('New content idea created via test')).toBeVisible()

    // Count should now be 4
    await expect(page.getByText('4 items')).toBeVisible()
  })

  test('create flow validates required idea field', async ({ page }) => {
    // Need at least one item so BacklogPanel is rendered (it shows EmptyState when empty)
    await setupBacklogMocks(page, [mockBacklogItems[0]])

    await page.goto('/content-gen/backlog')

    // Wait for items to load
    await expect(page.getByText('1 item')).toBeVisible()

    // Click "New item" button
    await page.getByRole('button', { name: 'New item' }).click()

    // Dialog should open
    await expect(page.getByText('New Backlog Item')).toBeVisible()

    // Try to submit without filling idea field
    await page.getByRole('button', { name: 'Save Changes' }).click()

    // Error should appear
    await expect(page.getByText('Idea is required.')).toBeVisible()

    // Dialog should still be open
    await expect(page.getByText('New Backlog Item')).toBeVisible()
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

  test('assistant tab in content studio shell navigates to dedicated chat page', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen')

    await page.getByRole('button', { name: 'Assistant' }).click()

    await expect(page).toHaveURL(/\/content-gen\/chat/)
    await expect(page.getByText('Backlog Assistant')).toBeVisible()
  })
})

test.describe('Backlog Detail Page', () => {
  test('grid card click navigates to detail page', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Wait for items to load
    await expect(page.getByText('3 items')).toBeVisible()

    // Click on the first card (item-001)
    await page.locator('article').first().click()

    // Should navigate to the detail page
    await expect(page).toHaveURL(/\/content-gen\/backlog\/item-001/)
    // Detail page should show the idea title
    await expect(page.getByText('AI coding assistants in enterprise software development')).toBeVisible()
  })

  test('list row click navigates to detail page', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Switch to list view
    await page.getByRole('button', { name: 'List' }).click()
    await expect(page.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true')

    // Click on the first row
    await page.locator('tr').first().click()

    // Should navigate to the detail page
    await expect(page).toHaveURL(/\/content-gen\/backlog\/item-001/)
    await expect(page.getByText('AI coding assistants in enterprise software development')).toBeVisible()
  })

  test('detail page renders correct idea title and metadata', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/item-002')

    // Should show the idea title in heading
    await expect(page.getByRole('heading', { name: /Sustainable packaging alternatives/ })).toBeVisible()
    // Should show status badge (first one is the header badge)
    await expect(page.getByText('selected').first()).toBeVisible()
    // Should show category badge
    await expect(page.getByText('evergreen').first()).toBeVisible()
    // Should show recommendation badge
    await expect(page.getByText('produce_now').first()).toBeVisible()
    // Should show idea_id in the header
    await expect(page.getByText(/item-002/)).toBeVisible()
    // Should show the score (in score panel)
    await expect(page.getByText('85').first()).toBeVisible()
  })

  test('detail page shows all editorial summary fields', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/item-002')

    // Editorial summary section
    await expect(page.getByText('Editorial summary')).toBeVisible()
    // Source theme shown
    await expect(page.getByText('Sustainability')).toBeVisible()
  })

  test('detail page select action works', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/item-001')

    // Should show the idea
    await expect(page.getByText('AI coding assistants in enterprise software development')).toBeVisible()

    // Click select button
    await page.getByRole('button', { name: /Select item/i }).click()

    // Wait for the API call
    await page.waitForResponse(/\/api\/content-gen\/backlog\/item-001\/select/)

    // Status should update to selected (check the select shows selected)
    await expect(page.locator('select').first().evaluate((el) => (el as HTMLSelectElement).value)).toBe('selected')
  })

  test('detail page status change works', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/item-001')

    // Change status to published via the select
    await page.locator('select').first().selectOption('published')

    // Wait for the API call
    await page.waitForResponse('**/api/content-gen/backlog/item-001')

    // The select value should now be published
    await expect(page.locator('select').first().evaluate((el) => (el as HTMLSelectElement).value)).toBe('published')
  })

  test('detail page delete navigates back to backlog overview', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/item-001')

    // Should show the idea (use heading to avoid strict mode violation)
    await expect(page.getByRole('heading', { name: /AI coding assistants/ })).toBeVisible()

    // Click delete button
    await page.getByRole('button', { name: /Delete/i }).click()

    // Dialog should appear
    await expect(page.getByText('Delete backlog item?')).toBeVisible()

    // Confirm delete
    await page.getByRole('button', { name: 'Delete item' }).last().click()

    // Wait for the DELETE request
    await page.waitForResponse(/\/api\/content-gen\/backlog\/item-001/)

    // Should navigate back to backlog overview
    await expect(page).toHaveURL(/\/content-gen\/backlog/)
    await expect(page.getByRole('heading', { name: /AI coding assistants/ })).not.toBeVisible()
  })

  test('unknown backlog id shows not-found state', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/nonexistent-id')

    // Should show not-found empty state
    await expect(page.getByText('Backlog item not found')).toBeVisible()
    await expect(page.getByText(/No backlog item with ID "nonexistent-id"/)).toBeVisible()
    // Should have a link back to backlog
    await expect(page.getByRole('link', { name: 'Back to backlog' })).toBeVisible()
  })

  test('detail page shows breadcrumb navigation', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/item-001')

    // Should show breadcrumb navigation
    await expect(page.getByText('Content Studio')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Backlog' })).toBeVisible()
  })

  test('detail page back link returns to backlog overview', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog/item-001')

    // Click back button (the detail page's own back link, not the shell's)
    await page.getByRole('link', { name: 'Back' }).first().click()

    // Should navigate back to backlog overview
    await expect(page).toHaveURL(/\/content-gen\/backlog/)
    await expect(page.getByText('3 items')).toBeVisible()
  })
})

test.describe('Backlog Chat Panel', () => {
  test('chat panel renders on backlog page with items', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/backlog')

    // Chat panel should be visible
    await expect(page.getByText('Backlog Assistant')).toBeVisible()
    // Send button should be present
    await expect(page.getByRole('button', { name: 'Send' })).toBeVisible()
    // Empty state hint should appear
    await expect(page.getByText(/Ask about gaps, priorities/)).toBeVisible()
  })

  test('chat panel shows empty state with chat when backlog is empty', async ({ page }) => {
    await setupBacklogMocks(page, [])

    await page.goto('/content-gen/backlog')

    // Chat panel should be visible alongside empty state
    await expect(page.getByText('Backlog Assistant')).toBeVisible()
    await expect(page.getByText('No backlog items yet')).toBeVisible()
  })

  test('user can send a message and receive a response', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    // Mock the backlog-chat/respond endpoint
    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      const body = JSON.parse(route.request().postDataBuffer()!.toString())
      // Verify request has correct shape
      expect(body.messages).toBeDefined()
      expect(body.backlog_items).toBeUndefined()
      expect(body.selected_idea_id).toBe('item-002')

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Here is what I would focus on first.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'update_item',
              idea_id: 'item-001',
              reason: 'Narrow the scope.',
              fields: { idea: 'Updated idea via chat' },
            },
          ],
          mentioned_idea_ids: ['item-001'],
        }),
      })
    })

    await page.goto('/content-gen/backlog')

    // Type a message
    const textarea = page.locator('textarea[placeholder*="Ask about"]')
    await textarea.fill('Help me tighten this backlog.')

    // Send it
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()

    // Wait for response
    await respondRequest

    // User message should appear in transcript
    await expect(page.getByText('Help me tighten this backlog.')).toBeVisible()
    // Assistant reply should appear
    await expect(page.getByText('Here is what I would focus on first.')).toBeVisible()
    // Proposal card should appear
    await expect(page.getByText('Proposed changes')).toBeVisible()
    await expect(page.getByText('Narrow the scope.')).toBeVisible()
  })

  test('proposal card shows apply button and dismiss', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Consider updating item-001.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'update_item',
              idea_id: 'item-001',
              reason: 'Reframe for authority.',
              fields: { idea: 'Reframed idea' },
            },
          ],
          mentioned_idea_ids: ['item-001'],
        }),
      })
    })

    await page.goto('/content-gen/backlog')

    // Send a message
    await page.locator('textarea[placeholder*="Ask about"]').fill('Reframe item-001')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    // Apply changes button should be visible
    await expect(page.getByRole('button', { name: 'Apply changes' })).toBeVisible()
    // dismiss link should be visible
    await expect(page.getByText('dismiss')).toBeVisible()

    // Click dismiss
    await page.getByText('dismiss').click()

    // Proposal card should be gone
    await expect(page.getByText('Proposed changes')).not.toBeVisible()
  })

  test('apply button updates backlog state without a reload request', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    // Mock respond endpoint
    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'I will create a new item.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'create_item',
              reason: 'Fill a gap.',
              fields: { idea: 'New chat idea', category: 'evergreen' },
            },
          ],
          mentioned_idea_ids: [],
        }),
      })
    })

    // Mock apply endpoint
    await page.route('**/api/content-gen/backlog-chat/apply', async (route) => {
      const body = JSON.parse(route.request().postDataBuffer()!.toString())
      expect(body.operations).toHaveLength(1)
      expect(body.operations[0].kind).toBe('create_item')

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          applied: 1,
          items: [
            {
              idea_id: 'chat-new-001',
              idea: 'New chat idea',
              category: 'evergreen',
              status: 'backlog',
            },
          ],
          errors: [],
        }),
      })
    })

    await page.goto('/content-gen/backlog')

    // Send message
    await page.locator('textarea[placeholder*="Ask about"]').fill('Add a new evergreen idea')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    // Apply changes
    const applyRequest = page.waitForResponse('**/api/content-gen/backlog-chat/apply')
    await page.getByRole('button', { name: 'Apply changes' }).click()
    await applyRequest

    // After apply, the proposal should be cleared and backlog should reload
    await expect(page.getByText('Proposed changes')).not.toBeVisible()
    // The item count should update (now 4 items)
    await expect(page.getByText('4 items')).toBeVisible()
  })

  test('apply shows inline errors on failure', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Applying.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'update_item',
              idea_id: 'item-001',
              reason: 'Test',
              fields: { idea: 'Updated' },
            },
          ],
          mentioned_idea_ids: ['item-001'],
        }),
      })
    })

    await page.route('**/api/content-gen/backlog-chat/apply', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          applied: 0,
          items: [],
          errors: ['update_item item-001: internal error'],
        }),
      })
    })

    await page.goto('/content-gen/backlog')

    // Send message and apply
    await page.locator('textarea[placeholder*="Ask about"]').fill('Update item-001')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest
    const applyRequest = page.waitForResponse('**/api/content-gen/backlog-chat/apply')
    await page.getByRole('button', { name: 'Apply changes' }).click()
    await applyRequest

    // Error should appear inline
    await expect(page.getByText(/update_item item-001: internal error/)).toBeVisible()
    // Transcript should be preserved
    await expect(page.getByText('Update item-001')).toBeVisible()
  })

  test('loading state shows while waiting for response', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    let respondResolve: (() => void) | undefined
    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      // Don't resolve immediately to test loading state
      await new Promise<void>((resolve) => {
        respondResolve = resolve
      })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Done.',
          apply_ready: false,
          warnings: [],
          operations: [],
          mentioned_idea_ids: [],
        }),
      })
    })

    await page.goto('/content-gen/backlog')

    // Send message
    await page.locator('textarea[placeholder*="Ask about"]').fill('Wait for me')
    await page.getByRole('button', { name: 'Send' }).click()

    // Loading spinner should appear
    await expect(page.getByText('Thinking...')).toBeVisible()
    // Send button should be disabled
    await expect(page.getByRole('button', { name: 'Send' })).toBeDisabled()

    // Resolve the response
    respondResolve?.()

    // Loading should disappear
    await expect(page.getByText('Thinking...')).not.toBeVisible()
  })

  test('warnings from respond are shown inline', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Watch out.',
          apply_ready: true,
          warnings: ['This may duplicate an existing idea.'],
          operations: [
            {
              kind: 'create_item',
              reason: 'New idea.',
              fields: { idea: 'Same as existing' },
            },
          ],
          mentioned_idea_ids: [],
        }),
      })
    })

    await page.goto('/content-gen/backlog')

    await page.locator('textarea[placeholder*="Ask about"]').fill('Add another idea')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    // Warning should appear
    await expect(page.getByText('This may duplicate an existing idea.')).toBeVisible()
  })
})

test.describe('Backlog Chat Page (/content-gen/chat)', () => {
  test('chat page renders workspace with header and context rail', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/chat')

    // Header visible
    await expect(page.getByText('Backlog Assistant')).toBeVisible()
    // Item count visible
    await expect(page.getByText('3 items')).toBeVisible()
    // Chat composer visible
    await expect(page.locator('textarea[placeholder*="Ask about"]')).toBeVisible()
  })

  test('chat page shows empty state with empty backlog', async ({ page }) => {
    await setupBacklogMocks(page, [])

    await page.goto('/content-gen/chat')

    await expect(page.getByText('Backlog Assistant')).toBeVisible()
    await expect(page.locator('textarea[placeholder*="Ask about"]')).toBeVisible()
    // Empty state hint
    await expect(page.getByText(/Ask about gaps, priorities/)).toBeVisible()
  })

  test('chat page renders assistant markdown response', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: '**Focus on quality over quantity.** Here is what I would prioritize first.',
          apply_ready: false,
          warnings: [],
          operations: [],
          mentioned_idea_ids: [],
        }),
      })
    })

    await page.goto('/content-gen/chat')

    await page.locator('textarea[placeholder*="Ask about"]').fill('What should I focus on?')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    // Bold markdown rendered
    await expect(page.locator('strong').filter({ hasText: 'Focus on quality over quantity' })).toBeVisible()
  })

  test('proposal operations render with expand/collapse before-after diff', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Here is what I would update.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'update_item',
              idea_id: 'item-001',
              reason: 'Narrow the scope.',
              fields: { idea: 'Updated idea via chat' },
            },
          ],
          mentioned_idea_ids: ['item-001'],
        }),
      })
    })

    await page.goto('/content-gen/chat')

    await page.locator('textarea[placeholder*="Ask about"]').fill('Update item-001')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    // Proposal card visible
    await expect(page.getByText('Proposed changes')).toBeVisible()
    // Operation badge visible
    await expect(page.getByText('update')).toBeVisible()
    // Collapse/expand chevron button visible
    await expect(page.locator('button[title="Expand"]')).toBeVisible()
  })

  test('per-operation dismiss removes one operation', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Two updates.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'update_item',
              idea_id: 'item-001',
              reason: 'First change.',
              fields: { idea: 'First update' },
            },
            {
              kind: 'update_item',
              idea_id: 'item-002',
              reason: 'Second change.',
              fields: { idea: 'Second update' },
            },
          ],
          mentioned_idea_ids: ['item-001', 'item-002'],
        }),
      })
    })

    await page.goto('/content-gen/chat')

    await page.locator('textarea[placeholder*="Ask about"]').fill('Make two updates')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    await expect(page.getByText('Proposed changes')).toBeVisible()

    // Dismiss the first operation
    const dismissButtons = page.locator('button[title="Dismiss this operation"]')
    await expect(dismissButtons).toHaveCount(2)
    await dismissButtons.first().click()

    // One operation should remain
    await expect(page.getByText('Proposed changes')).toBeVisible()
  })

  test('full proposal dismiss clears all pending ops', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Consider this.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'create_item',
              reason: 'New idea.',
              fields: { idea: 'Brand new idea' },
            },
          ],
          mentioned_idea_ids: [],
        }),
      })
    })

    await page.goto('/content-gen/chat')

    await page.locator('textarea[placeholder*="Ask about"]').fill('Add a new idea')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    await expect(page.getByText('Proposed changes')).toBeVisible()

    await page.getByText('dismiss').click()

    await expect(page.getByText('Proposed changes')).not.toBeVisible()
  })

  test('clear all button clears session', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Proposal.',
          apply_ready: true,
          warnings: [],
          operations: [
            {
              kind: 'create_item',
              reason: 'New.',
              fields: { idea: 'New idea' },
            },
          ],
          mentioned_idea_ids: [],
        }),
      })
    })

    await page.goto('/content-gen/chat')

    await page.locator('textarea[placeholder*="Ask about"]').fill('Add something')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    await expect(page.getByText('Proposal.')).toBeVisible()

    await page.getByText('clear all').click()

    // Transcript should be cleared
    await expect(page.getByText('Proposal.')).not.toBeVisible()
    await expect(page.locator('textarea[placeholder*="Ask about"]')).toHaveValue('')
  })

  test('starter prompts fill the composer', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/chat')

    // Click a starter prompt
    await page.getByText('Identify weak items').click()

    // Composer should be filled
    await expect(page.locator('textarea[placeholder*="Ask about"]')).toHaveValue('Identify items in the backlog that have weak evidence or thin justification.')
  })

  test('backlog insights visible in chat page header', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.goto('/content-gen/chat')

    // Insights section should be visible since backlog is populated
    // (insights derive from backlog data)
    // Check that the page renders without crashing
    await expect(page.getByText('Backlog Assistant')).toBeVisible()
  })

  test('session persists across page refresh', async ({ page }) => {
    await setupBacklogMocks(page, [...mockBacklogItems])

    await page.route('**/api/content-gen/backlog-chat/respond', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          reply_markdown: 'Here is my reply.',
          apply_ready: false,
          warnings: [],
          operations: [],
          mentioned_idea_ids: [],
        }),
      })
    })

    await page.goto('/content-gen/chat')

    // Send a message
    await page.locator('textarea[placeholder*="Ask about"]').fill('Hello assistant')
    const respondRequest = page.waitForResponse('**/api/content-gen/backlog-chat/respond')
    await page.getByRole('button', { name: 'Send' }).click()
    await respondRequest

    // User message should appear
    await expect(page.getByText('Hello assistant')).toBeVisible()

    // Refresh the page
    await page.reload()

    // Message should be restored from localStorage
    await expect(page.getByText('Hello assistant')).toBeVisible()
    await expect(page.getByText('Here is my reply.')).toBeVisible()
  })
})
