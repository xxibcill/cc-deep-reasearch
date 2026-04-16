"""CLI commands for the content generation workflow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import click

from cc_deep_research.config import load_config
from cc_deep_research.content_gen.storage import AuditStore, ScriptingStore

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import (
        AngleOption,
        PipelineContext,
        ScriptingContext,
        ScriptVersion,
    )

KNOWN_MODULES = frozenset(
    {
        "scripting",
        "backlog",
        "angle",
        "research",
        "visual",
        "production",
        "packaging",
        "qc",
        "publish",
        "performance",
    }
)


def register_content_gen_commands(cli: click.Group) -> None:
    """Register content-gen commands with the main CLI group."""

    @cli.group()
    def content_gen() -> None:
        """Content generation workflow for short-form video."""

    # ------------------------------------------------------------------
    # Strategy commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def strategy() -> None:
        """Manage persistent strategy memory."""

    @strategy.command()
    def strategy_show() -> None:
        """Display current strategy memory."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        mem = store.load()
        if not mem.niche and not mem.content_pillars:
            click.echo("Strategy memory is empty. Run 'content-gen strategy init' to create one.")
            return
        click.echo(f"Niche: {mem.niche}")
        click.echo(f"Content pillars: {', '.join(mem.content_pillars)}")
        click.echo(f"Platforms: {', '.join(mem.platforms)}")
        click.echo(f"Tone rules: {', '.join(mem.tone_rules)}")
        click.echo(f"Forbidden claims: {', '.join(mem.forbidden_claims)}")
        click.echo(f"Proof standards: {', '.join(mem.proof_standards)}")
        for seg in mem.audience_segments:
            click.echo(f"\n  Audience: {seg.name} — {seg.description}")
            click.echo(f"  Pain points: {', '.join(seg.pain_points)}")
        if mem.past_winners:
            click.echo(f"\nPast winners: {', '.join(w.title for w in mem.past_winners)}")
        if mem.past_losers:
            click.echo(f"Past losers: {', '.join(w.title for w in mem.past_losers)}")

    @strategy.command()
    def strategy_init() -> None:
        """Create a blank strategy file."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        if store.path.exists():
            click.echo(f"Strategy file already exists at {store.path}")
            return
        store.save(store.load())
        click.echo(f"Created strategy file at {store.path}")

    @strategy.command()
    @click.argument("key")
    @click.argument("value")
    def strategy_set(key: str, value: str) -> None:
        """Update a strategy field. For lists, use comma-separated values."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        list_fields = {
            "content_pillars",
            "tone_rules",
            "offer_cta_rules",
            "platforms",
            "forbidden_claims",
            "proof_standards",
        }
        patch = {key: [v.strip() for v in value.split(",")]} if key in list_fields else {key: value}
        store.update(patch)
        click.echo(f"Updated {key} in {store.path}")

    # ------------------------------------------------------------------
    # Backlog commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def backlog() -> None:
        """Manage the content idea backlog."""

    @backlog.command()
    @click.option("--theme", required=True, help="Theme or content pillar")
    @click.option("--count", default=20, help="Number of ideas to generate")
    @click.option("-o", "--output", type=click.Path(), default=None, help="Save to file")
    def backlog_build(theme: str, count: int, output: str | None) -> None:
        """Generate backlog ideas for a theme."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.backlog_service import BacklogService
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            service = BacklogService(config)
            click.echo(f'Building backlog for: "{theme}" ({count} ideas)...')
            result = await orch.run_backlog(theme, count=count)
            result = service.persist_generated(result, theme=theme)

            click.echo(f"\nGenerated {len(result.items)} ideas, rejected {result.rejected_count}")
            for item in result.items:
                click.echo(f"  [{item.category}] {item.idea}")
            click.echo(f"\nBacklog store: {service.path}")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    @backlog.command()
    @click.option("--from-file", type=click.Path(exists=True), help="Backlog JSON file")
    @click.option("--select-top", default=5, help="Number of top ideas to select")
    @click.option("-o", "--output", type=click.Path(), default=None, help="Save to file")
    def backlog_score(from_file: str | None, select_top: int, output: str | None) -> None:
        """Score backlog ideas and pick the best ones."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.backlog_service import BacklogService
            from cc_deep_research.content_gen.models import BacklogOutput
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            service = BacklogService(config)
            items = []
            if from_file:
                data = BacklogOutput.model_validate_json(Path(from_file).read_text())
                items = data.items

            if not items:
                click.echo("No items to score. Use --from-file or build a backlog first.")
                return

            click.echo(f"Scoring {len(items)} ideas...")
            service.upsert_items(items)
            result = await orch.run_scoring(items)
            service.apply_scoring(result)

            click.echo(f"\nProduce now ({len(result.produce_now)}):")
            for sid in result.produce_now[:select_top]:
                score = next((s for s in result.scores if s.idea_id == sid), None)
                if score:
                    click.echo(f"  {sid}: {score.total_score}/35 — {score.reason}")

            if result.shortlist:
                click.echo(f"\nShortlist ({len(result.shortlist)}):")
                for sid in result.shortlist[:select_top]:
                    score = next((s for s in result.scores if s.idea_id == sid), None)
                    if score:
                        click.echo(f"  {sid}: {score.total_score}/35")
                    else:
                        click.echo(f"  {sid}")
            if result.selected_idea_id:
                click.echo(f"\nSelected: {result.selected_idea_id}")
                if result.selection_reasoning:
                    click.echo(f"Reason: {result.selection_reasoning}")

            click.echo(f"\nHold ({len(result.hold)}):")
            for sid in result.hold[:5]:
                click.echo(f"  {sid}")

            click.echo(f"\nKilled ({len(result.killed)}):")
            for sid in result.killed[:5]:
                score = next((s for s in result.scores if s.idea_id == sid), None)
                if score:
                    click.echo(f"  {sid}: {score.reason}")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Angle commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def angle() -> None:
        """Generate editorial angles."""

    @angle.command()
    @click.option("--idea", required=True, help="The content idea")
    @click.option("--audience", default="", help="Target audience")
    @click.option("--problem", default="", help="Viewer problem")
    @click.option("-o", "--output", type=click.Path(), default=None)
    def angle_generate(idea: str, audience: str, problem: str, output: str | None) -> None:
        """Generate 3-5 editorial angles for an idea."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.models import BacklogItem
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            item = BacklogItem(idea=idea, audience=audience, problem=problem)

            click.echo(f'Generating angles for: "{idea}"...')
            result = await orch.run_angle(item)

            click.echo(f"\nGenerated {len(result.angle_options)} angles:")
            for opt in result.angle_options:
                click.echo(f"\n  [{opt.angle_id}] Audience: {opt.target_audience}")
                click.echo(f"  Promise: {opt.core_promise}")
                click.echo(f"  Lens: {opt.lens} | Tone: {opt.tone}")

            if result.selected_angle_id:
                click.echo(f"\nRecommended: {result.selected_angle_id}")
                click.echo(f"Reason: {result.selection_reasoning}")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Research commands
    # ------------------------------------------------------------------

    @content_gen.command()
    @click.option("--idea", required=True, help="Content idea")
    @click.option("--angle", default="", help="Core promise or angle")
    @click.option("-o", "--output", type=click.Path(), default=None)
    def research(idea: str, angle: str, output: str | None) -> None:
        """Build a research pack for an idea and angle."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.models import AngleOption, BacklogItem
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            item = BacklogItem(idea=idea)
            ang = AngleOption(core_promise=angle) if angle else AngleOption()

            click.echo(f'Building research pack for: "{idea}"...')
            result = await orch.run_research(item, ang)

            click.echo(f"\nProof points ({len(result.proof_points)}):")
            for p in result.proof_points[:5]:
                click.echo(f"  - {p}")
            click.echo(f"\nGaps to exploit ({len(result.gaps_to_exploit)}):")
            for g in result.gaps_to_exploit:
                click.echo(f"  - {g}")
            click.echo(f"\nStop reason: {result.research_stop_reason}")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Visual commands
    # ------------------------------------------------------------------

    @content_gen.command()
    @click.option("--from-file", type=click.Path(exists=True), help="Scripting context JSON")
    @click.option("-o", "--output", type=click.Path(), default=None)
    def visual(from_file: str, output: str | None) -> None:
        """Translate a script into a visual plan."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.models import ScriptingContext
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            ctx = ScriptingContext.model_validate_json(Path(from_file).read_text())

            click.echo("Translating script to visual plan...")
            result = await orch.run_visual(ctx)

            click.echo(f"\nVisual plan ({len(result.visual_plan)} beats):")
            for bv in result.visual_plan:
                click.echo(f"  {bv.beat}: {bv.visual} [{bv.shot_type}]")
            click.echo(f"\nRefresh check: {result.visual_refresh_check}")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Production commands
    # ------------------------------------------------------------------

    @content_gen.command("production")
    @click.option("--from-file", type=click.Path(exists=True), help="Visual plan JSON")
    @click.option("-o", "--output", type=click.Path(), default=None)
    def production_brief(from_file: str, output: str | None) -> None:
        """Generate a production brief from a visual plan."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.models import VisualPlanOutput
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            plan = VisualPlanOutput.model_validate_json(Path(from_file).read_text())

            click.echo("Building production brief...")
            result = await orch.run_production(plan)

            click.echo(f"\nLocation: {result.location}")
            click.echo(f"Setup: {result.setup}")
            click.echo(f"Props: {', '.join(result.props)}")
            click.echo(f"Assets: {', '.join(result.assets_to_prepare)}")
            click.echo(f"Backup: {result.backup_plan}")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Packaging commands
    # ------------------------------------------------------------------

    @content_gen.command()
    @click.option("--from-file", type=click.Path(exists=True), help="Scripting context JSON")
    @click.option(
        "--platforms", default=None, help="Comma-separated platforms (default: tiktok,reels,shorts)"
    )
    @click.option("-o", "--output", type=click.Path(), default=None)
    def package(from_file: str, platforms: str | None, output: str | None) -> None:
        """Generate platform packaging variants."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            platforms_list = [p.strip() for p in platforms.split(",")] if platforms else None

            text = Path(from_file).read_text()
            script, angle = _load_packaging_inputs(text)

            click.echo("Generating packaging...")
            result = await orch.run_packaging(script, angle, platforms=platforms_list)

            for pkg in result.platform_packages:
                click.echo(f"\n--- {pkg.platform} ---")
                click.echo(f"Hook: {pkg.primary_hook}")
                click.echo(f"Alt hooks: {', '.join(pkg.alternate_hooks[:3])}")
                click.echo(f"Caption: {pkg.caption[:100]}...")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # QC commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def qc() -> None:
        """Quality control review and approval."""

    @qc.command()
    @click.option("--from-file", type=click.Path(exists=True), help="Pipeline context JSON")
    def qc_review(from_file: str) -> None:
        """Run AI-assisted QC review on a pipeline output."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.models import PipelineContext
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            ctx = PipelineContext.model_validate_json(Path(from_file).read_text())

            script = ""
            if ctx.scripting:
                script = ctx.scripting.qc.final_script if ctx.scripting.qc else ""
                if not script and ctx.scripting.tightened:
                    script = ctx.scripting.tightened.content

            visual_summary = ""
            if ctx.visual_plan:
                visual_summary = "; ".join(
                    f"{bv.beat}: {bv.visual}" for bv in ctx.visual_plan.visual_plan[:5]
                )

            packaging_summary = ""
            if ctx.packaging:
                packaging_summary = "; ".join(
                    f"{p.platform}: {p.primary_hook}" for p in ctx.packaging.platform_packages
                )

            click.echo("Running QC review...")
            result = await orch.run_qc(
                script=script, visual_summary=visual_summary, packaging_summary=packaging_summary
            )

            click.echo(f"\nHook strength: {result.hook_strength}")
            click.echo(f"Release state: {result.release_state.value}")
            click.echo(f"Clarity issues: {len(result.clarity_issues)}")
            click.echo(f"Factual issues: {len(result.factual_issues)}")
            click.echo(f"Must fix: {len(result.must_fix_items)}")
            for item in result.must_fix_items:
                click.echo(f"  - {item}")

        asyncio.run(_run())

    @qc.command()
    @click.option("--idea-id", required=True, help="Idea ID to approve")
    @click.option(
        "--from-file",
        type=click.Path(exists=True),
        required=True,
        help="Pipeline context JSON to update",
    )
    @click.option(
        "--release-state",
        type=click.Choice(["approved", "approved-with-known-risks"]),
        default="approved",
        help="Release state: approved (clean) or approved-with-known-risks (operator override)",
    )
    @click.option(
        "--override-reason",
        default="",
        help="Required reason when approving with known risks (identifies what risks are accepted)",
    )
    @click.option(
        "--actor",
        default="operator",
        help="Operator identifier for audit trail",
    )
    def qc_approve(
        idea_id: str,
        from_file: str,
        release_state: str,
        override_reason: str,
        actor: str,
    ) -> None:
        """Manually approve a video for publish with explicit release state.

        P6-T2: Release state replaces the boolean approved_for_publish.
        --release-state=approved: Full approval with no known issues.
        --release-state=approved-with-known-risks: Operator accepts documented risks (requires --override-reason).

        Examples:
            cc-deep-research content-gen qc approve --idea-id idea123 --from-file ctx.json
            cc-deep-research content-gen qc approve --idea-id idea123 --from-file ctx.json \\
                --release-state approved-with-known-risks --override-reason "hook is adequate, not strong"
        """
        from datetime import UTC, datetime

        from cc_deep_research.content_gen.models import PipelineContext, ReleaseState

        path = Path(from_file)
        ctx = PipelineContext.model_validate_json(path.read_text())

        if ctx.qc_gate is None:
            click.echo("No QC gate found in context. Run 'qc review' first.")
            return

        # Set release state
        if release_state == "approved":
            ctx.qc_gate.release_state = ReleaseState.APPROVED
            ctx.qc_gate.approved_for_publish = True
            ctx.qc_gate.override_actor = ""
            ctx.qc_gate.override_reason = ""
            ctx.qc_gate.override_timestamp = ""
        else:
            # approved-with-known-risks: operator override
            if not override_reason:
                click.echo(
                    "--override-reason is required when --release-state approved-with-known-risks. "
                    "Document the accepted risks."
                )
                return
            ctx.qc_gate.release_state = ReleaseState.APPROVED_WITH_KNOWN_RISKS
            ctx.qc_gate.approved_for_publish = True  # Override allows publish
            ctx.qc_gate.override_actor = actor
            ctx.qc_gate.override_reason = override_reason
            ctx.qc_gate.override_timestamp = datetime.now(tz=UTC).isoformat()

        path.write_text(ctx.model_dump_json(indent=2))

        state_label = ctx.qc_gate.release_state.value
        click.echo(f"Approved idea {idea_id} for publish. Release state: {state_label}")
        if ctx.qc_gate.override_reason:
            click.echo(f"Override reason: {ctx.qc_gate.override_reason}")

        # P6-T3: Log operator override to audit trail when releasing with known risks
        if ctx.qc_gate.release_state.value == "approved_with_known_risks":
            try:
                from cc_deep_research.content_gen.brief_service import BriefService
                from cc_deep_research.content_gen.storage import AuditStore
                audit = AuditStore()
                audit.log_operator_override(
                    idea_id=idea_id,
                    original_state="blocked",
                    override_reason=ctx.qc_gate.override_reason,
                    actor_label=actor,
                    actor="operator",
                    brief_id=ctx.brief_reference.brief_id if ctx.brief_reference else "",
                )
                if ctx.brief_reference:
                    BriefService().record_override(
                        ctx.brief_reference.brief_id,
                        actor_label=actor,
                        reason=ctx.qc_gate.override_reason,
                        pipeline_id=ctx.pipeline_id,
                    )
            except Exception:
                pass  # Audit store is best-effort

    # ------------------------------------------------------------------
    # Publish commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def publish() -> None:
        """Manage the publish queue."""

    @publish.command()
    @click.option("--from-file", type=click.Path(exists=True), help="Packaging output JSON")
    @click.option("--idea-id", default="", help="Idea ID")
    @click.option("-o", "--output", type=click.Path(), default=None)
    def publish_schedule(from_file: str | None, idea_id: str, output: str | None) -> None:  # noqa: ARG001
        """Create publish queue entries."""
        config = load_config()

        async def _run() -> None:
            from cc_deep_research.content_gen.models import PackagingOutput
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator
            from cc_deep_research.content_gen.storage import PublishQueueStore

            orch = ContentGenOrchestrator(config)

            packaging = None
            if from_file:
                packaging = PackagingOutput.model_validate_json(Path(from_file).read_text())

            if packaging is None:
                click.echo("No packaging data. Use --from-file.")
                return

            click.echo("Creating publish queue entries...")
            items = await orch.run_publish(packaging, idea_id=idea_id)

            store = PublishQueueStore()
            for item in items:
                store.add(item)

            click.echo(f"Scheduled {len(items)} items:")
            for item in items:
                click.echo(f"  {item.platform}: {item.publish_datetime} ({item.status})")

        asyncio.run(_run())

    @publish.command()
    def publish_list() -> None:
        """Show the current publish queue."""
        from cc_deep_research.content_gen.storage import PublishQueueStore

        store = PublishQueueStore()
        items = store.load()
        if not items:
            click.echo("Publish queue is empty.")
            return
        for item in items:
            click.echo(
                f"  {item.idea_id} | {item.platform} | {item.publish_datetime} | {item.status}"
            )

    # ------------------------------------------------------------------
    # Performance commands
    # ------------------------------------------------------------------

    @content_gen.command()
    @click.option("--video-id", required=True, help="Video ID")
    @click.option("--metrics-file", type=click.Path(exists=True), help="JSON file with metrics")
    @click.option("--script", default="", help="Video script text")
    @click.option("-o", "--output", type=click.Path(), default=None)
    def performance(
        video_id: str, metrics_file: str | None, script: str, output: str | None
    ) -> None:
        """Analyze video performance and generate follow-up ideas."""
        import json

        config = load_config()
        metrics: dict = {}
        if metrics_file:
            metrics = json.loads(Path(metrics_file).read_text())

        async def _run() -> None:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)

            click.echo(f'Analyzing performance for video: "{video_id}"...')
            result = await orch.run_performance(video_id=video_id, metrics=metrics, script=script)

            click.echo("\nWhat worked:")
            for w in result.what_worked[:5]:
                click.echo(f"  - {w}")
            click.echo("\nWhat failed:")
            for f in result.what_failed[:5]:
                click.echo(f"  - {f}")
            click.echo(f"\nLesson: {result.lesson}")
            click.echo(f"Next test: {result.next_test}")
            click.echo("\nFollow-up ideas:")
            for idea in result.follow_up_ideas[:5]:
                click.echo(f"  - {idea}")

            if output:
                Path(output).write_text(result.model_dump_json(indent=2))
                click.echo(f"\nSaved to: {output}")

        asyncio.run(_run())

    @content_gen.group()
    def learnings() -> None:
        """Review and apply performance learnings."""

    @learnings.command("list")
    @click.option("--category", default=None, help="Optional learning category filter")
    @click.option("--durability", default=None, help="Optional durability filter")
    def learnings_list(category: str | None, durability: str | None) -> None:
        from cc_deep_research.content_gen.models import LearningCategory, LearningDurability
        from cc_deep_research.content_gen.storage import PerformanceLearningStore

        store = PerformanceLearningStore()
        learnings = store.get_active_learnings(
            category=LearningCategory(category) if category else None,
            durability=LearningDurability(durability) if durability else None,
        )
        if not learnings:
            click.echo("No active learnings found.")
            return
        for learning in learnings:
            click.echo(f"{learning.learning_id} [{learning.category.value}/{learning.durability.value}]")
            click.echo(f"  Observation: {learning.observation}")
            click.echo(f"  Guidance: {learning.guidance}")
            if learning.source_video_ids:
                click.echo(f"  Source videos: {', '.join(learning.source_video_ids[:3])}")

    @learnings.command("apply")
    @click.option("--learning-id", "learning_ids", multiple=True, required=True, help="Learning ID to promote into durable strategy guidance")
    @click.option("--approved-by", default="operator", help="Operator applying the learning")
    def learnings_apply(learning_ids: tuple[str, ...], approved_by: str) -> None:
        from cc_deep_research.content_gen.storage import PerformanceLearningStore

        store = PerformanceLearningStore()
        guidance = store.apply_learnings_to_strategy(
            list(learning_ids),
            operator_approved=True,
            record_versions=True,
        )
        click.echo(f"Applied {len(learning_ids)} learning(s) to strategy guidance.")
        click.echo(f"Winning hooks: {len(guidance.winning_hooks)}")
        click.echo(f"Winning framings: {len(guidance.winning_framings)}")
        click.echo(f"Proof expectations: {len(guidance.proof_expectations)}")
        click.echo(f"Approved by: {approved_by}")

    @learnings.command("rules")
    @click.option("--kind", default=None, help="Optional rule kind filter")
    def learnings_rules(kind: str | None) -> None:
        from cc_deep_research.telemetry.query import query_content_gen_rule_versions

        result = query_content_gen_rule_versions(kind=kind)
        versions = result.get("versions", [])
        if not versions:
            click.echo("No rule versions recorded.")
            return
        for version in versions:
            click.echo(f"{version['created_at']} [{version['kind']}/{version['operation']}]")
            click.echo(f"  {version['change_summary']}")

    @content_gen.command("operating-fitness")
    def operating_fitness() -> None:
        from cc_deep_research.telemetry.query import query_content_gen_operating_fitness

        result = query_content_gen_operating_fitness()
        summary = result.get("summary", {})
        if not summary:
            click.echo("No operating-fitness metrics recorded yet.")
            return
        for key, value in summary.items():
            click.echo(f"{key}: {value}")

    # ------------------------------------------------------------------
    # Script command (existing, preserved)
    # ------------------------------------------------------------------

    @content_gen.command()
    @click.option(
        "--idea", default=None, help="Raw video idea (required unless --from-file is given)"
    )
    @click.option(
        "--from-file",
        type=click.Path(exists=True),
        default=None,
        help="Resume from saved context JSON",
    )
    @click.option(
        "--from-step",
        type=int,
        default=None,
        help="Step number to resume from (1-10)",
    )
    @click.option("-o", "--output", type=click.Path(), default=None, help="Save output to file")
    @click.option(
        "--save-context",
        is_flag=True,
        help="Save intermediate context as JSON",
    )
    @click.option("--quiet", is_flag=True, help="Only show final result")
    @click.option(
        "--no-iterate",
        is_flag=True,
        help="Disable iterative evaluation even if enabled in config",
    )
    def script(
        idea: str | None,
        from_file: str | None,
        from_step: int | None,
        output: str | None,
        save_context: bool,
        quiet: bool,
        no_iterate: bool,
    ) -> None:
        """Run the 10-step scripting pipeline for a short-form video."""
        config = load_config()
        store = ScriptingStore()

        from cc_deep_research.content_gen.models import SCRIPTING_STEPS, ScriptingContext

        ctx: ScriptingContext | None = None
        step: int | None = None

        if from_file:
            ctx = ScriptingContext.model_validate_json(Path(from_file).read_text())
            step = from_step or 1
            if idea and idea != ctx.raw_idea:
                msg = "--idea does not match the saved context in --from-file"
                raise click.UsageError(msg)
            idea = idea or ctx.raw_idea
        else:
            if not idea:
                msg = "--idea is required unless --from-file is provided"
                raise click.UsageError(msg)
            step = from_step

        total = len(SCRIPTING_STEPS)

        if step is not None and not 1 <= step <= total:
            msg = f"--from-step must be between 1 and {total}"
            raise click.UsageError(msg)

        def progress(idx: int, label: str) -> None:
            if not quiet:
                click.echo(f"  Step {idx + 1}/{total}: {label}...")

        async def _run() -> ScriptingContext:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)

            if ctx is not None and step is not None:
                if not quiet:
                    click.echo(f"Resuming from step {step}/{total}...")
                return await orch.run_scripting_from_step(ctx, step, progress_callback=progress)
            else:
                if not quiet:
                    click.echo(f'Scripting: "{idea}"')
                    click.echo(f"Running {total}-step pipeline...\n")
                if config.content_gen.enable_iterative_mode and not no_iterate:
                    result_ctx, iter_state = await orch.run_scripting_iterative(
                        idea,
                        progress_callback=progress,  # type: ignore[arg-type]
                    )
                    if not quiet and iter_state.current_iteration > 1:
                        click.echo(f"\nCompleted in {iter_state.current_iteration} iterations")
                        if iter_state.is_converged:
                            click.echo(f"Convergence: {iter_state.convergence_reason}")
                    return result_ctx
                return await orch.run_scripting(idea, progress_callback=progress)  # type: ignore[arg-type]

        try:
            result = asyncio.run(_run())
        except Exception:
            # Auto-save context on failure if a path is available.
            _auto_save_failed_context(ctx, output, quiet)
            raise

        saved_run = store.save(result)

        # Output
        final = result.qc.final_script if result.qc else ""
        if not final:
            final = result.tightened.content if result.tightened else ""
        if not final:
            final = result.draft.content if result.draft else ""

        if not quiet:
            click.echo()
            if final:
                click.echo("=" * 60)
                click.echo("FINAL SCRIPT")
                click.echo("=" * 60)
                click.echo(final)
                click.echo("=" * 60)
                wc = len(final.split())
                click.echo(f"Word count: {wc}")
            else:
                click.echo("No script generated.")

        if output:
            Path(output).write_text(final)
            if not quiet:
                click.echo(f"\nSaved to: {output}")

        if not quiet:
            click.echo(f"Autosaved run: {saved_run.run_id}")
            click.echo(f"Latest script: {store.path / 'latest.txt'}")
            click.echo(f"Latest context: {store.path / 'latest.context.json'}")

        if save_context:
            ctx_path = output + ".context.json" if output else "scripting_context.json"
            Path(ctx_path).write_text(result.model_dump_json(indent=2))
            if not quiet:
                click.echo(f"Context saved to: {ctx_path}")

    @content_gen.group()
    def scripts() -> None:
        """Browse autosaved scripting runs."""

    @scripts.command("list")
    @click.option("--limit", type=int, default=10, help="Number of runs to show")
    def scripts_list(limit: int) -> None:
        """List recent autosaved scripting runs."""
        store = ScriptingStore()
        runs = store.list_runs(limit=limit)
        if not runs:
            click.echo(f"No saved scripting runs found in {store.path}")
            return

        click.echo(f"Saved scripting runs in {store.path}:")
        for run in runs:
            click.echo(f"  {run.run_id} | {run.saved_at} | {run.word_count} words | {run.raw_idea}")

    @scripts.command("show")
    @click.option("--run-id", default=None, help="Saved run id")
    @click.option("--latest", "use_latest", is_flag=True, help="Show the latest saved run")
    @click.option(
        "--context",
        "show_context",
        is_flag=True,
        help="Show saved context JSON instead of the final script",
    )
    def scripts_show(run_id: str | None, use_latest: bool, show_context: bool) -> None:
        """Show a saved scripting run or its context."""
        store = ScriptingStore()
        if use_latest or not run_id:
            run = store.latest()
        else:
            run = store.get(run_id)

        if run is None:
            target = run_id or "latest"
            click.echo(f"No saved scripting run found for: {target}")
            raise click.Abort()

        path = Path(run.context_path if show_context else run.script_path)
        click.echo(path.read_text())

    # ------------------------------------------------------------------
    # Pipeline command (expanded)
    # ------------------------------------------------------------------

    @content_gen.command()
    @click.option("--theme", default=None, help="Theme for backlog generation")
    @click.option("--idea", default=None, help="Skip backlog; start scripting with this idea")
    @click.option("--from-stage", type=int, default=None, help="Resume from stage (0-13)")
    @click.option("--to-stage", type=int, default=None, help="Stop after this stage")
    @click.option(
        "--from-file",
        type=click.Path(exists=True),
        default=None,
        help="Resume from saved PipelineContext",
    )
    @click.option("--content-type", default="", help="Run-level content type profile")
    @click.option(
        "--effort-tier",
        type=click.Choice(["quick", "standard", "deep"]),
        default=None,
        help="Run-level effort tier used for scoring, research depth, and iteration budgets",
    )
    @click.option("--owner", default="", help="Run owner for traceability and execution handoff")
    @click.option("--channel-goal", default="", help="Primary channel or distribution goal")
    @click.option("--success-target", default="", help="Current success target for this run")
    @click.option(
        "--research-depth-override",
        type=click.Choice(["light", "standard", "deep"]),
        default=None,
        help="Override automatic research-depth routing for this run",
    )
    @click.option(
        "--research-override-reason",
        default="",
        help="Why the automatic research-depth routing is being overridden",
    )
    @click.option("-o", "--output", type=click.Path(), default=None)
    @click.option("--save-context", is_flag=True, help="Save pipeline context as JSON")
    @click.option("--quiet", is_flag=True, help="Only show final result")
    def pipeline(
        theme: str | None,
        idea: str | None,
        from_stage: int | None,
        to_stage: int | None,
        from_file: str | None,
        content_type: str,
        effort_tier: str | None,
        owner: str,
        channel_goal: str,
        success_target: str,
        research_depth_override: str | None,
        research_override_reason: str,
        output: str | None,
        save_context: bool,
        quiet: bool,
    ) -> None:
        """Run the full content generation pipeline."""
        config = load_config()

        from cc_deep_research.content_gen.models import (
            PIPELINE_STAGES,
            BacklogItem,
            BacklogOutput,
            PipelineCandidate,
            PipelineContext,
            RunConstraints,
            ScoringOutput,
        )

        ctx: PipelineContext | None = None
        bypass_ideation = False

        if from_file:
            ctx = PipelineContext.model_validate_json(Path(from_file).read_text())
            if theme and ctx.theme and theme != ctx.theme:
                msg = "--theme does not match the saved context in --from-file"
                raise click.UsageError(msg)
            if idea:
                selected_item = None
                if ctx.backlog is not None:
                    selected_idea_id = ctx.selected_idea_id or (
                        ctx.scoring.selected_idea_id if ctx.scoring else ""
                    )
                    selected_item = next(
                        (item for item in ctx.backlog.items if item.idea_id == selected_idea_id),
                        None,
                    )
                saved_idea = selected_item.idea if selected_item is not None else ctx.theme
                if idea != saved_idea:
                    msg = "--idea does not match the saved context in --from-file"
                    raise click.UsageError(msg)
            theme = theme or ctx.theme
        elif idea:
            seeded_item = BacklogItem(
                idea=idea,
                source="direct_idea",
                source_theme=theme or idea,
                status="selected",
            )
            ctx = PipelineContext(
                theme=theme or idea,
                backlog=BacklogOutput(items=[seeded_item]),
                scoring=ScoringOutput(
                    produce_now=[seeded_item.idea_id],
                    shortlist=[seeded_item.idea_id],
                    selected_idea_id=seeded_item.idea_id,
                    selection_reasoning="Seeded directly from --idea.",
                    active_candidates=[
                        PipelineCandidate(
                            idea_id=seeded_item.idea_id, role="primary", status="selected"
                        )
                    ],
                ),
                shortlist=[seeded_item.idea_id],
                selected_idea_id=seeded_item.idea_id,
                selection_reasoning="Seeded directly from --idea.",
                active_candidates=[
                    PipelineCandidate(
                        idea_id=seeded_item.idea_id, role="primary", status="selected"
                    )
                ],
            )
            bypass_ideation = True
        elif not theme:
            msg = "--theme, --idea, or --from-file is required"
            raise click.UsageError(msg)

        start = from_stage if from_stage is not None else 0
        if from_file and from_stage is None and ctx is not None:
            start = ctx.current_stage + 1
            if start >= len(PIPELINE_STAGES):
                msg = "Saved context is already at the final stage; pass --from-stage to rerun a stage."
                raise click.UsageError(msg)

        if not 0 <= start < len(PIPELINE_STAGES):
            msg = f"--from-stage must be between 0 and {len(PIPELINE_STAGES) - 1}"
            raise click.UsageError(msg)
        if to_stage is not None and to_stage < start:
            msg = "--to-stage must be greater than or equal to --from-stage"
            raise click.UsageError(msg)

        context_output_path = _resolve_pipeline_context_path(output, save_context)
        latest_ctx = ctx

        if ctx is not None and ctx.run_constraints is not None:
            run_constraints = ctx.run_constraints.model_copy(deep=True)
        else:
            run_constraints = RunConstraints()
        if content_type:
            run_constraints.content_type = content_type
        if effort_tier:
            run_constraints.effort_tier = effort_tier
        if owner:
            run_constraints.owner = owner
        if channel_goal:
            run_constraints.channel_goal = channel_goal
        if success_target:
            run_constraints.success_target = success_target
        if research_depth_override:
            run_constraints.research_depth_override = research_depth_override
            run_constraints.research_override_reason = research_override_reason

        def progress(idx: int, label: str) -> None:
            if not quiet:
                click.echo(f"  Stage {idx + 1}/{len(PIPELINE_STAGES)}: {label}...")

        def on_stage_completed(
            _idx: int,
            _status: str,
            _detail: str,
            stage_ctx: PipelineContext,
        ) -> None:
            nonlocal latest_ctx
            latest_ctx = stage_ctx.model_copy(deep=True)
            if context_output_path is not None:
                _write_pipeline_context(stage_ctx, context_output_path)

        async def _run() -> PipelineContext:
            import inspect

            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            if ctx is not None:
                resume_error = orch.validate_resume_context(
                    from_stage=start,
                    ctx=ctx,
                    bypass_ideation=bypass_ideation,
                )
                if resume_error:
                    raise click.UsageError(resume_error)
            t = theme or idea or "general"
            kwargs = {
                "from_stage": start,
                "to_stage": to_stage,
                "initial_context": ctx,
                "bypass_ideation": bypass_ideation,
                "progress_callback": progress,
                "stage_completed_callback": on_stage_completed,
            }
            if "run_constraints" in inspect.signature(orch.run_full_pipeline).parameters:
                kwargs["run_constraints"] = run_constraints
            return await orch.run_full_pipeline(t, **kwargs)

        try:
            result = asyncio.run(_run())
        except Exception:
            _auto_save_failed_pipeline_context(
                latest_ctx,
                context_output_path,
                quiet,
            )
            if not quiet:
                click.echo("Pipeline failed.", err=True)
            raise

        if not quiet:
            click.echo()
            click.echo("=" * 60)
            click.echo("PIPELINE COMPLETE")
            click.echo("=" * 60)
            click.echo(f"Stages completed: {result.current_stage + 1}/{len(PIPELINE_STAGES)}")

            if result.backlog:
                click.echo(f"Backlog: {len(result.backlog.items)} ideas")
            if result.scoring:
                click.echo(
                    "Scoring: "
                    f"{len(result.scoring.produce_now)} produce now, "
                    f"{len(result.scoring.shortlist)} shortlisted, "
                    f"selected={result.selected_idea_id or result.scoring.selected_idea_id or 'none'}"
                )
            if result.angles:
                click.echo(f"Angles: {len(result.angles.angle_options)} generated")
            if result.scripting and result.scripting.qc:
                click.echo(f"Script: {len(result.scripting.qc.final_script.split())} words")
            if result.visual_plan:
                click.echo(f"Visual plan: {len(result.visual_plan.visual_plan)} beats")
            if result.packaging:
                click.echo(f"Packaging: {len(result.packaging.platform_packages)} platforms")
            if result.qc_gate:
                click.echo(f"QC: approved={result.qc_gate.approved_for_publish}")

        if context_output_path is not None:
            _write_pipeline_context(result, context_output_path)
            if not quiet:
                click.echo(f"\nContext saved to: {context_output_path}")

        if output:
            # Write final script to output
            final = ""
            if result.scripting and result.scripting.qc:
                final = result.scripting.qc.final_script
            Path(output).write_text(final)
            if not quiet:
                click.echo(f"Script saved to: {output}")

    # ------------------------------------------------------------------
    # Audit commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def audit() -> None:
        """Inspect AI proposal history and governance audit trail."""

    @audit.command()
    @click.option("--limit", type=int, default=50, help="Number of entries to show")
    @click.option("--event-type", help="Filter by event type (e.g., proposal_created)")
    @click.option("--actor", help="Filter by actor (operator, ai_proposal, maintenance)")
    def audit_list(limit: int, event_type: str | None, actor: str | None) -> None:
        """Show recent audit entries."""
        from cc_deep_research.content_gen.storage import AuditActor, AuditEventType

        store = AuditStore()
        try:
            evt_filter = AuditEventType(event_type) if event_type else None
        except ValueError:
            click.echo(f"Unknown event type: {event_type}")
            return
        try:
            actor_filter = AuditActor(actor) if actor else None
        except ValueError:
            click.echo(f"Unknown actor: {actor}")
            return

        entries = store.load_entries(event_type=evt_filter, actor=actor_filter, limit=limit)
        if not entries:
            click.echo("No audit entries found.")
            return

        click.echo(f"Audit log: {store.path}")
        click.echo(f"Showing {len(entries)} entries:\n")
        for e in entries:
            click.echo(f"  [{e.timestamp}] {e.event_type.value}")
            click.echo(f"    Actor: {e.actor.value} ({e.actor_label})")
            if e.idea_id:
                click.echo(f"    Item: {e.idea_id}")
            if e.proposal_id:
                click.echo(f"    Proposal: {e.proposal_id}")
            if e.description:
                click.echo(f"    {e.description}")
            click.echo(f"    Outcome: {e.outcome}")
            click.echo()

    @audit.command()
    @click.option("--idea-id", required=True, help="Filter by idea ID")
    @click.option("--limit", type=int, default=20, help="Number of entries to show")
    def audit_show(idea_id: str, limit: int) -> None:
        """Show audit history for a specific backlog item."""
        store = AuditStore()
        entries = store.load_entries(idea_id=idea_id, limit=limit)
        if not entries:
            click.echo(f"No audit entries found for item: {idea_id}")
            return

        click.echo(f"Audit history for {idea_id} ({len(entries)} entries):\n")
        for e in entries:
            click.echo(f"  [{e.timestamp}] {e.event_type.value}")
            click.echo(f"    Actor: {e.actor.value} ({e.actor_label})")
            if e.description:
                click.echo(f"    {e.description}")
            click.echo(f"    Outcome: {e.outcome}")
            click.echo()

    # ------------------------------------------------------------------
    # Brief commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def briefs() -> None:
        """Manage persistent opportunity briefs."""

    @briefs.command()
    def briefs_list() -> None:
        """List all managed briefs."""
        from cc_deep_research.content_gen.brief_service import BriefService

        service = BriefService()
        output = service.load()
        if not output.briefs:
            click.echo("No briefs found.")
            return

        click.echo(f"Briefs ({len(output.briefs)}):\n")
        for b in output.briefs:
            state = b.lifecycle_state.value.upper()
            click.echo(f"  [{state}] {b.brief_id}")
            click.echo(f"    Title: {b.title or '(untitled)'}")
            click.echo(f"    Revisions: {b.revision_count}")
            click.echo(f"    Updated: {b.updated_at or b.created_at}")
            click.echo()

    @briefs.command()
    def briefs_migrate() -> None:
        """Force-migrate YAML brief data to SQLite.

        Runs the one-time YAML import even if SQLite already has data.
        Existing SQLite records are preserved; only missing briefs are added.
        """
        from cc_deep_research.content_gen.storage import SqliteBriefStore

        click.echo("Running YAML -> SQLite brief migration...")

        store = SqliteBriefStore()
        yaml_path = store._yaml_path

        if yaml_path is None or not yaml_path.exists():
            click.echo("No YAML brief file found. Nothing to migrate.")
            return

        click.echo(f"YAML source: {yaml_path}")
        click.echo(f"SQLite destination: {store.path}")

        # Count before
        before = store.load()
        count_before = len(before.briefs)

        # Force re-import by temporarily renaming
        # We use the internal import method directly
        imported = store._import_from_yaml()
        if imported is None:
            click.echo("No briefs found in YAML file to migrate.")
            return

        count_imported = len(imported.briefs)
        after = store.load()
        count_after = len(after.briefs)

        click.echo("\nMigration complete.")
        click.echo(f"  Briefs in YAML: {count_imported}")
        click.echo(f"  Briefs before migration: {count_before}")
        click.echo(f"  Briefs after migration: {count_after}")
        click.echo(f"  New briefs added: {count_after - count_before}")

    @briefs.command()
    def briefs_health() -> None:
        """Check consistency between YAML and SQLite brief stores.

        Reports any discrepancies between the two stores and identifies
        briefs that exist only in one store or the other.
        """
        from cc_deep_research.content_gen.storage import BriefStore, SqliteBriefStore

        click.echo("Checking brief store health...\n")

        yaml_store = BriefStore()
        sqlite_store = SqliteBriefStore()

        yaml_output = yaml_store.load()
        sqlite_output = sqlite_store.load()

        yaml_ids = {b.brief_id for b in yaml_output.briefs}
        sqlite_ids = {b.brief_id for b in sqlite_output.briefs}

        yaml_only = yaml_ids - sqlite_ids
        sqlite_only = sqlite_ids - yaml_ids
        common = yaml_ids & sqlite_ids

        click.echo(f"YAML store: {len(yaml_output.briefs)} briefs")
        click.echo(f"SQLite store: {len(sqlite_output.briefs)} briefs")
        click.echo(f"Common: {len(common)}")
        click.echo()

        if yaml_only:
            click.echo(f"Only in YAML ({len(yaml_only)}):")
            for bid in sorted(yaml_only):
                click.echo(f"  - {bid}")
            click.echo()

        if sqlite_only:
            click.echo(f"Only in SQLite ({len(sqlite_only)}):")
            for bid in sorted(sqlite_only):
                click.echo(f"  - {bid}")
            click.echo()

        if not yaml_only and not sqlite_only:
            click.echo("Stores are in sync.")
        else:
            click.echo("Run 'briefs migrate' to sync SQLite from YAML.")

    @briefs.command()
    @click.option("--brief-id", required=True, help="Brief ID to inspect")
    def briefs_show(brief_id: str) -> None:
        """Show details of a specific brief."""
        from cc_deep_research.content_gen.brief_service import BriefService

        service = BriefService()
        managed = service.get_brief(brief_id)
        if managed is None:
            click.echo(f"Brief not found: {brief_id}")
            raise click.Abort()

        click.echo(f"Brief: {managed.brief_id}")
        click.echo(f"  Title: {managed.title or '(untitled)'}")
        click.echo(f"  State: {managed.lifecycle_state.value.upper()}")
        click.echo(f"  Provenance: {managed.provenance.value}")
        click.echo(f"  Revisions: {managed.revision_count}")
        click.echo(f"  Current: {managed.current_revision_id}")
        click.echo(f"  Latest: {managed.latest_revision_id}")
        click.echo(f"  Created: {managed.created_at}")
        click.echo(f"  Updated: {managed.updated_at}")
        if managed.source_brief_id:
            click.echo(f"  Source: {managed.source_brief_id}")
        if managed.branch_reason:
            click.echo(f"  Branch reason: {managed.branch_reason}")
        if managed.revision_history:
            click.echo("  Revision history:")
            for entry in managed.revision_history:
                click.echo(f"    - {entry}")

        # Show current revision content
        if managed.current_revision_id:
            rev = service.get_revision(managed.current_revision_id)
            if rev:
                click.echo(f"\n  Current revision ({rev.revision_id}):")
                click.echo(f"    Version: {rev.version}")
                click.echo(f"    Theme: {rev.theme or '(none)'}")
                click.echo(f"    Goal: {rev.goal or '(none)'}")
                click.echo(f"    Audience: {rev.primary_audience_segment or '(none)'}")
                if rev.problem_statements:
                    click.echo(f"    Problems ({len(rev.problem_statements)}):")
                    for p in rev.problem_statements[:3]:
                        click.echo(f"      - {p[:80]}...")
                if rev.sub_angles:
                    click.echo(f"    Sub-angles ({len(rev.sub_angles)}): {', '.join(rev.sub_angles[:3])}")

    # ------------------------------------------------------------------
    # Maintenance commands
    # ------------------------------------------------------------------

    @content_gen.group()
    def maintenance() -> None:
        """Manage background maintenance workflows and proposals."""

    @maintenance.command()
    @click.option(
        "--status", help="Filter by status (pending, approved, rejected, applied, expired)"
    )
    @click.option(
        "--job-type",
        help="Filter by job type (stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend)",
    )
    @click.option("--limit", type=int, default=50, help="Number of proposals to show")
    def maintenance_list(status: str | None, job_type: str | None, limit: int) -> None:
        """List maintenance proposals."""
        from cc_deep_research.content_gen.maintenance_workflow import (
            MaintenanceJobType,
            MaintenanceProposalStatus,
            MaintenanceStore,
        )

        store = MaintenanceStore()
        try:
            status_filter = MaintenanceProposalStatus(status) if status else None
        except ValueError:
            click.echo(f"Unknown status: {status}")
            return
        try:
            job_filter = MaintenanceJobType(job_type) if job_type else None
        except ValueError:
            click.echo(f"Unknown job type: {job_type}")
            return

        proposals = store.load_proposals(status=status_filter, job_type=job_filter, limit=limit)
        if not proposals:
            click.echo("No maintenance proposals found.")
            return

        click.echo(f"Proposals: {store._proposals_path}")
        click.echo(f"Showing {len(proposals)} proposals:\n")
        for p in proposals:
            click.echo(f"  [{p.status.value}] {p.title}")
            click.echo(f"    Job: {p.job_type.value} | Priority: {p.priority}")
            click.echo(f"    ID: {p.proposal_id} | Created: {p.created_at}")
            if p.affected_idea_ids:
                click.echo(f"    Items: {', '.join(p.affected_idea_ids[:5])}")
            if p.description:
                click.echo(f"    {p.description[:100]}...")
            if p.reviewed_by:
                click.echo(f"    Reviewed by: {p.reviewed_by} at {p.reviewed_at}")
            click.echo()

    @maintenance.command()
    @click.option(
        "--job-type",
        required=True,
        help="Job type to run (stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend)",
    )
    def maintenance_run(job_type: str) -> None:
        """Trigger a maintenance job immediately."""
        from cc_deep_research.content_gen.maintenance_workflow import (
            MaintenanceJobType,
            MaintenanceScheduler,
        )

        try:
            jt = MaintenanceJobType(job_type)
        except ValueError:
            click.echo(f"Unknown job type: {job_type}")
            click.echo(
                "Valid types: stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend"
            )
            return

        config = load_config()
        scheduler = MaintenanceScheduler(config=config)
        click.echo(f"Running maintenance job: {jt.value}...")
        run = scheduler.trigger_job(jt)
        click.echo(f"Job completed: {run.outcome}")
        click.echo(f"Proposals generated: {run.proposals_count}")
        click.echo(f"Duration: {run.completed_at}")

    @maintenance.command()
    @click.option("--proposal-id", required=True, help="Proposal ID to resolve")
    @click.option(
        "--approve",
        "decision",
        flag_value="approved",
        default=True,
        help="Approve the proposal (default)",
    )
    @click.option("--reject", "decision", flag_value="rejected", help="Reject the proposal")
    @click.option("--by", "reviewed_by", default="operator", help="Reviewer identity")
    def maintenance_resolve(proposal_id: str, decision: str, reviewed_by: str) -> None:
        """Resolve (approve or reject) a maintenance proposal."""
        from cc_deep_research.content_gen.maintenance_workflow import MaintenanceStore

        if decision is None:
            decision = "approved"

        store = MaintenanceStore()
        proposal = store.resolve_proposal(proposal_id, decision, reviewed_by=reviewed_by)
        if proposal is None:
            click.echo(f"Proposal not found: {proposal_id}")
            return

        click.echo(f"Proposal {proposal_id} {decision}")
        click.echo(f"  Title: {proposal.title}")
        click.echo(f"  Reviewed by: {proposal.reviewed_by} at {proposal.reviewed_at}")

    @maintenance.command()
    @click.option("--limit", type=int, default=20, help="Number of runs to show")
    def maintenance_runs(limit: int) -> None:
        """Show recent maintenance run history."""
        from cc_deep_research.content_gen.maintenance_workflow import MaintenanceStore

        store = MaintenanceStore()
        runs = store.load_runs(limit=limit)
        if not runs:
            click.echo("No maintenance runs found.")
            return

        click.echo(f"Maintenance runs history ({len(runs)} entries):\n")
        for r in runs:
            click.echo(f"  [{r.outcome}] {r.job_type.value}")
            click.echo(f"    Run: {r.run_id} | Started: {r.started_at}")
            click.echo(f"    Proposals: {r.proposals_count} | Completed: {r.completed_at}")
            if r.error:
                click.echo(f"    Error: {r.error[:100]}...")
            click.echo()


