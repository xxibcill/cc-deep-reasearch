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

type SearchCacheEntry = {
  cache_key: string;
  provider: string;
  normalized_query: string;
  created_at: string;
  expires_at: string;
  last_accessed_at: string;
  hit_count: number;
  is_expired: boolean;
};

type SearchCacheStatsResponse = {
  enabled: boolean;
  db_path: string;
  db_exists: boolean;
  ttl_seconds: number;
  max_entries: number;
  total_entries: number;
  active_entries: number;
  expired_entries: number;
  total_hits: number;
  approximate_size_bytes: number;
};

type CodexAccountResponse = {
  runtime_status: string;
  authenticated: boolean;
  requires_openai_auth: boolean | null;
  account_type: string | null;
  email: string | null;
  plan_type: string | null;
  error_code: string | null;
  error_message: string | null;
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
        codex: {
          enabled: false,
          model: null,
          reasoning_effort: "medium",
          timeout_seconds: 180,
        },
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
        codex: {
          enabled: false,
          model: null,
          reasoning_effort: "medium",
          timeout_seconds: 180,
        },
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

function makeSearchCacheStats(
  overrides: Partial<SearchCacheStatsResponse> = {}
): SearchCacheStatsResponse {
  return {
    enabled: false,
    db_path: "/tmp/search-cache.sqlite3",
    db_exists: false,
    ttl_seconds: 3600,
    max_entries: 1000,
    total_entries: 0,
    active_entries: 0,
    expired_entries: 0,
    total_hits: 0,
    approximate_size_bytes: 0,
    ...overrides,
  };
}

function makeCodexAccount(
  overrides: Partial<CodexAccountResponse> = {}
): CodexAccountResponse {
  return {
    runtime_status: "ready",
    authenticated: false,
    requires_openai_auth: true,
    account_type: null,
    email: null,
    plan_type: null,
    error_code: null,
    error_message: null,
    ...overrides,
  };
}

function makeSearchCacheEntry(overrides: Partial<SearchCacheEntry> = {}): SearchCacheEntry {
  const now = new Date("2026-04-06T10:00:00.000Z");
  const inTwoHours = new Date(now.getTime() + 2 * 60 * 60 * 1000);

  return {
    cache_key: "cache-key-1",
    provider: "tavily",
    normalized_query: "market structure update",
    created_at: now.toISOString(),
    expires_at: inTwoHours.toISOString(),
    last_accessed_at: now.toISOString(),
    hit_count: 2,
    is_expired: false,
    ...overrides,
  };
}

async function mockSettingsApis(
  page: Page,
  config: ConfigResponse,
  options: {
    searchCacheStats?: SearchCacheStatsResponse;
    searchCacheEntries?: SearchCacheEntry[];
    codexAccount?: CodexAccountResponse;
  } = {}
) {
  let searchCacheEntries = [...(options.searchCacheEntries ?? [])];
  let searchCacheStats = makeSearchCacheStats(options.searchCacheStats ?? {});

  const refreshSearchCacheStats = () => {
    const totalEntries = searchCacheEntries.length;
    const activeEntries = searchCacheEntries.filter((entry) => !entry.is_expired).length;
    const expiredEntries = searchCacheEntries.filter((entry) => entry.is_expired).length;
    const totalHits = searchCacheEntries.reduce((sum, entry) => sum + entry.hit_count, 0);
    const approximateSizeBytes = searchCacheEntries.reduce(
      (sum, entry) => sum + entry.normalized_query.length * 32,
      0
    );

    searchCacheStats = {
      ...searchCacheStats,
      total_entries: totalEntries,
      active_entries: activeEntries,
      expired_entries: expiredEntries,
      total_hits: totalHits,
      approximate_size_bytes: approximateSizeBytes,
      db_exists: searchCacheStats.db_exists || totalEntries > 0,
    };
  };

  refreshSearchCacheStats();

  await page.route("**/api/llm/codex/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/llm/codex/account") && route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(options.codexAccount ?? makeCodexAccount()),
      });
      return;
    }

    if (
      pathname.endsWith("/llm/codex/login/active") &&
      route.request().method() === "GET"
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "null",
      });
      return;
    }

    await route.fallback();
  });

  await page.route("**/api/search-cache**", async (route) => {
    const requestUrl = new URL(route.request().url());
    const pathname = requestUrl.pathname;

    if (pathname.endsWith("/search-cache/stats")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(searchCacheStats),
      });
      return;
    }

    if (pathname.endsWith("/search-cache/purge-expired")) {
      const purged = searchCacheEntries.filter((entry) => entry.is_expired).length;
      searchCacheEntries = searchCacheEntries.filter((entry) => !entry.is_expired);
      refreshSearchCacheStats();

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          purged,
          message: `Purged ${purged} expired entries`,
        }),
      });
      return;
    }

    if (pathname.endsWith("/search-cache") && route.request().method() === "DELETE") {
      const cleared = searchCacheEntries.length;
      searchCacheEntries = [];
      refreshSearchCacheStats();

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          cleared,
          message: `Cleared ${cleared} entries.`,
        }),
      });
      return;
    }

    if (pathname.includes("/search-cache/") && route.request().method() === "DELETE") {
      const cacheKey = pathname.split("/").pop() ?? "";
      const entry = searchCacheEntries.find((item) => item.cache_key === cacheKey);
      searchCacheEntries = searchCacheEntries.filter((item) => item.cache_key !== cacheKey);
      refreshSearchCacheStats();

      await route.fulfill({
        status: entry ? 200 : 404,
        contentType: "application/json",
        body: JSON.stringify(
          entry
            ? { cache_key: cacheKey, deleted: true }
            : { deleted: false, error: `Entry not found: ${cacheKey}` }
        ),
      });
      return;
    }

    if (pathname.endsWith("/search-cache")) {
      const includeExpired = requestUrl.searchParams.get("include_expired") === "true";
      const limit = Number(requestUrl.searchParams.get("limit") ?? "100");
      const offset = Number(requestUrl.searchParams.get("offset") ?? "0");

      const filteredEntries = includeExpired
        ? searchCacheEntries
        : searchCacheEntries.filter((entry) => !entry.is_expired);
      const pagedEntries = filteredEntries.slice(offset, offset + limit);

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          entries: pagedEntries,
          total: pagedEntries.length,
          message: searchCacheStats.enabled ? undefined : "Cache is disabled",
        }),
      });
      return;
    }

    await route.fallback();
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

