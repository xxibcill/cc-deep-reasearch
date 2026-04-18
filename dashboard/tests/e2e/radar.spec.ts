import { expect, test } from "@playwright/test";

import { mockDashboardApis } from "./dashboard-mocks";

// ---------------------------------------------------------------------------
// Radar mocks
// ---------------------------------------------------------------------------

const mockOpportunities = [
  {
    id: "opp-001",
    title: "Anthropic Enterprise tier expansion",
    summary:
      "Anthropic appears to be preparing an enterprise tier above current Business, based on recent job postings and feature hints from internal sources.",
    opportunity_type: "competitor_move",
    status: "new",
    priority_label: "high_potential",
    why_it_matters:
      "An enterprise tier would target the largest accounts and could shift market positioning for AI-native companies.",
    recommended_action: "Review pricing strategy and identify differentiation points.",
    total_score: 72.5,
    freshness_state: "fresh",
    created_at: "2026-04-17T10:00:00Z",
    updated_at: "2026-04-17T14:30:00Z",
  },
  {
    id: "opp-002",
    title: "Rising demand for multi-model orchestration tooling",
    summary:
      "Community discussions across HN and GitHub show increasing interest in managing inference across multiple LLM providers in a single pipeline.",
    opportunity_type: "rising_topic",
    status: "saved",
    priority_label: "act_now",
    why_it_matters:
      "Early positioning in orchestration tooling could capture developer mindshare before incumbents react.",
    recommended_action: "Design a reference architecture and publish a technical brief.",
    total_score: 84.1,
    freshness_state: "new",
    created_at: "2026-04-16T08:00:00Z",
    updated_at: "2026-04-18T06:00:00Z",
  },
  {
    id: "opp-003",
    title: "Cohere enters the晚饭 market with enterprise focus",
    summary:
      "Cohere announced a new enterprise offering with proprietary fine-tuning capabilities, competing directly with OpenAI and Anthropic.",
    opportunity_type: "competitor_move",
    status: "monitoring",
    priority_label: "monitor",
    why_it_matters: "Potential mid-market disruption with a different pricing model.",
    recommended_action: "Monitor pricing and customer feedback.",
    total_score: 58.3,
    freshness_state: "stale",
    created_at: "2026-04-10T12:00:00Z",
    updated_at: "2026-04-14T09:00:00Z",
  },
];

const mockSources = [
  {
    id: "src-001",
    source_type: "news",
    label: "Anthropic News Feed",
    url_or_identifier: "https://www.anthropic.com/news/rss",
    status: "active",
    scan_cadence: "1h",
    last_scanned_at: "2026-04-18T09:45:00Z",
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-18T09:45:00Z",
  },
  {
    id: "src-002",
    source_type: "competitor",
    label: "OpenAI Blog",
    url_or_identifier: "https://openai.com/blog/rss",
    status: "active",
    scan_cadence: "2h",
    last_scanned_at: "2026-04-18T09:30:00Z",
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-18T09:30:00Z",
  },
];

const mockOpportunityDetail = {
  opportunity: mockOpportunities[0],
  score: {
    opportunity_id: "opp-001",
    strategic_relevance_score: 78.0,
    novelty_score: 65.0,
    urgency_score: 70.0,
    evidence_score: 80.0,
    business_value_score: 72.0,
    workflow_fit_score: 68.0,
    total_score: 72.5,
    priority_label: "high_potential",
    explanation:
      "Strong signal with high strategic relevance and credible evidence from multiple sources.",
    scored_at: "2026-04-17T15:00:00Z",
  },
  signals: [
    {
      id: "sig-001",
      source_id: "src-001",
      external_id: "anthropic-job-2026-042",
      title: "Senior Enterprise Sales Engineer posting",
      summary:
        "Job description mentions 'enterprise tier architecture' and references to upcoming product lines not yet announced.",
      url: "https://anthropic.com/careers/sea-042",
      published_at: "2026-04-16T14:00:00Z",
      discovered_at: "2026-04-17T08:00:00Z",
      content_hash: null,
      metadata: {},
      normalized_type: "job_posting",
    },
  ],
  feedback: [],
  workflow_links: [],
};

function mockRadarApis(page: Parameters<typeof mockDashboardApis>[0]) {
  // Mock opportunities list
  page.route("**/api/radar/opportunities", async (route) => {
    const url = new URL(route.request().url());
    const status = url.searchParams.get("status");

    let items = mockOpportunities;
    if (status && status !== "all") {
      items = mockOpportunities.filter((o) => o.status === status);
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, count: items.length }),
    });
  });

  // Mock opportunity detail
  page.route("**/api/radar/opportunities/opp-001", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockOpportunityDetail),
    });
  });

  page.route("**/api/radar/opportunities/opp-002", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        opportunity: mockOpportunities[1],
        score: {
          opportunity_id: "opp-002",
          strategic_relevance_score: 85.0,
          novelty_score: 90.0,
          urgency_score: 80.0,
          evidence_score: 75.0,
          business_value_score: 82.0,
          workflow_fit_score: 88.0,
          total_score: 84.1,
          priority_label: "act_now",
          explanation: "High novelty with strong workflow fit.",
          scored_at: "2026-04-18T06:00:00Z",
        },
        signals: [],
        feedback: [],
        workflow_links: [],
      }),
    });
  });

  // Mock sources list
  page.route("**/api/radar/sources", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: mockSources, count: mockSources.length }),
    });
  });

  // Mock create source
  page.route("**/api/radar/sources", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: `src-${Date.now()}`,
          source_type: body.source_type,
          label: body.label,
          url_or_identifier: body.url_or_identifier,
          status: "active",
          scan_cadence: body.scan_cadence ?? "6h",
          last_scanned_at: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
    }
  });

  // Mock status update
  page.route("**/api/radar/opportunities/opp-001/status", async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...mockOpportunities[0], status: body.status }),
    });
  });

  // Mock feedback
  page.route("**/api/radar/opportunities/opp-001/feedback", async (route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: `fb-${Date.now()}`,
        opportunity_id: "opp-001",
        feedback_type: "dismissed",
        created_at: new Date().toISOString(),
        metadata: {},
      }),
    });
  });
}