def _auto_save_failed_context(
    ctx: ScriptingContext | None,
    output: str | None,
    quiet: bool,
) -> None:
    """Best-effort save of context when the pipeline crashes."""
    if ctx is None:
        return
    try:
        fallback_path = output + ".context.json" if output else "scripting_context_failed.json"
        Path(fallback_path).write_text(ctx.model_dump_json(indent=2))
        if not quiet:
            click.echo(f"\nPipeline failed. Partial context saved to: {fallback_path}", err=True)
    except Exception:
        pass  # best-effort; don't mask the original error


def _resolve_pipeline_context_path(output: str | None, save_context: bool) -> str | None:
    """Return the intended pipeline context path for explicit saves."""
    if output:
        return output + ".context.json"
    if save_context:
        return "pipeline_context.json"
    return None


def _write_pipeline_context(ctx: PipelineContext, path: str) -> None:
    """Persist a pipeline context snapshot."""
    Path(path).write_text(ctx.model_dump_json(indent=2))


def _auto_save_failed_pipeline_context(
    ctx: PipelineContext | None,
    output_path: str | None,
    quiet: bool,
) -> None:
    """Best-effort save of partial pipeline context on failure."""
    if ctx is None:
        return
    try:
        fallback_path = output_path or "pipeline_context_failed.json"
        _write_pipeline_context(ctx, fallback_path)
        if not quiet:
            click.echo(f"\nPipeline failed. Partial context saved to: {fallback_path}", err=True)
    except Exception:
        pass


