import { expect, test } from "@playwright/test";

import { mockDashboardApis, mockSessions } from "./dashboard-mocks";
import { SCENARIOS, getScenario } from "./scenarios";
import { setupTestPage } from "./test-fixtures";

test("home page exposes the control-room structure and launch presets @smoke", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/");

  await expect(page).toHaveTitle(/CC Deep Research/);
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
  await expect(page.getByText("Running now", { exact: true })).toBeVisible();
  await expect(page.getByText("Failed or interrupted", { exact: true })).toBeVisible();
  await expect(page.getByText("Reports ready", { exact: true })).toBeVisible();
  await expect(page.getByText("Fast verification for a claim, update, or short question.")).toBeVisible();
  await expect(page.getByText("Balanced coverage for most day-to-day research requests.")).toBeVisible();
  await expect(page.getByText("Broader collection and more synthesis room for complex topics.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Running" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Needs Attention" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Report Ready" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Archived" })).toBeVisible();
});

test("keyboard shortcuts navigate quickly and stay out of text inputs", async ({ page }) => {
  await setupTestPage(page, { customSessions: mockSessions });

  await page.goto("/session/research-report-003");

  await expect(page.getByRole("button", { name: /Palette · GH home · \/ search/i })).toBeVisible();
  await page.getByRole("button", { name: /Palette · GH home · \/ search/i }).click();
  await expect(page.getByPlaceholder("Search commands...")).toBeVisible();
  await page.keyboard.press("Escape");

  await page.keyboard.press("g");
  await page.keyboard.press("m");
  await expect(page).toHaveURL(/\/session\/research-report-003\/monitor$/);

  await page.keyboard.press("g");
  await page.keyboard.press("r");
  await expect(page).toHaveURL(/\/session\/research-report-003\/report$/);

  await page.goto("/");

  const queryField = page.getByLabel("Research Query");
  await queryField.focus();
  await queryField.press("/");
  await expect(queryField).toBeFocused();
  await expect(page.locator("[data-session-search]")).not.toBeFocused();

  await queryField.evaluate((element) => {
    (element as HTMLTextAreaElement).blur();
  });
  await page.keyboard.press("/");
  await expect(page.locator("[data-session-search]")).toBeFocused();
});

test("launch form submits preset-derived options and prompt overrides", async ({ page }) => {
  await mockDashboardApis(page);

  let requestBody: Record<string, unknown> | null = null;
  await page.route("**/api/research-runs", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "research-report-003",
        status: "running",
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: /Quick factual check/i }).click();
  await page.getByLabel("Research Query").fill("Check whether the ECB changed its inflation forecast today.");
  await page.getByRole("button", { name: /Operator Prompt Overrides/i }).click();
  await page.getByLabel("Analyzer Prompt Prefix", { exact: true }).fill("Prioritize central-bank sources.");
  await page.getByRole("button", { name: /Start Quick factual check/i }).click();

  await expect(page).toHaveURL(/\/session\/research-report-003\/monitor$/);
  await expect(page.getByText("Run started")).toBeVisible();
  expect(requestBody).toMatchObject({
    depth: "quick",
    min_sources: 3,
    realtime_enabled: true,
    agent_prompt_overrides: {
      analyzer: {
        prompt_prefix: "Prioritize central-bank sources.",
      },
    },
  });
});

test("compare mode guides selection and opens the integrated compare route", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Start Compare" }).click();

  await expect(page.getByText("Compare mode is active")).toBeVisible();
  await page.getByLabel("Compare session Stablecoin Banking Landscape").click();
  await expect(page.getByText("Baseline locked: Stablecoin Banking Landscape.")).toBeVisible();
  await page.getByLabel("Compare session Energy Grid Contagion Deep Dive").click();

  await expect(page.getByText("Comparison ready")).toBeVisible();
  await page.getByRole("button", { name: "View Comparison" }).click();

  await expect(page).toHaveURL(/\/compare\?a=research-report-003&b=research-deep-004$/);
  await expect(page.getByRole("heading", { name: "Session Comparison" })).toBeVisible();
  await expect(page.getByText("Operator summary")).toBeVisible();
  await expect(page.getByText("Material changes")).toBeVisible();
});