test("settings page shows persisted vs runtime override state @smoke", async ({ page }) => {
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

test("settings page supports search cache cleanup and entry inspection", async ({ page }) => {
  const recentActiveEntry = makeSearchCacheEntry({
    cache_key: "cache-key-active",
    normalized_query: "ethereum etf flows",
    hit_count: 4,
  });
  const staleEntry = makeSearchCacheEntry({
    cache_key: "cache-key-expired",
    normalized_query: "stale supply chain snapshot",
    created_at: "2026-04-05T06:00:00.000Z",
    last_accessed_at: "2026-04-05T07:00:00.000Z",
    expires_at: "2026-04-05T09:00:00.000Z",
    hit_count: 0,
    is_expired: true,
  });

  await mockSettingsApis(page, makeConfigResponse(), {
    searchCacheStats: makeSearchCacheStats({
      enabled: true,
      db_exists: true,
      ttl_seconds: 7200,
    }),
    searchCacheEntries: [recentActiveEntry, staleEntry],
  });

  await page.goto("/settings");

  await expect(page.getByText("expired entries are taking space that active results could use.")).toBeVisible();
  await expect(page.getByText("Use recent entries to connect stale or repeated research behavior to what is actually stored in the cache.")).toBeVisible();
  await expect(page.getByText("stale supply chain snapshot")).toBeVisible();
  await expect(page.getByText("ethereum etf flows")).toBeVisible();

  await page.getByRole("button", { name: "Delete entry" }).nth(1).click();
  await expect(page.getByText("Delete this cached result?")).toBeVisible();
  await page
    .getByRole("alertdialog", { name: "Delete this cached result?" })
    .getByRole("button", { name: "Delete entry" })
    .click();
  await expect(
    page.locator("article").filter({ hasText: "stale supply chain snapshot" })
  ).toHaveCount(0);

  await page.getByRole("button", { name: "Active only" }).click();
  await expect(page.getByText("ethereum etf flows")).toBeVisible();

  await page.getByRole("button", { name: "Show active + expired" }).click();
  await page.getByRole("button", { name: "Clear all cached results" }).click();
  await expect(page.getByText("including 1 entry that could still satisfy repeat research.")).toBeVisible();
  await page.getByRole("button", { name: "Clear all results" }).click();
  await expect(page.getByText("Cleared 1 entries.")).toBeVisible();
  await expect(page.getByText("No recent cache entries to review.")).toBeVisible();
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

test("settings page configures and authenticates the Codex provider", async ({ page }) => {
  const configPatchBodies: Array<Record<string, unknown>> = [];
  let currentResponse = makeConfigResponse();
  let account = makeCodexAccount();

  await mockSettingsApis(page, currentResponse);

  await page.route("**/api/config", async (route) => {
    if (route.request().method() !== "PATCH") {
      await route.fallback();
      return;
    }

    const body = route.request().postDataJSON() as {
      updates: Record<string, unknown>;
    };
    configPatchBodies.push(body.updates);

    const codex = {
      enabled: body.updates["llm.codex.enabled"] ?? false,
      model: body.updates["llm.codex.model"] ?? null,
      reasoning_effort: body.updates["llm.codex.reasoning_effort"] ?? "medium",
      timeout_seconds: body.updates["llm.codex.timeout_seconds"] ?? 180,
    };
    const persistedLlm = currentResponse.persisted_config.llm as Record<string, unknown>;
    const effectiveLlm = currentResponse.effective_config.llm as Record<string, unknown>;
    currentResponse = {
      ...currentResponse,
      persisted_config: {
        ...currentResponse.persisted_config,
        llm: { ...persistedLlm, codex },
      },
      effective_config: {
        ...currentResponse.effective_config,
        llm: { ...effectiveLlm, codex },
      },
    };

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(currentResponse),
    });
  });

  await page.route("**/api/llm/codex/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const method = route.request().method();

    if (pathname.endsWith("/llm/codex/account") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(account),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/device-code") && method === "POST") {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          login_id: "login-e2e",
          flow: "device_code",
          status: "pending",
          auth_url: null,
          verification_url: "https://chatgpt.com/activate",
          user_code: "ABCD-EFGH",
          error: null,
          created_at: "2026-07-31T12:00:00+00:00",
          completed_at: null,
        }),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/login-e2e") && method === "GET") {
      account = makeCodexAccount({
        authenticated: true,
        account_type: "chatgpt",
        email: "operator@example.com",
        plan_type: "plus",
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          login_id: "login-e2e",
          flow: "device_code",
          status: "succeeded",
          auth_url: null,
          verification_url: null,
          user_code: null,
          error: null,
          created_at: "2026-07-31T12:00:00+00:00",
          completed_at: "2026-07-31T12:00:02+00:00",
        }),
      });
      return;
    }

    await route.fallback();
  });

  await page.goto("/settings");

  await expect(page.locator('option[value="codex"]')).toHaveCount(5);
  await page.getByLabel("Enable the Codex provider").click();
  await page.getByLabel("Codex model").fill("codex-model-test");
  await page.getByLabel("Codex reasoning effort").selectOption("high");
  await page.getByLabel("Codex request timeout in seconds").fill("240");
  await page.getByRole("button", { name: "Save Codex settings" }).click();

  await expect(page.getByText("Saved 4 Codex settings for future runs.")).toBeVisible();
  expect(configPatchBodies[0]).toEqual({
    "llm.codex.enabled": true,
    "llm.codex.model": "codex-model-test",
    "llm.codex.reasoning_effort": "high",
    "llm.codex.timeout_seconds": 240,
  });

  await page.getByRole("button", { name: "Use device code" }).click();
  await expect(page.getByText("ABCD-EFGH")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open verification page" })).toHaveAttribute(
    "href",
    "https://chatgpt.com/activate"
  );
  await expect(page.getByText("ChatGPT account connected")).toBeVisible();
  await expect(page.getByText(/operator@example.com is authenticated/)).toBeVisible();
});