def _load_packaging_inputs(text: str) -> tuple[ScriptVersion, AngleOption]:
    """Extract packaging inputs from workflow context JSON."""
    from cc_deep_research.content_gen.models import (
        AngleOption,
        PipelineContext,
        ScriptingContext,
    )

    try:
        pipeline_ctx = PipelineContext.model_validate_json(text)
    except Exception:
        pipeline_ctx = None

    if pipeline_ctx is not None:
        script = _extract_script_from_pipeline_context(pipeline_ctx)
        angle = _extract_angle_from_pipeline_context(pipeline_ctx)
        if script is not None and angle is not None:
            return script, angle

    scripting_ctx = ScriptingContext.model_validate_json(text)
    script = _extract_script_from_scripting_context(scripting_ctx)
    if script is None or scripting_ctx.angle is None:
        msg = "Packaging requires a saved scripting or pipeline context with a final script and angle."
        raise click.UsageError(msg)

    return (
        script,
        AngleOption(
            target_audience=scripting_ctx.core_inputs.audience if scripting_ctx.core_inputs else "",
            viewer_problem=scripting_ctx.angle.core_tension,
            core_promise=scripting_ctx.angle.angle,
            primary_takeaway=scripting_ctx.core_inputs.outcome if scripting_ctx.core_inputs else "",
            lens=scripting_ctx.angle.content_type,
            tone="",
        ),
    )


def _extract_script_from_pipeline_context(ctx: PipelineContext) -> ScriptVersion | None:

    if ctx.scripting is None:
        return None
    return _extract_script_from_scripting_context(ctx.scripting)


def _extract_script_from_scripting_context(ctx: ScriptingContext) -> ScriptVersion | None:
    from cc_deep_research.content_gen.models import ScriptVersion

    if ctx.qc and ctx.qc.final_script:
        content = ctx.qc.final_script
    elif ctx.tightened and ctx.tightened.content:
        content = ctx.tightened.content
    elif ctx.draft and ctx.draft.content:
        content = ctx.draft.content
    else:
        return None
    return ScriptVersion(content=content, word_count=len(content.split()))


def _extract_angle_from_pipeline_context(ctx: PipelineContext) -> AngleOption | None:

    if ctx.angles is None:
        return None
    if ctx.angles.selected_angle_id:
        for option in ctx.angles.angle_options:
            if option.angle_id == ctx.angles.selected_angle_id:
                return option
    if ctx.angles.angle_options:
        return ctx.angles.angle_options[0]
    return None


__all__ = ["register_content_gen_commands"]
