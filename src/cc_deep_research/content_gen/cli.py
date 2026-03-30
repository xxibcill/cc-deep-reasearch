"""CLI commands for the content generation workflow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import click

from cc_deep_research.config import load_config
from cc_deep_research.content_gen.storage import ScriptingStore

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext, ScriptingContext

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
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            click.echo(f'Building backlog for: "{theme}" ({count} ideas)...')
            result = await orch.run_backlog(theme, count=count)

            click.echo(f"\nGenerated {len(result.items)} ideas, rejected {result.rejected_count}")
            for item in result.items:
                click.echo(f"  [{item.category}] {item.idea}")

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
            from cc_deep_research.content_gen.models import BacklogOutput
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            items = []
            if from_file:
                data = BacklogOutput.model_validate_json(Path(from_file).read_text())
                items = data.items

            if not items:
                click.echo("No items to score. Use --from-file or build a backlog first.")
                return

            click.echo(f"Scoring {len(items)} ideas...")
            result = await orch.run_scoring(items)

            click.echo(f"\nProduce now ({len(result.produce_now)}):")
            for sid in result.produce_now[:select_top]:
                score = next((s for s in result.scores if s.idea_id == sid), None)
                if score:
                    click.echo(f"  {sid}: {score.total_score}/35 — {score.reason}")

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
            click.echo(f"Clarity issues: {len(result.clarity_issues)}")
            click.echo(f"Factual issues: {len(result.factual_issues)}")
            click.echo(f"Must fix: {len(result.must_fix_items)}")
            for item in result.must_fix_items:
                click.echo(f"  - {item}")
            click.echo(f"\nApproved: {result.approved_for_publish}")

        asyncio.run(_run())

    @qc.command()
    @click.option("--idea-id", required=True, help="Idea ID to approve")
    @click.option(
        "--from-file",
        type=click.Path(exists=True),
        required=True,
        help="Pipeline context JSON to update",
    )
    def qc_approve(idea_id: str, from_file: str) -> None:
        """Manually approve a video for publish. Only humans can do this."""
        from cc_deep_research.content_gen.models import PipelineContext

        path = Path(from_file)
        ctx = PipelineContext.model_validate_json(path.read_text())

        if ctx.qc_gate is None:
            click.echo("No QC gate found in context. Run 'qc review' first.")
            return

        ctx.qc_gate.approved_for_publish = True
        path.write_text(ctx.model_dump_json(indent=2))
        click.echo(f"Approved idea {idea_id} for publish.")

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
                        idea, progress_callback=progress  # type: ignore[arg-type]
                    )
                    if not quiet and iter_state.current_iteration > 1:
                        click.echo(
                            f"\nCompleted in {iter_state.current_iteration} iterations"
                        )
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
            click.echo(
                f"  {run.run_id} | {run.saved_at} | {run.word_count} words | {run.raw_idea}"
            )

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
    @click.option("--from-stage", type=int, default=None, help="Resume from stage (0-11)")
    @click.option("--to-stage", type=int, default=None, help="Stop after this stage")
    @click.option(
        "--from-file",
        type=click.Path(exists=True),
        default=None,
        help="Resume from saved PipelineContext",
    )
    @click.option("-o", "--output", type=click.Path(), default=None)
    @click.option("--save-context", is_flag=True, help="Save pipeline context as JSON")
    @click.option("--quiet", is_flag=True, help="Only show final result")
    def pipeline(
        theme: str | None,
        idea: str | None,
        from_stage: int | None,
        to_stage: int | None,
        from_file: str | None,  # noqa: ARG001
        output: str | None,
        save_context: bool,
        quiet: bool,
    ) -> None:
        """Run the full content generation pipeline."""
        config = load_config()

        from cc_deep_research.content_gen.models import PIPELINE_STAGES

        start = from_stage or 0
        if not 0 <= start < len(PIPELINE_STAGES):
            msg = f"--from-stage must be between 0 and {len(PIPELINE_STAGES) - 1}"
            raise click.UsageError(msg)

        def progress(idx: int, label: str) -> None:
            if not quiet:
                click.echo(f"  Stage {idx + 1}/{len(PIPELINE_STAGES)}: {label}...")

        async def _run() -> PipelineContext:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            t = theme or idea or "general"
            return await orch.run_full_pipeline(
                t,
                from_stage=start,
                to_stage=to_stage,
                progress_callback=progress,
            )

        try:
            result = asyncio.run(_run())
        except Exception:
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
                click.echo(f"Scoring: {len(result.scoring.produce_now)} produce now")
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

        if save_context or output:
            ctx_path = (output + ".context.json") if output else "pipeline_context.json"
            Path(ctx_path).write_text(result.model_dump_json(indent=2))
            if not quiet:
                click.echo(f"\nContext saved to: {ctx_path}")

        if output:
            # Write final script to output
            final = ""
            if result.scripting and result.scripting.qc:
                final = result.scripting.qc.final_script
            Path(output).write_text(final)
            if not quiet:
                click.echo(f"Script saved to: {output}")


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


def _load_packaging_inputs(text: str) -> tuple[ScriptVersion, AngleOption]:
    """Extract packaging inputs from workflow context JSON."""
    from cc_deep_research.content_gen.models import (
        AngleOption,
        PipelineContext,
        ScriptVersion,
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
    from cc_deep_research.content_gen.models import ScriptVersion

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
    from cc_deep_research.content_gen.models import AngleOption

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
