import { expect, test, type Page } from "@playwright/test";

type ConfigResponse = {
  config_path: string;
  file_exists: boolean;
  persisted_config: Record<string, unknown>;
  effective_config: Record<string, unknown>;
  overridden_fields: string[];
  override_sources: Record<string, string[]>;
  secret_fields: Array<{
    field: string;
    persisted_present: boolean;
    effective_present: boolean;
    persisted_count: number;
    effective_count: number;
    overridden: boolean;
  }>;
};

function makeConfigResponse(overrides: Partial<ConfigResponse> = {}): ConfigResponse {
  return {
    config_path: "/tmp/config.yaml",
    file_exists: true,
    persisted_config: {
      search: { providers: ["tavily"], depth: "deep" },
      research: { enable_cross_ref: true },
      search_team: { team_size: 4, parallel_execution: true },
      output: { format: "markdown", save_dir: "./reports" },
      llm: {
        route_defaults: {
          analyzer: "anthropic",
          deep_analyzer: "anthropic",
          report_quality_evaluator: "anthropic",
          reporter: "anthropic",
          default: "anthropic",
        },
        openrouter: { api_key: "********" },
      },
      search_cache: { enabled: false, ttl_seconds: 3600, max_entries: 1000 },
    },
    effective_config: {
      search: { providers: ["tavily"], depth: "deep" },
      research: { enable_cross_ref: true },
      search_team: { team_size: 4, parallel_execution: true },
      output: { format: "markdown", save_dir: "./reports" },
      llm: {
        route_defaults: {
          analyzer: "anthropic",
          deep_analyzer: "anthropic",
          report_quality_evaluator: "anthropic",
          reporter: "anthropic",
          default: "anthropic",
        },
        openrouter: { api_key: "********" },
      },
      search_cache: { enabled: false, ttl_seconds: 3600, max_entries: 1000 },
    },
    overridden_fields: [],
    override_sources: {},
    secret_fields: [
      {
        field: "llm.openrouter.api_key",
        persisted_present: true,
        effective_present: true,
        persisted_count: 1,
        effective_count: 1,
        overridden: false,
      },
    ],
    ...overrides,
  };
}

async function mockSettingsApis(page: Page, config: ConfigResponse) {
  await page.route("**/api/search-cache/stats", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        enabled: false,
        total_entries: 0,
        active_entries: 0,
        expired_entries: 0,
        total_hits: 0,
        ttl_seconds: 3600,
        max_entries: 1000,
        approximate_size_bytes: 0,
      }),
    });
  });

  await page.route("**/api/config", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(config),
      });
      return;
    }

    await route.continue();
  });
}

test("settings page shows persisted vs runtime override state", async ({ page }) => {
  await mockSettingsApis(
    page,
    makeConfigResponse({
      effective_config: {
        search: { providers: ["tavily"], depth: "deep" },
        research: { enable_cross_ref: true },
        search_team: { team_size: 4, parallel_execution: true },
        output: { format: "json", save_dir: "./reports" },
        llm: {
          route_defaults: {
            analyzer: "anthropic",
            deep_analyzer: "anthropic",
            report_quality_evaluator: "anthropic",
            reporter: "anthropic",
            default: "anthropic",
          },
          openrouter: { api_key: "********" },
        },
        search_cache: { enabled: false, ttl_seconds: 3600, max_entries: 1000 },
      },
      overridden_fields: ["output.format"],
      override_sources: { "output.format": ["CC_DEEP_RESEARCH_FORMAT"] },
    })
  );

  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  await expect(page.getByText("Manage the saved defaults used for future runs")).toBeVisible();
  await expect(page.getByText("Runtime currently uses json. Saved config remains markdown. Source: CC_DEEP_RESEARCH_FORMAT.")).toBeVisible();
  await expect(page.getByRole("combobox").filter({ has: page.locator('option[value="markdown"]') }).first()).toBeDisabled();
  await expect(page.getByText("OpenRouter API key")).toBeVisible();
});

