import { expect, test, type Page } from "@playwright/test";

async function mockSessionsList(page: Page) {
  await page.route("**/api/sessions*", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.has("include_derived")) {
      await route.fallback();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        sessions: [],
        total: 0,
        next_cursor: null,
      }),
    });
  });
}

async function mockRunStatus(page: Page, runId: string) {
  await page.route(`**/api/research-runs/${runId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        status: "running",
        created_at: "2026-03-25T00:00:00Z",
        session_id: "prompt-session",
        stop_requested: false,
      }),
    });
  });
}

test("start form resets prompt overrides and omits empty payloads", async ({ page }) => {
  let requestBody: Record<string, unknown> | null = null;

  await mockSessionsList(page);
  await mockRunStatus(page, "run-empty");
  await page.route("**/api/research-runs", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "run-empty",
        status: "queued",
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Advanced Settings (Agent Prompts)" }).click();
  await page.getByLabel("Analyzer Prompt Prefix", { exact: true }).fill("Prioritize filings");
  await page.getByRole("button", { name: "Reset" }).nth(0).click();
  await expect(page.getByLabel("Analyzer Prompt Prefix", { exact: true })).toHaveValue("");

  await page.getByLabel("Research Query").fill("What changed in cloud margins?");
  await page.getByRole("button", { name: "Start Research" }).click();
  await page.waitForURL("**/session/run-empty/monitor");

  expect(requestBody).not.toBeNull();
  expect(requestBody).not.toHaveProperty("agent_prompt_overrides");
});

test("start form serializes supported prompt overrides into the research request", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | null = null;

  await mockSessionsList(page);
  await mockRunStatus(page, "run-overrides");
  await page.route("**/api/research-runs", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "run-overrides",
        status: "queued",
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Advanced Settings (Agent Prompts)" }).click();
  await expect(
    page.getByText(
      "V1 support is limited to Analyzer, Deep Analyzer, and Report Quality Evaluator."
    )
  ).toBeVisible();
  await page
    .getByLabel("Analyzer Prompt Prefix", { exact: true })
    .fill("Focus on primary sources.");
  await page
    .getByLabel("Report Quality Evaluator Prompt Prefix", { exact: true })
    .fill("Score structure before prose.");
  await page.getByLabel("Research Query").fill("Summarize the latest earnings call.");
  await page.getByRole("button", { name: "Start Research" }).click();
  await page.waitForURL("**/session/run-overrides/monitor");

  expect(requestBody).toMatchObject({
    query: "Summarize the latest earnings call.",
    realtime_enabled: true,
    agent_prompt_overrides: {
      analyzer: {
        prompt_prefix: "Focus on primary sources.",
      },
      report_quality_evaluator: {
        prompt_prefix: "Score structure before prose.",
      },
    },
  });
});

test("session monitor shows configured prompt metadata from session detail", async ({ page }) => {
  await page.route("**/api/sessions/prompt-session*", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.has("include_derived")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session: {
            session_id: "prompt-session",
            label: "Prompt Session",
            created_at: "2026-03-25T00:00:00Z",
            total_time_ms: 1200,
            total_sources: 4,
            status: "completed",
            active: false,
            event_count: 0,
            last_event_at: "2026-03-25T00:20:00Z",
            query: "Prompt session",
            depth: "standard",
            completed_at: "2026-03-25T00:20:00Z",
            has_session_payload: true,
            has_report: false,
          },
          summary: {
            metadata: {
              prompts: {
                overrides_applied: true,
                effective_overrides: {
                  analyzer: {
                    prompt_prefix: "Focus on management guidance.",
                    system_prompt: null,
                  },
                },
                default_prompts_used: [
                  "deep_analyzer",
                  "report_quality_evaluator",
                ],
              },
            },
          },
          events_page: {
            events: [],
            total: 0,
            has_more: false,
            next_cursor: null,
            prev_cursor: null,
          },
          event_tail: [],
          agent_timeline: [],
          active_phase: null,
          narrative: [],
          critical_path: { nodes: [], edges: [] },
          state_changes: [],
          decisions: [],
          degradations: [],
          failures: [],
          decision_graph: { nodes: [], edges: [], summary: { node_count: 0, edge_count: 0 } },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session: {
          session_id: "prompt-session",
          label: "Prompt Session",
          created_at: "2026-03-25T00:00:00Z",
          total_time_ms: 1200,
          total_sources: 4,
          status: "completed",
          active: false,
          event_count: 0,
          last_event_at: "2026-03-25T00:20:00Z",
          query: "Prompt session",
          depth: "standard",
          completed_at: "2026-03-25T00:20:00Z",
          has_session_payload: true,
          has_report: false,
        },
      }),
    });
  });

  await page.goto("/session/prompt-session/monitor");
  await page.getByRole("button", { name: "Prompts" }).click();

  await expect(page.getByText("Prompt Configuration")).toBeVisible();
  await expect(page.getByText("Custom Prompts Applied")).toBeVisible();
  await expect(page.getByText("Focus on management guidance.")).toBeVisible();
  await expect(page.getByText("Deep Analyzer")).toBeVisible();
  await expect(page.getByText("Report Quality Evaluator")).toBeVisible();
});