test("settings page resumes an active Codex login after reload", async ({ page }) => {
  let account = makeCodexAccount();
  let allowLoginCompletion = false;
  let loginStatusReads = 0;

  await mockSettingsApis(page, makeConfigResponse());

  await page.route("**/api/llm/codex/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const method = route.request().method();

    if (pathname.endsWith("/llm/codex/account") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(account),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/browser") && method === "POST") {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          login_id: "login-reload",
          flow: "browser",
          status: "pending",
          auth_url: "https://chatgpt.com/auth/private",
          verification_url: null,
          user_code: null,
          error: null,
          created_at: "2026-07-31T12:00:00+00:00",
          completed_at: null,
        }),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/login-reload") && method === "GET") {
      loginStatusReads += 1;
      if (allowLoginCompletion) {
        account = makeCodexAccount({
          authenticated: true,
          account_type: "chatgpt",
          email: "reloaded@example.com",
          plan_type: "plus",
        });
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          login_id: "login-reload",
          flow: "browser",
          status: allowLoginCompletion ? "succeeded" : "pending",
          auth_url: allowLoginCompletion ? null : "https://chatgpt.com/auth/private",
          verification_url: null,
          user_code: null,
          error: null,
          created_at: "2026-07-31T12:00:00+00:00",
          completed_at: allowLoginCompletion
            ? "2026-07-31T12:00:03+00:00"
            : null,
        }),
      });
      return;
    }

    await route.fallback();
  });

  await page.goto("/settings");
  await page.getByRole("button", { name: "Sign in with browser" }).click();

  const storedRecovery = await page.evaluate(() => {
    const serialized = window.sessionStorage.getItem("ccdr.codex-active-login");
    return serialized ? JSON.parse(serialized) : null;
  });
  expect(Object.keys(storedRecovery).sort()).toEqual(["flow", "login_id", "timestamp"]);
  expect(storedRecovery.login_id).toBe("login-reload");
  expect(storedRecovery.flow).toBe("browser");
  expect(typeof storedRecovery.timestamp).toBe("number");
  expect(JSON.stringify(storedRecovery)).not.toContain("auth_url");
  expect(JSON.stringify(storedRecovery)).not.toContain("chatgpt.com");

  await page.reload();
  await expect(page.getByText("Resuming Codex sign-in")).toBeVisible();
  allowLoginCompletion = true;

  await expect(page.getByText("ChatGPT account connected")).toBeVisible();
  await expect(page.getByText(/reloaded@example.com is authenticated/)).toBeVisible();
  expect(loginStatusReads).toBeGreaterThan(0);
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.sessionStorage.getItem("ccdr.codex-active-login")
      )
    )
    .toBeNull();
});

