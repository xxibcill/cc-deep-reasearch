import { expect, test, type Page } from "@playwright/test";
import type { PipelineContext, PipelineRunSummary } from "@/types/content-gen";

const pipelineId = "cgp-observe01";

interface PipelineDetailResponse extends PipelineRunSummary {
  context: PipelineContext;
}

function makePipelineDetailResponse(): PipelineDetailResponse {
  const context: PipelineContext = {
    pipeline_id: pipelineId,
    theme: "AI agent onboarding hooks",
    created_at: "2026-04-03T09:00:00Z",
    current_stage: 12,
    strategy: {
      niche: "AI operator education",
      content_pillars: ["operator workflows", "AI systems", "launch analysis"],
      audience_segments: [],
      tone_rules: ["Be concrete", "Avoid empty hype"],
      offer_cta_rules: [],
      platforms: ["YouTube Shorts", "TikTok"],
      forbidden_claims: [],
      proof_standards: [],
      past_winners: [],
      past_losers: [],
    },
    opportunity_brief: {
      theme: "AI agent onboarding hooks",
      goal: "Turn product launch chaos into a concrete operator lesson.",
      primary_audience_segment: "Technical founders shipping AI tools",
      secondary_audience_segments: ["AI PMs", "developer advocates"],
      problem_statements: [
        "Launch videos explain features but miss the setup friction.",
        "Operators need a fast path to the first successful workflow.",
      ],
      content_objective: "Show the one onboarding moment that earns trust.",
      proof_requirements: ["Reference a real onboarding failure", "Show a corrected flow"],
      platform_constraints: ["Under 60 seconds"],
      risk_constraints: ["Avoid hype claims"],
      freshness_rationale: "A cluster of April 2026 agent launches all repeated the same setup mistake.",
      sub_angles: [
        "The false-success moment in agent onboarding",
        "Why setup friction kills the first retained user",
      ],
      research_hypotheses: ["Operators trust workflow demos over feature lists"],
      success_criteria: ["A clear operator takeaway", "At least one reusable launch lesson"],
    },
    backlog: {
      items: [
        {
          idea_id: "idea-selected",
          category: "authority-building",
          idea: "The first 90 seconds of your AI agent onboarding decide whether operators trust it.",
          audience: "Technical founders",
          problem: "Users think they succeeded before the workflow is actually usable.",
          source: "launch review",
          why_now: "Several April launches repeated the same flaw.",
          potential_hook: "Your onboarding celebrates the wrong moment.",
          content_type: "short video",
          evidence: "Launch teardown notes",
          risk_level: "low",
          priority_score: 4.8,
          status: "selected",
        },
        {
          idea_id: "idea-alt",
          category: "trend-responsive",
          idea: "Agent launch videos keep skipping the handoff from demo to real workflow.",
          audience: "AI PMs",
          problem: "Viewers see the result, not the operator setup path.",
          source: "launch review",
          why_now: "The same pattern showed up across multiple launches.",
          potential_hook: "The demo ends before the actual work begins.",
          content_type: "short video",
          evidence: "Launch teardown notes",
          risk_level: "medium",
          priority_score: 4.2,
          status: "backlog",
        },
        {
          idea_id: "idea-hold",
          category: "evergreen",
          idea: "Build an onboarding checklist for your next AI workflow release.",
          audience: "Developer advocates",
          problem: "Teams ship without a repeatable operator checklist.",
          source: "editorial planning",
          why_now: "Useful, but not the freshest angle this week.",
          potential_hook: "The release checklist your agent team forgot.",
          content_type: "short video",
          evidence: "Internal notes",
          risk_level: "low",
          priority_score: 3.4,
          status: "backlog",
        },
      ],
      rejected_count: 1,
      rejection_reasons: ["One concept repeated an older teardown too closely."],
      is_degraded: false,
      degradation_reason: "",
    },
    scoring: {
      scores: [
        {
          idea_id: "idea-selected",
          relevance: 5,
          novelty: 4,
          authority_fit: 5,
          production_ease: 4,
          evidence_strength: 4,
          hook_strength: 5,
          repurposing: 4,
          total_score: 31,
          recommendation: "produce_now",
          reason: "Strongest authority fit because it ties a visible launch mistake to an actionable operator fix.",
        },
        {
          idea_id: "idea-alt",
          relevance: 4,
          novelty: 4,
          authority_fit: 4,
          production_ease: 4,
          evidence_strength: 4,
          hook_strength: 4,
          repurposing: 4,
          total_score: 28,
          recommendation: "produce_now",
          reason: "Strong alternate, but the story stays broader and less specific than the selected hook.",
        },
        {
          idea_id: "idea-hold",
          relevance: 3,
          novelty: 3,
          authority_fit: 4,
          production_ease: 5,
          evidence_strength: 3,
          hook_strength: 3,
          repurposing: 4,
          total_score: 25,
          recommendation: "hold",
          reason: "Useful support content, but it lacks the urgency of the launch-analysis angle.",
        },
      ],
      produce_now: ["idea-selected", "idea-alt"],
      shortlist: ["idea-selected", "idea-alt"],
      selected_idea_id: "idea-selected",
      selection_reasoning:
        "Fallback scoring rationale should stay behind the pipeline-level rationale when both are present.",
      runner_up_idea_ids: ["idea-alt"],
      hold: ["idea-hold"],
      killed: [],
      is_degraded: false,
      degradation_reason: "",
    },
    shortlist: ["idea-selected", "idea-alt"],
    selected_idea_id: "idea-selected",
    selection_reasoning:
      "Selected idea-selected for the clearest authority-to-action path after comparing launch specificity across the shortlist.",
    runner_up_idea_ids: ["idea-alt"],
    angles: {
      idea_id: "idea-selected",
      angle_options: [
        {
          angle_id: "angle-selected",
          target_audience: "Technical founders",
          viewer_problem: "The launch video sells success before the workflow is actually usable.",
          core_promise: "Show the onboarding moment that proves your agent works in the real world.",
          primary_takeaway: "Celebrate workflow completion, not setup completion.",
          lens: "observability teardown",
          format: "short video",
          tone: "direct",
          cta: "Audit your first operator workflow",
          why_this_version_should_exist: "It turns a product critique into an operator lesson with a clear fix.",
        },
        {
          angle_id: "angle-alt",
          target_audience: "AI PMs",
          viewer_problem: "Launch demos end before the operator handoff is visible.",
          core_promise: "Map the invisible handoff that makes or breaks onboarding.",
          primary_takeaway: "The handoff matters more than the feature reveal.",
          lens: "launch review",
          format: "short video",
          tone: "analytical",
          cta: "Rebuild your onboarding handoff",
          why_this_version_should_exist: "It broadens the lesson, but loses some urgency.",
        },
      ],
      selected_angle_id: "angle-selected",
      selection_reasoning: "Best connects launch friction to a concrete operator payoff without diluting the hook.",
    },
    research_pack: {
      idea_id: "idea-selected",
      angle_id: "angle-selected",
      audience_insights: [],
      competitor_observations: [],
      key_facts: ["Operators drop when the workflow completion state is ambiguous."],
      proof_points: ["Multiple launches showed setup success before task success."],
      examples: [],
      case_studies: [],
      gaps_to_exploit: [],
      assets_needed: [],
      claims_requiring_verification: ["Launch retention deltas need source confirmation."],
      unsafe_or_uncertain_claims: [],
      research_stop_reason: "Cached research pack was sufficient for this run.",
    },
    scripting: {
      raw_idea: "AI onboarding hook",
      research_context: "",
      tone: "direct",
      cta: "Audit your first operator workflow",
      core_inputs: {
        topic: "AI onboarding",
        outcome: "Show the trust-breaking moment",
        audience: "Technical founders",
      },
      angle: {
        angle: "Celebrate the real workflow success moment",
        content_type: "short video",
        core_tension: "Launch polish vs. operator trust",
        why_it_works: "It reframes launch quality through operator outcomes.",
      },
      structure: {
        chosen_structure: "teardown",
        why_it_fits: "The format supports before-and-after analysis.",
        beat_list: ["Hook", "Mistake", "Fix", "CTA"],
      },
      beat_intents: { beats: [] },
      hooks: {
        hooks: ["Your onboarding celebrates the wrong moment."],
        best_hook: "Your onboarding celebrates the wrong moment.",
        best_hook_reason: "Short, direct, and tied to the operator problem.",
      },
      draft: {
        content: "Your onboarding celebrates the wrong moment.\nShow the actual workflow success instead.",
        word_count: 14,
      },
      retention_revised: null,
      tightened: null,
      annotated_script: null,
      visual_notes: [],
      qc: {
        checks: [],
        weakest_parts: [],
        final_script: "Your onboarding celebrates the wrong moment.\nShow the actual workflow success instead.",
      },
      step_traces: [],
    },
    visual_plan: null,
    production_brief: null,
    packaging: {
      idea_id: "idea-selected",
      platform_packages: [
        {
          platform: "TikTok",
          primary_hook: "Your onboarding celebrates the wrong moment.",
          alternate_hooks: ["Stop praising setup. Praise the first real workflow."],
          cover_text: "Fix the false-success moment",
          caption: "A teardown of the onboarding step that breaks operator trust.",
          keywords: ["AI onboarding", "operator trust"],
          hashtags: ["#ai", "#product"],
          pinned_comment: "Audit the first completed workflow, not the setup screen.",
          cta: "Review your onboarding handoff",
          version_notes: "Lead with the trust problem.",
        },
      ],
    },
    qc_gate: null,
    publish_item: null,
    performance: null,
    iteration_state: null,
    stage_traces: [
      {
        stage_index: 0,
        stage_name: "load_strategy",
        stage_label: "Loading strategy memory",
        status: "completed",
        started_at: "2026-04-03T09:00:03Z",
        completed_at: "2026-04-03T09:00:04Z",
        duration_ms: 820,
        input_summary: "theme=AI agent onboarding hooks",
        output_summary: "strategy loaded",
        warnings: [],
        decision_summary: "",
        metadata: {},
      },
      {
        stage_index: 1,
        stage_name: "plan_opportunity",
        stage_label: "Planning opportunity brief",
        status: "completed",
        started_at: "2026-04-03T09:00:04Z",
        completed_at: "2026-04-03T09:00:11Z",
        duration_ms: 6400,
        input_summary: "theme=AI agent onboarding hooks niche=AI operator education",
        output_summary: "goal, audience, proof requirements captured",
        warnings: [],
        decision_summary: "Narrowed the brief around operator trust instead of generic launch advice.",
        metadata: {},
      },
      {
        stage_index: 2,
        stage_name: "build_backlog",
        stage_label: "Building backlog",
        status: "completed",
        started_at: "2026-04-03T09:00:11Z",
        completed_at: "2026-04-03T09:00:20Z",
        duration_ms: 9000,
        input_summary: "goal=Turn product launch chaos into a concrete operator lesson.",
        output_summary: "items=3 rejected=1",
        warnings: ["1 low-confidence source left in backlog for manual verification."],
        decision_summary: "",
        metadata: {},
      },
      {
        stage_index: 3,
        stage_name: "score_ideas",
        stage_label: "Scoring ideas",
        status: "completed",
        started_at: "2026-04-03T09:00:20Z",
        completed_at: "2026-04-03T09:00:28Z",
        duration_ms: 7700,
        input_summary: "items=3",
        output_summary: "produce=2 hold=1 kill=0",
        warnings: [],
        decision_summary: "Selected idea-selected for the clearest authority-to-action path.",
        metadata: {},
      },
      {
        stage_index: 4,
        stage_name: "generate_angles",
        stage_label: "Generating angles",
        status: "completed",
        started_at: "2026-04-03T09:00:28Z",
        completed_at: "2026-04-03T09:00:36Z",
        duration_ms: 7600,
        input_summary: "idea_id=idea-selected",
        output_summary: "angles=2 selected=angle-selected",
        warnings: [],
        decision_summary: "Selected the operator-trust framing for stronger specificity.",
        metadata: {},
      },
      {
        stage_index: 5,
        stage_name: "build_research_pack",
        stage_label: "Building research pack",
        status: "skipped",
        started_at: "2026-04-03T09:00:36Z",
        completed_at: "2026-04-03T09:00:36Z",
        duration_ms: 0,
        input_summary: "idea_id=idea-selected angle_id=angle-selected",
        output_summary: "research pack reused from cache",
        warnings: [],
        decision_summary: "Skipped: research pack reused from cached brief",
        metadata: {},
      },
      {
        stage_index: 6,
        stage_name: "run_scripting",
        stage_label: "Running scripting pipeline",
        status: "completed",
        started_at: "2026-04-03T09:00:36Z",
        completed_at: "2026-04-03T09:02:05Z",
        duration_ms: 89000,
        input_summary: "research ready",
        output_summary: "script drafted and QC'd",
        warnings: [],
        decision_summary: "",
        metadata: {},
      },
    ],
  };

  return {
    pipeline_id: pipelineId,
    theme: "AI agent onboarding hooks",
    from_stage: 0,
    to_stage: 12,
    status: "completed",
    current_stage: 12,
    error: null,
    created_at: "2026-04-03T09:00:00Z",
    started_at: "2026-04-03T09:00:03Z",
    completed_at: "2026-04-03T09:05:00Z",
    context,
  };
}