test("settings page surfaces save validation errors", async ({ page }) => {
  await mockSettingsApis(page, makeConfigResponse());

  await page.route("**/api/config", async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.fallback();
      return;
    }

    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({
        error: "Config update failed validation.",
        fields: [
          {
            field: "output.save_dir",
            code: "invalid_value",
            message: "Save directory must be a writable path.",
          },
        ],
        conflicts: [],
      }),
    });
  });

  await page.goto("/settings");
  await page.locator('input[value="./reports"]').fill("/root/forbidden");
  await page.getByRole("button", { name: "Save settings" }).click();

  await expect(page.getByText("Save directory must be a writable path.")).toBeVisible();
});

test("settings page resets unsaved draft changes", async ({ page }) => {
  await mockSettingsApis(page, makeConfigResponse());

  await page.goto("/settings");

  const reportDir = page.locator('input[value="./reports"]');
  await reportDir.fill("./draft-reports");
  await expect(page.getByText("Draft: ./draft-reports. Saved now: ./reports. Save writes the persisted config used for future runs.")).toBeVisible();

  await page.getByRole("button", { name: "Reset draft" }).click();

  await expect(reportDir).toHaveValue("./reports");
  await expect(page.getByText("Reset 1 unsaved change back to the persisted config. Runtime overrides stay locked until their environment values change.")).toBeVisible();
});

test("settings page saves config updates and supports secret replace/clear flows", async ({
  page,
}) => {
  const patchBodies: Array<Record<string, unknown>> = [];
  let currentResponse = makeConfigResponse();

  await mockSettingsApis(page, currentResponse);

  await page.route("**/api/config", async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.fallback();
      return;
    }

    const body = route.request().postDataJSON() as {
      updates: Record<string, unknown>;
    };
    patchBodies.push(body.updates);

    if ("output.save_dir" in body.updates) {
      currentResponse = makeConfigResponse({
        persisted_config: {
          ...currentResponse.persisted_config,
          output: { format: "markdown", save_dir: "./custom-reports" },
        },
        effective_config: {
          ...currentResponse.effective_config,
          output: { format: "markdown", save_dir: "./custom-reports" },
        },
      });
    } else if ("llm.openrouter.api_key" in body.updates) {
      const secretPatch = body.updates["llm.openrouter.api_key"] as {
        action: string;
      };
      currentResponse = makeConfigResponse({
        secret_fields: [
          {
            field: "llm.openrouter.api_key",
            persisted_present: secretPatch.action === "replace",
            effective_present: secretPatch.action === "replace",
            persisted_count: secretPatch.action === "replace" ? 1 : 0,
            effective_count: secretPatch.action === "replace" ? 1 : 0,
            overridden: false,
          },
        ],
      });
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(currentResponse),
    });
  });

  await page.goto("/settings");

  await page.locator('input[value="./reports"]').fill("./custom-reports");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText("Saved 1 setting to the persisted config. Future runs will use the updated values.")).toBeVisible();

  const secretRow = page.locator("div").filter({ hasText: "llm.openrouter.api_key" }).first();
  await secretRow.getByRole("button", { name: "Replace", exact: true }).click();
  await page.getByPlaceholder("Enter a replacement value").fill("sk-new");
  await page.getByRole("button", { name: "Save secret" }).click();
  await expect(page.getByText("OpenRouter API key was updated in the persisted config. Future runs will use it.")).toBeVisible();

  await secretRow.getByRole("button", { name: "Clear", exact: true }).click();
  await page.getByRole("button", { name: "Clear secret" }).click();
  await expect(page.getByText("OpenRouter API key was removed from the persisted config. Future runs will no longer load it from saved settings.")).toBeVisible();

  expect(patchBodies[0]["output.save_dir"]).toBe("./custom-reports");
  expect(patchBodies[1]["llm.openrouter.api_key"]).toEqual({
    action: "replace",
    value: "sk-new",
  });
  expect(patchBodies[2]["llm.openrouter.api_key"]).toEqual({
    action: "clear",
  });
});