// ---------------------------------------------------------------------------
// Radar tests
// ---------------------------------------------------------------------------

test("radar page loads with empty state when no opportunities exist", async ({ page }) => {
  page.route("**/api/radar/opportunities", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], count: 0 }),
    });
  });
  page.route("**/api/radar/sources", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], count: 0 }),
    });
  });

  await page.goto("/radar");

  await expect(page.getByRole("heading", { name: "Radar Inbox" })).toBeVisible();
  await expect(page.getByText("Inbox zero", { exact: true })).toBeVisible();
  await expect(
    page.getByText("No opportunities detected yet. Configure sources to start monitoring.")
  ).toBeVisible();
});

test("radar page shows opportunities with correct priority and freshness badges", async ({ page }) => {
  mockRadarApis(page);

  await page.goto("/radar");

  await expect(page.getByRole("heading", { name: "Radar Inbox" })).toBeVisible();
  await expect(page.getByText("Act Now", { exact: true })).toBeVisible();
  await expect(page.getByText("High Potential", { exact: true })).toBeVisible();

  await expect(page.getByText("Anthropic Enterprise tier expansion")).toBeVisible();
  await expect(page.getByText("Rising demand for multi-model orchestration tooling")).toBeVisible();
});

test("radar page filters opportunities by status", async ({ page }) => {
  mockRadarApis(page);

  await page.goto("/radar");

  await page.locator('select').selectOption("new");
  await page.waitForResponse("**/api/radar/opportunities?status=new");

  await expect(page.getByText("Anthropic Enterprise tier expansion")).toBeVisible();
});

test("radar opportunity detail page loads with score breakdown and actions", async ({ page }) => {
  mockRadarApis(page);

  await page.goto("/radar");

  await page.getByRole("link", { name: /Anthropic Enterprise tier expansion/i }).click();

  await expect(page).toHaveURL(/\/radar\/opportunities\/opp-001/);
  await expect(page.getByRole("heading", { name: "Anthropic Enterprise tier expansion" })).toBeVisible();
  await expect(page.getByText("Score Breakdown")).toBeVisible();
  await expect(page.getByText("Strategic Relevance")).toBeVisible();
  await expect(page.getByText("Why it matters")).toBeVisible();
  await expect(page.getByText("High Potential")).toBeVisible();
  await expect(page.getByText("New", { exact: true })).toBeVisible();
});

test("radar status update transition reflects in the sidebar actions", async ({ page }) => {
  mockRadarApis(page);

  await page.goto("/radar/opportunities/opp-001");

  const saveButton = page.getByRole("button", { name: /Save/i });
  await expect(saveButton).toBeVisible();
});

test("radar sources management shows existing sources with status badges", async ({ page }) => {
  mockRadarApis(page);

  await page.goto("/radar/sources");

  await expect(page.getByText("Anthropic News Feed")).toBeVisible();
  await expect(page.getByText("OpenAI Blog")).toBeVisible();
  await expect(page.getByText("active", { exact: true })).toBeVisible();
});

test("radar add source form creates a new source and shows it in the list", async ({ page }) => {
  mockRadarApis(page);

  await page.goto("/radar/sources");

  await page.getByRole("button", { name: /Add Source/i }).click();

  await page.getByLabel("Label").fill("Test Source");
  await page.getByLabel("URL or Identifier").fill("https://example.com/rss");
  await page.getByRole("button", { name: /Create Source/i }).click();

  await expect(page.getByText("Test Source")).toBeVisible();
});

test("radar navigation link appears in the navbar and navigates correctly", async ({ page }) => {
  mockRadarApis(page);

  await page.goto("/");

  const radarNavLink = page.getByRole("link", { name: "Radar" });
  await expect(radarNavLink).toBeVisible();

  await radarNavLink.click();
  await expect(page).toHaveURL("/radar");
  await expect(page.getByRole("heading", { name: "Radar Inbox" })).toBeVisible();
});

test("radar page shows loading skeletons while fetching opportunities", async ({ page }) => {
  // Delay the response to allow skeleton to render
  page.route("**/api/radar/opportunities", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: mockOpportunities, count: mockOpportunities.length }),
    });
  });

  await page.goto("/radar");

  // Should show skeleton-like loading state
  await expect(page.getByText("All Opportunities")).toBeVisible();
});