async function mockPipelineApis(page: Page, response: PipelineDetailResponse = makePipelineDetailResponse()) {
  await page.route("**/api/content-gen/pipelines", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            pipeline_id: response.pipeline_id,
            theme: response.theme,
            from_stage: response.from_stage,
            to_stage: response.to_stage,
            status: response.status,
            current_stage: response.current_stage,
            error: response.error,
            created_at: response.created_at,
            started_at: response.started_at,
            completed_at: response.completed_at,
          },
        ],
      }),
    });
  });

  await page.route(`**/api/content-gen/pipelines/${pipelineId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response),
    });
  });

  await page.route("**/api/content-gen/scripts", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });

  await page.route("**/api/content-gen/publish", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    });
  });

  await page.route("**/api/content-gen/strategy", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response.context.strategy),
    });
  });
}

test("pipeline detail surfaces traces, skips, and shortlist rationale from backend context", async ({
  page,
}) => {
  await mockPipelineApis(page);

  await page.goto(`/content-gen/pipeline/${pipelineId}`);

  await expect(page.getByRole("heading", { name: "Pipeline", exact: true })).toBeVisible();
  await expect(page.locator("main").getByText("AI agent onboarding hooks", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Plan Opportunity completed/ })).toBeVisible();
  await expect(
    page.getByText("Turn product launch chaos into a concrete operator lesson.", { exact: true }),
  ).toBeVisible();

  await expect(page.getByText("1 low-confidence source left in backlog for manual verification.")).toBeVisible();
  await expect(page.getByText("Skipped: research pack reused from cached brief")).toBeVisible();

  await expect(page.getByText("Scored ideas")).toBeVisible();
  await expect(page.getByText("idea-selected", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "Selected idea-selected for the clearest authority-to-action path after comparing launch specificity across the shortlist.",
    ),
  ).toBeVisible();
  await expect(page.getByText("idea-alt", { exact: true })).toBeVisible();
});

test("pipeline detail shows degraded reasons when backlog or scoring complete in degraded mode", async ({
  page,
}) => {
  const response = makePipelineDetailResponse();
  response.context.backlog = {
    ...response.context.backlog!,
    is_degraded: true,
    degradation_reason: "Only one viable idea survived duplicate filtering and evidence review.",
  };
  response.context.scoring = {
    ...response.context.scoring!,
    is_degraded: true,
    degradation_reason: "Scoring continued with a narrowed shortlist after backlog degradation.",
  };

  await mockPipelineApis(page, response);

  await page.goto(`/content-gen/pipeline/${pipelineId}`);

  await expect(page.getByText("Backlog degraded")).toBeVisible();
  await expect(
    page.getByText("Only one viable idea survived duplicate filtering and evidence review."),
  ).toBeVisible();
  await expect(page.getByText("Scoring degraded")).toBeVisible();
  await expect(
    page.getByText("Scoring continued with a narrowed shortlist after backlog degradation."),
  ).toBeVisible();
});