test("compare mode suggests a stronger baseline when the selected run needs explanation", async ({
  page,
}) => {
  await mockDashboardApis(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Start Compare" }).click();
  await page.getByLabel("Compare session Broken Reuters Fact Check").click();

  await expect(page.getByText("Suggested baseline: Stablecoin Banking Landscape")).toBeVisible();
  await page.getByRole("button", { name: "Use Suggested Baseline" }).click();

  await expect(page.getByText("A: Stablecoin Banking Landscape")).toBeVisible();
  await expect(page.getByText("B: Broken Reuters Fact Check")).toBeVisible();
});

test("compare route suggests a same-query baseline when the current one is weak", async ({
  page,
}) => {
  await mockDashboardApis(page, {
    sessions: [
      ...mockSessions,
      {
        session_id: "research-report-007",
        label: "Stablecoin Banking Landscape Follow-up",
        created_at: "2026-04-05T09:10:00Z",
        total_time_ms: 50200,
        total_sources: 11,
        status: "completed",
        active: false,
        event_count: 62,
        last_event_at: "2026-04-05T09:10:52Z",
        query: "Summarize the current banking-access landscape for major stablecoin issuers.",
        depth: "standard",
        completed_at: "2026-04-05T09:10:52Z",
        has_session_payload: true,
        has_report: true,
        archived: false,
      },
    ],
  });

  await page.goto("/");
  await page.goto("/compare?a=research-history-006&b=research-report-003");

  await expect(
    page.getByRole("heading", { name: "Alternative baseline suggested" })
  ).toBeVisible();
  await expect(page.getByText("Suggested baselines for Session B")).toBeVisible();
  await expect(
    page.getByText("Stablecoin Banking Landscape Follow-up", { exact: true })
  ).toBeVisible();
  await expect(page.getByText("Same query baseline")).toBeVisible();
  await expect(page.getByText("Inspect next")).toBeVisible();
});

test("session workspace navigation covers overview, monitor, and report views", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/session/research-report-003");

  await expect(page.getByRole("heading", { name: "Session Overview" })).toBeVisible();
  await expect(page.getByText("Stablecoin Banking Landscape")).toBeVisible();

  await page.getByRole("link", { name: "Monitor" }).click();
  await expect(page).toHaveURL(/\/session\/research-report-003\/monitor$/);
  await expect(page.getByRole("heading", { name: "Telemetry Monitor" })).toBeVisible();
  await expect(page.getByText("Telemetry Explorer")).toBeVisible();

  await page.getByRole("link", { name: "Report" }).click();
  await expect(page).toHaveURL(/\/session\/research-report-003\/report$/);
  await expect(page.getByRole("heading", { name: "Session Report" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Stablecoin Banking Landscape" })).toBeVisible();
});

test("monitor labels completed sessions as historical-only", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/session/research-report-003/monitor");

  await expect(page.getByText("Viewing historical telemetry only")).toBeVisible();
  await expect(page.getByText("Historical", { exact: true })).toBeVisible();
});

test("monitor reconnects after a dropped socket and keeps deduplicated events", async ({ page }) => {
  await page.addInitScript(() => {
    const realSetTimeout = window.setTimeout.bind(window);
    const schedule = (callback: () => void, delay = 0) =>
      realSetTimeout(callback, Math.min(delay, 25));
    const NativeWebSocket = window.WebSocket;

    let connectionAttempt = 0;

    class MockSessionWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;

      readyState = MockSessionWebSocket.CONNECTING;
      url: string;
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      constructor(url: string) {
        this.url = url;
        connectionAttempt += 1;

        if (connectionAttempt === 1) {
          schedule(() => {
            this.readyState = MockSessionWebSocket.CLOSED;
            this.onerror?.(new Event("error"));
            this.onclose?.(new CloseEvent("close", { code: 1011, reason: "mock disconnect" }));
          }, 10);
          return;
        }

        schedule(() => {
          this.readyState = MockSessionWebSocket.OPEN;
          this.onopen?.(new Event("open"));
        }, 10);
      }

      send(payload: string) {
        const message = JSON.parse(payload) as { type: string };
        if (message.type !== "get_history" || this.readyState !== MockSessionWebSocket.OPEN) {
          return;
        }

        const baseEvent = {
          parent_event_id: "research-running-001-1",
          timestamp: "2026-04-06T01:12:03Z",
          session_id: "research-running-001",
          category: "tool",
          agent_id: "analyzer",
          metadata: { provider: "tavily", count: 7 },
        };

        schedule(() => {
          this.onmessage?.(
            new MessageEvent("message", {
              data: JSON.stringify({
                type: "history",
                events: [
                  {
                    event_id: "research-running-001-1",
                    parent_event_id: null,
                    sequence_number: 1,
                    timestamp: "2026-04-06T01:00:00Z",
                    session_id: "research-running-001",
                    event_type: "research.started",
                    category: "agent",
                    name: "research-started",
                    status: "started",
                    duration_ms: null,
                    agent_id: "analyzer",
                    metadata: { phase: "intake" },
                  },
                  {
                    event_id: "research-running-001-2",
                    sequence_number: 2,
                    event_type: "source.collected",
                    name: "source-collected",
                    status: "completed",
                    duration_ms: 1200,
                    ...baseEvent,
                  },
                  {
                    event_id: "research-running-001-3",
                    sequence_number: 3,
                    ...baseEvent,
                    event_type: "report.generated",
                    name: "report-generated",
                    status: "completed",
                    duration_ms: null,
                    category: "llm",
                  },
                ],
              }),
            })
          );

          const newEvent = {
            type: "event",
            event: {
              event_id: "research-running-001-4",
              sequence_number: 4,
              event_type: "source.collected",
              name: "source-collected",
              status: "completed",
              duration_ms: 900,
              ...baseEvent,
            },
          };

          this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(newEvent) }));
          this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(newEvent) }));
        }, 10);
      }

      close() {
        this.readyState = MockSessionWebSocket.CLOSED;
      }
    }

    const MockWebSocket = function (
      url: string | URL,
      protocols?: string | string[]
    ) {
      const normalizedUrl = String(url);
      if (normalizedUrl.includes("/session/research-running-001")) {
        return new MockSessionWebSocket(normalizedUrl);
      }
      return protocols
        ? new NativeWebSocket(url, protocols)
        : new NativeWebSocket(url);
    } as unknown as typeof window.WebSocket;

    Object.assign(MockWebSocket, NativeWebSocket, {
      CONNECTING: NativeWebSocket.CONNECTING,
      OPEN: NativeWebSocket.OPEN,
      CLOSING: NativeWebSocket.CLOSING,
      CLOSED: NativeWebSocket.CLOSED,
    });

    Object.defineProperty(window, "WebSocket", {
      configurable: true,
      writable: true,
      value: MockWebSocket,
    });
  });

  await mockDashboardApis(page);
  await page.goto("/session/research-running-001/monitor");

  await expect(page.getByText("Live", { exact: true })).toBeVisible();
  await expect(page.getByText("4 events buffered. Streaming live updates.")).toBeVisible();
});

