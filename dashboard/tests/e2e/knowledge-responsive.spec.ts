import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const graphSnapshot = {
  exported_at: '2026-08-08T00:00:00Z',
  nodes: [
    {
      id: 'node-session',
      kind: 'session',
      label: 'Mobile research session',
      properties: { status: 'completed' },
    },
    {
      id: 'node-source',
      kind: 'source',
      label: 'Responsive source',
      properties: { url: 'https://example.com/research' },
    },
  ],
  edges: [
    {
      id: 'edge-cited',
      kind: 'cited',
      source_id: 'node-session',
      target_id: 'node-source',
      properties: {},
    },
  ],
};

async function mockKnowledgeApis(page: Page) {
  await page.route('**/api/knowledge/graph', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(graphSnapshot),
    });
  });

  await page.route('**/api/knowledge/nodes/node-session/neighbors', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        node: graphSnapshot.nodes[0],
        neighbors: [graphSnapshot.nodes[1]],
        edges: graphSnapshot.edges,
      }),
    });
  });
}

async function openKnowledgeGraph(page: Page) {
  await mockKnowledgeApis(page);
  await page.goto('/knowledge');
  await page.getByRole('button', { name: 'Load Graph' }).click();
  await expect(page.getByRole('group', { name: 'Knowledge graph' })).toBeVisible();
}

for (const width of [320, 375, 768]) {
  test(`Knowledge workspace reflows without clipping at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 768 ? 1024 : 844 });
    await openKnowledgeGraph(page);

    const filterDisclosure = page.locator('details').filter({ hasText: 'Node types' });
    const filterSummary = filterDisclosure.locator('summary');
    const graphRegion = page.getByTestId('knowledge-graph-region');
    const inspector = page.getByTestId('knowledge-node-inspector');

    await expect(filterSummary).toBeVisible();
    await expect(filterDisclosure).not.toHaveAttribute('open', '');

    const [summaryBox, graphBox, inspectorBox] = await Promise.all([
      filterSummary.boundingBox(),
      graphRegion.boundingBox(),
      inspector.boundingBox(),
    ]);

    expect(summaryBox?.height ?? 0).toBeGreaterThanOrEqual(44);
    expect(graphBox?.width ?? 0).toBeGreaterThanOrEqual(width - 32);
    expect(graphBox?.height ?? 0).toBeGreaterThanOrEqual(352);
    expect(inspectorBox?.y ?? 0).toBeGreaterThanOrEqual(
      (graphBox?.y ?? 0) + (graphBox?.height ?? 0) - 1,
    );

    const pageWidth = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      main: document.querySelector('main')?.scrollWidth ?? 0,
    }));
    expect(Math.max(pageWidth.document, pageWidth.body, pageWidth.main)).toBeLessThanOrEqual(
      pageWidth.viewport + 1,
    );

    await filterSummary.click();
    await expect(filterDisclosure).toHaveAttribute('open', '');

    const sessionFilter = page.getByRole('button', { name: 'session', exact: true });
    const sessionFilterBox = await sessionFilter.boundingBox();
    expect(sessionFilterBox?.height ?? 0).toBeGreaterThanOrEqual(44);

    await sessionFilter.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: 'query', exact: true })).toHaveAttribute(
      'aria-pressed',
      'false',
    );

    const sessionNode = page.getByRole('button', {
      name: 'session: Mobile research session',
    });
    const nodeBox = await sessionNode.boundingBox();
    expect(nodeBox?.width ?? 0).toBeGreaterThanOrEqual(44);
    expect(nodeBox?.height ?? 0).toBeGreaterThanOrEqual(44);

    await sessionNode.focus();
    await page.keyboard.press('Enter');
    await expect(inspector.getByText('Mobile research session', { exact: true })).toBeVisible();
  });
}

test('Knowledge workspace preserves its three-pane desktop layout', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openKnowledgeGraph(page);

  const filterSummary = page.locator('details summary').filter({ hasText: 'Node types' });
  const search = page.getByLabel('Search knowledge graph nodes');
  const graph = page.getByTestId('knowledge-graph-region');
  const inspector = page.getByTestId('knowledge-node-inspector');

  await expect(filterSummary).toBeHidden();
  await expect(page.getByRole('button', { name: 'session', exact: true })).toBeVisible();

  const [searchBox, graphBox, inspectorBox] = await Promise.all([
    search.boundingBox(),
    graph.boundingBox(),
    inspector.boundingBox(),
  ]);

  expect(graphBox?.x ?? 0).toBeGreaterThan((searchBox?.x ?? 0) + (searchBox?.width ?? 0));
  expect(inspectorBox?.x ?? 0).toBeGreaterThan((graphBox?.x ?? 0) + (graphBox?.width ?? 0));
  expect(Math.abs((graphBox?.y ?? 0) - (inspectorBox?.y ?? 0))).toBeLessThanOrEqual(1);
});

test('Knowledge mobile controls meet the accessibility baseline @a11y', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 844 });
  await openKnowledgeGraph(page);

  await page.getByText('Graph data', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Relationships' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'cited' })).toBeVisible();

  const results = await new AxeBuilder({ page })
    .include('main')
    .withTags(['wcag2a', 'wcag2aa'])
    .disableRules(['color-contrast'])
    .analyze();

  expect(results.violations).toEqual([]);
});