test("settings page recovers an active Codex login after browser storage is lost", async ({
  page,
}) => {
  let account = makeCodexAccount();
  let allowLoginCompletion = false;
  const activeLogin = {
    login_id: "login-recovered",
    flow: "browser",
    status: "pending",
    auth_url: "https://chatgpt.com/auth/recovered",
    verification_url: null,
    user_code: null,
    error: null,
    created_at: "2026-07-31T12:00:00+00:00",
    completed_at: null,
  };

  await mockSettingsApis(page, makeConfigResponse());
  await page.route("**/api/llm/codex/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const method = route.request().method();

    if (pathname.endsWith("/llm/codex/account") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(account),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/active") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(activeLogin),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/login-recovered") && method === "GET") {
      if (allowLoginCompletion) {
        account = makeCodexAccount({
          authenticated: true,
          account_type: "chatgpt",
          email: "recovered@example.com",
          plan_type: "plus",
        });
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...activeLogin,
          status: allowLoginCompletion ? "succeeded" : "pending",
          auth_url: allowLoginCompletion ? null : activeLogin.auth_url,
          completed_at: allowLoginCompletion
            ? "2026-07-31T12:00:03+00:00"
            : null,
        }),
      });
      return;
    }

    await route.fallback();
  });

  await page.goto("/settings");

  await expect(page.getByText("Resuming Codex sign-in")).toBeVisible();
  const recoveredStorage = await page.evaluate(() => {
    const serialized = window.sessionStorage.getItem("ccdr.codex-active-login");
    return serialized ? JSON.parse(serialized) : null;
  });
  expect(Object.keys(recoveredStorage).sort()).toEqual(["flow", "login_id", "timestamp"]);
  expect(recoveredStorage.login_id).toBe("login-recovered");
  expect(JSON.stringify(recoveredStorage)).not.toContain("auth_url");

  allowLoginCompletion = true;
  await expect(page.getByText("ChatGPT account connected")).toBeVisible();
  await expect(page.getByText(/recovered@example.com is authenticated/)).toBeVisible();
});