test("session archive and delete actions emit operator feedback", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/");

  const stablecoinCard = page.locator("article").filter({ hasText: "Stablecoin Banking Landscape" });
  await stablecoinCard.getByRole("button", { name: "Archive" }).click();
  await expect(page.getByText("Session archived")).toBeVisible();

  const telemetryCard = page.locator("article").filter({ hasText: "Telemetry Dry Run" });
  await telemetryCard.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("heading", { name: "Delete Session" })).toBeVisible();
  await page.getByRole("button", { name: "Delete Session" }).click();

  await expect(page.getByText("Session deleted")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Telemetry Dry Run" })).toHaveCount(0);
});

test("home page shows the empty state when no sessions are available", async ({ page }) => {
  await setupTestPage(page, { customSessions: [] });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Ready to research" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No sessions available" })).toBeVisible();
});

test("session list saved views persist, apply, and delete across reloads", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/");

  const activityFilter = page.getByRole("button", { name: "All Sessions" });
  await activityFilter.click();

  await expect(page.getByRole("heading", { name: "Live NVIDIA Supply Chain Watch" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Stablecoin Banking Landscape" })).not.toBeVisible();

  await page.getByTestId("session-view-save-current").click();
  await page.getByTestId("session-view-name").fill("Active only");
  await page.getByTestId("session-view-save").click();

  await page.getByRole("button", { name: "Active Only" }).click();
  await expect(page.getByRole("heading", { name: "Stablecoin Banking Landscape" })).toBeVisible();

  await page.reload();
  await page.getByTestId("session-view-select").selectOption("Active only");
  await page.getByTestId("session-view-apply").click();

  await expect(page.getByRole("button", { name: "Active Only" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Live NVIDIA Supply Chain Watch" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Stablecoin Banking Landscape" })).not.toBeVisible();

  await page.getByTestId("session-view-delete").click();
  await page.reload();

  const sessionViewOptions = await page
    .getByTestId("session-view-select")
    .locator("option")
    .allTextContents();
  expect(sessionViewOptions).not.toContain("Active only");
});

test("telemetry saved views sanitize stale filters and persist valid presets", async ({ page }) => {
  await page.addInitScript(() => {
    const storageKey = "ccdr.dashboard.saved-telemetry-views";
    if (window.localStorage.getItem(storageKey)) {
      return;
    }

    window.localStorage.setItem(
      storageKey,
      JSON.stringify([
        {
          name: "Stale telemetry",
          value: {
            phase: ["missing-phase"],
            agent: ["ghost-agent"],
            tool: ["missing-tool"],
            provider: ["ghost-provider"],
            status: ["ghost-status"],
            eventTypes: ["ghost-event"],
            timeRange: null,
          },
          updatedAt: "2026-04-06T00:00:00.000Z",
        },
      ])
    );
  });

  await mockDashboardApis(page);
  await page.goto("/session/research-report-003/monitor");

  await page.getByRole("button", { name: /Filters/ }).click();
  await page.getByTestId("telemetry-view-select").selectOption("Stale telemetry");
  await page.getByTestId("telemetry-view-apply").click();

  await expect(
    page.getByText("Showing all telemetry data. Expand filters only when you need to narrow the view.")
  ).toBeVisible();
  await expect(page.getByText("Agent: analyzer")).not.toBeVisible();

  await page.getByTestId("telemetry-filter-agent").selectOption("analyzer");
  await expect(page.getByText("Agent: analyzer")).toBeVisible();

  await page.getByTestId("telemetry-view-save-current").click();
  await page.getByTestId("telemetry-view-name").fill("Analyzer sweep");
  await page.getByTestId("telemetry-view-save").click();
  await expect(
    page.getByTestId("telemetry-view-select").locator("option")
  ).toContainText(["Analyzer sweep"]);

  await page.getByTestId("telemetry-filter-agent").selectOption("");
  await expect(
    page.getByText("Showing all telemetry data. Expand filters only when you need to narrow the view.")
  ).toBeVisible();

  await page.reload();
  await expect(page.getByText("Telemetry Explorer")).toBeVisible();
  await page.getByRole("button", { name: /Filters/ }).click();
  await page.getByTestId("telemetry-view-select").selectOption("Analyzer sweep");
  await page.getByTestId("telemetry-view-apply").click();

  await expect(page.getByText("Agent: analyzer")).toBeVisible();

  await page.getByTestId("telemetry-view-delete").click();
  await page.reload();
  await page.getByRole("button", { name: /Filters/ }).click();

  const telemetryViewOptions = await page
    .getByTestId("telemetry-view-select")
    .locator("option")
    .allTextContents();
  expect(telemetryViewOptions).not.toContain("Analyzer sweep");
});

test("compare route shows a clear error state for invalid selections", async ({ page }) => {
  await setupTestPage(page, { customSessions: mockSessions });

  await page.goto("/compare?a=research-report-003&b=research-report-003");

  await expect(page.getByRole("heading", { name: "Invalid comparison" })).toBeVisible();
  await expect(page.getByText("Pick two different sessions")).toBeVisible();
});