test("settings page reports a login that wins a cancellation race", async ({ page }) => {
  let account = makeCodexAccount();

  await mockSettingsApis(page, makeConfigResponse());

  await page.route("**/api/llm/codex/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const method = route.request().method();

    if (pathname.endsWith("/llm/codex/account") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(account),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/browser") && method === "POST") {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          login_id: "login-race",
          flow: "browser",
          status: "pending",
          auth_url: "https://chatgpt.com/auth",
          verification_url: null,
          user_code: null,
          error: null,
          created_at: "2026-07-31T12:00:00+00:00",
          completed_at: null,
        }),
      });
      return;
    }

    if (pathname.endsWith("/llm/codex/login/login-race") && method === "DELETE") {
      account = makeCodexAccount({
        authenticated: true,
        account_type: "chatgpt",
        email: "race-winner@example.com",
        plan_type: "pro",
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          login_id: "login-race",
          flow: "browser",
          status: "succeeded",
          auth_url: null,
          verification_url: null,
          user_code: null,
          error: null,
          created_at: "2026-07-31T12:00:00+00:00",
          completed_at: "2026-07-31T12:00:01+00:00",
        }),
      });
      return;
    }

    await route.fallback();
  });

  await page.goto("/settings");
  await page.getByRole("button", { name: "Sign in with browser" }).click();
  await page.getByRole("button", { name: "Cancel sign-in" }).click();

  await expect(
    page.getByText("Codex sign-in completed before cancellation")
  ).toBeVisible();
  await expect(page.getByText(/race-winner@example.com is authenticated/)).toBeVisible();
  await expect(page.getByText("Codex sign-in canceled")).toHaveCount(0);
  expect(
    await page.evaluate(() =>
      window.sessionStorage.getItem("ccdr.codex-active-login")
    )
  ).toBeNull();
});

test("settings page preserves dirty Codex fields across parent config refreshes", async ({
  page,
}) => {
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
    expect(body.updates["llm.openrouter.api_key"]).toEqual({
      action: "replace",
      value: "sk-refresh",
    });

    const persistedLlm = currentResponse.persisted_config.llm as Record<string, unknown>;
    const effectiveLlm = currentResponse.effective_config.llm as Record<string, unknown>;
    const codex = {
      enabled: true,
      model: "server-model",
      reasoning_effort: "high",
      timeout_seconds: 240,
    };
    currentResponse = {
      ...currentResponse,
      persisted_config: {
        ...currentResponse.persisted_config,
        llm: { ...persistedLlm, codex },
      },
      effective_config: {
        ...currentResponse.effective_config,
        llm: { ...effectiveLlm, codex },
      },
      secret_fields: currentResponse.secret_fields.map((field) =>
        field.field === "llm.openrouter.api_key"
          ? {
              ...field,
              persisted_present: true,
              effective_present: true,
              persisted_count: 1,
              effective_count: 1,
            }
          : field
      ),
    };

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(currentResponse),
    });
  });

  await page.goto("/settings");
  await page.getByLabel("Codex model").fill("unsaved-draft-model");

  const secretRow = page.locator("div").filter({ hasText: "llm.openrouter.api_key" }).first();
  await secretRow.getByRole("button", { name: "Replace", exact: true }).click();
  await page.getByPlaceholder("Enter a replacement value").fill("sk-refresh");
  await page.getByRole("button", { name: "Save secret" }).click();

  await expect(page.getByLabel("Codex model")).toHaveValue("unsaved-draft-model");
  await expect(page.getByLabel("Enable the Codex provider")).toBeChecked();
  await expect(page.getByLabel("Codex reasoning effort")).toHaveValue("high");
  await expect(page.getByLabel("Codex request timeout in seconds")).toHaveValue("240");
  await expect(page.getByText("1 unsaved")).toBeVisible();
});
