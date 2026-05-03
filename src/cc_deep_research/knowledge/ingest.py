"""Ingest a ResearchSession into the knowledge vault."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cc_deep_research.knowledge import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
    PageFrontmatter,
    PageStatus,
)
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.vault import (
    claims_dir,
    graph_sqlite_path,
    init_vault,
    questions_dir,
    raw_session_dir,
    raw_source_file,
    sessions_dir,
    sources_dir,
    vault_root,
    wiki_log_path,
)

if TYPE_CHECKING:
    from cc_deep_research.models import ResearchSession
    from cc_deep_research.models.quality import CrossReferenceClaim
    from cc_deep_research.models.search import SearchResultItem


def _slug(text: str) -> str:
    """Convert text to a kebab-case slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return re.sub(r'-+', '-', text).strip('-')


def _node_id(kind: NodeKind, stem: str) -> str:
    return f"{kind.value}:{stem}"


def _claim_stem(claim_text: str) -> str:
    """Derive a stable stem from claim text."""
    text = claim_text.strip()
    if len(text) > 60:
        text = text[:60]
    return _slug(text)


def _url_stem(url: str) -> str:
    """Derive a stable stem from a URL."""
    parsed = url.split("?")[0].split("#")[0].rstrip("/")
    if "/" in parsed:
        stem = parsed.split("/")[-1]
    else:
        stem = parsed
    if not stem:
        stem = _slug(parsed)
    return _slug(stem)


def _ingest_manifest(
    session_id: str,
    *,
    sources_count: int,
    claims_count: int,
    findings_count: int,
    gaps_count: int,
    config_path: Path | None = None,
) -> dict:
    """Write an ingest manifest for the session."""
    manifest = {
        "session_id": session_id,
        "ingested_at": datetime.now(UTC).isoformat(),
        "counts": {
            "sources": sources_count,
            "claims": claims_count,
            "findings": findings_count,
            "gaps": gaps_count,
        },
    }
    path = raw_session_dir(session_id, config_path) / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# Raw artifact snapshotting
# ---------------------------------------------------------------------------


def _snapshot_session(
    session: ResearchSession,
    *,
    config_path: Path | None = None,
) -> None:
    """Write the session JSON to raw storage."""
    path = raw_source_file(session.session_id, session.session_id, "session", config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.model_dump_json(indent=2), encoding="utf-8")


def _snapshot_report(
    session_id: str,
    report_md: str | None,
    *,
    config_path: Path | None = None,
) -> None:
    """Write the markdown report to raw storage."""
    if report_md is None:
        return
    path = raw_source_file(session_id, session_id, "report", config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_md, encoding="utf-8")


def _snapshot_sources(
    session: ResearchSession,
    *,
    config_path: Path | None = None,
) -> None:
    """Write the session's sources to raw storage."""
    if not session.sources:
        return
    path = raw_source_file(session.session_id, session.session_id, "sources", config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [s.model_dump(mode="json") for s in session.sources]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Wiki page generation
# ---------------------------------------------------------------------------


def _yaml_frontmatter(fm: PageFrontmatter) -> str:
    """Serialize page frontmatter as YAML."""
    import yaml

    raw = fm.model_dump(mode="python")
    # Prune None values for cleanliness
    pruned = {k: v for k, v in raw.items() if v is not None}
    return "---\n" + yaml.dump(pruned, default_flow_style=False, sort_keys=False).rstrip()


def _write_page(
    content: str,
    dir_fn: Callable[[Path | None], Path],
    filename: str,
    config_path: Path | None = None,
) -> Path:
    """Write a wiki page, creating its directory if needed."""
    path = dir_fn(config_path) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _ingest_session_page(
    session: ResearchSession,
    *,
    config_path: Path | None = None,
) -> KnowledgeNode:
    """Create or update the wiki page for a research session."""
    node_id = _node_id(NodeKind.SESSION, session.session_id)
    stem = session.session_id

    fm = PageFrontmatter(
        id=node_id,
        kind=NodeKind.SESSION,
        title=session.query,
        status=PageStatus.STABLE,
        tags=[session.depth.value] if session.depth else [],
        session_ids=[session.session_id],
        confidence=0.8,
    )

    lines = [
        _yaml_frontmatter(fm),
        "",
        f"# Research Session: {session.query}",
        "",
        f"**Session ID:** `{session.session_id}`",
        f"**Depth:** {session.depth.value if session.depth else 'unknown'}",
        f"**Started:** {session.started_at.isoformat()}",
    ]
    if session.completed_at:
        lines.append(f"**Completed:** {session.completed_at.isoformat()}")
        lines.append(f"**Duration:** {session.execution_time_seconds:.1f}s")

    analysis = session.metadata.get("analysis", {})
    if analysis:
        key_findings = analysis.get("key_findings", [])
        if key_findings:
            lines.append("")
            lines.append("## Key Findings")
            for f in key_findings:
                title = f.get("title") if isinstance(f, dict) else str(f)
                lines.append(f"- {title}")

        gaps = analysis.get("gaps", [])
        if gaps:
            lines.append("")
            lines.append("## Gaps Identified")
            for g in gaps:
                desc = g.get("gap_description") if isinstance(g, dict) else str(g)
                lines.append(f"- {desc}")

    sources = session.metadata.get("providers", {}).get("available", [])
    if sources:
        lines.append("")
        lines.append(f"**Sources used:** {', '.join(sources)}")

    lines.append("")
    lines.append(f"<!-- Auto-generated by ingest on {datetime.now(UTC).date().isoformat()} -->")

    content = "\n".join(lines)
    _write_page(content, sessions_dir, f"{stem}.md", config_path)

    return KnowledgeNode(
        id=node_id,
        kind=NodeKind.SESSION,
        label=session.query,
        properties={
            "depth": session.depth.value if session.depth else None,
            "source_count": session.total_sources,
        },
    )


def _ingest_source_page(
    source: SearchResultItem,
    session_id: str,
    *,
    config_path: Path | None = None,
) -> KnowledgeNode:
    """Create or update the wiki page for a source."""
    stem = _url_stem(source.url)
    node_id = _node_id(NodeKind.SOURCE, stem)

    fm = PageFrontmatter(
        id=node_id,
        kind=NodeKind.SOURCE,
        title=source.title or source.url,
        status=PageStatus.STABLE,
        tags=["source"],
        source_ids=[stem],
        session_ids=[session_id],
        confidence=0.8,
    )

    lines = [
        _yaml_frontmatter(fm),
        "",
        f"# Source: {source.title or source.url}",
        "",
        f"**URL:** {source.url}",
        f"**Score:** {source.score:.2f}" if source.score else "",
    ]

    if source.snippet:
        lines.append("")
        lines.append(f"> {source.snippet}")

    queries = [p.query for p in source.query_provenance]
    if queries:
        lines.append("")
        lines.append("**Retrieved by queries:**")
        for q in queries:
            lines.append(f"- {q}")

    lines.append("")
    lines.append(f"<!-- Auto-generated by ingest on {datetime.now(UTC).date().isoformat()} -->")

    content = "\n".join(line for line in lines if line)
    _write_page(content, sources_dir, f"{stem}.md", config_path)

    return KnowledgeNode(
        id=node_id,
        kind=NodeKind.SOURCE,
        label=source.title or source.url,
        properties={
            "url": source.url,
            "score": source.score,
        },
    )


def _ingest_claim_page(
    claim: CrossReferenceClaim,
    session_id: str,
    *,
    config_path: Path | None = None,
) -> tuple[KnowledgeNode, list[KnowledgeEdge]]:
    """Create or update the wiki page for a claim with source backing."""
    stem = _claim_stem(claim.claim)
    node_id = _node_id(NodeKind.CLAIM, stem)

    supporting = claim.supporting_sources
    contradicting = claim.contradicting_sources

    has_support = bool(supporting)
    status = PageStatus.STABLE if has_support else PageStatus.NEEDS_REVIEW

    fm = PageFrontmatter(
        id=node_id,
        kind=NodeKind.CLAIM,
        title=claim.claim[:120],
        status=status,
        tags=["claim"],
        source_ids=[s.url for s in supporting],
        session_ids=[session_id],
        confidence=0.8 if has_support else 0.3,
    )

    lines = [
        _yaml_frontmatter(fm),
        "",
        f"# Claim: {claim.claim}",
        "",
        f"**Confidence:** {claim.confidence or 'unknown'}",
        f"**Freshness:** {claim.freshness.value if claim.freshness else 'unknown'}",
        f"**Evidence type:** {claim.evidence_type.value if claim.evidence_type else 'unknown'}",
        f"**Consensus level:** {claim.consensus_level:.2f}" if claim.consensus_level else "",
    ]

    if supporting:
        lines.append("")
        lines.append("## Supporting Sources")
        for src in supporting:
            title = src.title or src.url
            lines.append(f"- [{title}]({src.url})")
            if src.snippet:
                lines.append(f"  > {src.snippet[:150]}")

    if contradicting:
        lines.append("")
        lines.append("## Contradicting Sources")
        for src in contradicting:
            title = src.title or src.url
            lines.append(f"- [{title}]({src.url})")

    if not supporting:
        lines.append("")
        lines.append("⚠️ **No supporting sources — claim is unsupported.**")

    lines.append("")
    lines.append(f"<!-- Auto-generated by ingest on {datetime.now(UTC).date().isoformat()} -->")

    content = "\n".join(line for line in lines if line)
    _write_page(content, claims_dir, f"{stem}.md", config_path)

    node = KnowledgeNode(
        id=node_id,
        kind=NodeKind.CLAIM,
        label=claim.claim[:80],
        properties={
            "confidence": claim.confidence,
            "freshness": claim.freshness.value if claim.freshness else None,
            "consensus_level": claim.consensus_level,
        },
    )

    edges: list[KnowledgeEdge] = []
    for src in supporting:
        src_stem = _url_stem(src.url)
        src_id = _node_id(NodeKind.SOURCE, src_stem)
        edge_id = f"cited:{node_id}:{src_id}"
        edges.append(
            KnowledgeEdge(
                id=edge_id,
                source_id=src_id,
                target_id=node_id,
                kind=EdgeKind.CITED,
            )
        )
    for src in contradicting:
        src_stem = _url_stem(src.url)
        src_id = _node_id(NodeKind.SOURCE, src_stem)
        edge_id = f"contradicts:{node_id}:{src_id}"
        edges.append(
            KnowledgeEdge(
                id=edge_id,
                source_id=src_id,
                target_id=node_id,
                kind=EdgeKind.CONTRADICTS,
            )
        )

    return node, edges


def _ingest_gap_page(
    gap_description: str,
    suggested_queries: list[str],
    session_id: str,
    importance: str | None,
    *,
    config_path: Path | None = None,
) -> KnowledgeNode:
    """Create or update the wiki page for a research gap."""
    stem = _slug(gap_description)[:60]
    node_id = _node_id(NodeKind.GAP, stem)

    fm = PageFrontmatter(
        id=node_id,
        kind=NodeKind.GAP,
        title=gap_description[:120],
        status=PageStatus.NEEDS_REVIEW,
        tags=["gap"],
        session_ids=[session_id],
        confidence=0.4,
    )

    lines = [
        _yaml_frontmatter(fm),
        "",
        f"# Research Gap: {gap_description}",
        "",
    ]

    if importance:
        lines.append(f"**Importance:** {importance}")

    if suggested_queries:
        lines.append("")
        lines.append("## Suggested Follow-up Queries")
        for q in suggested_queries:
            lines.append(f"- {q}")

    lines.append("")
    lines.append(f"<!-- Auto-generated by ingest on {datetime.now(UTC).date().isoformat()} -->")

    content = "\n".join(lines)
    _write_page(content, questions_dir, f"{stem}.md", config_path)

    return KnowledgeNode(
        id=node_id,
        kind=NodeKind.GAP,
        label=gap_description[:80],
        properties={"importance": importance},
    )


def _append_log_entry(session_id: str, event: str, config_path: Path | None = None) -> None:
    """Append an entry to the vault activity log."""
    log = wiki_log_path(config_path)
    if not log.exists():
        return
    timestamp = datetime.now(UTC).isoformat()
    entry = f"\n- **{timestamp}** [{event}] session=`{session_id}`\n"
    with open(log, "a", encoding="utf-8") as f:
        f.write(entry)


def ingest_session(
    session: ResearchSession,
    report_md: str | None = None,
    *,
    config_path: Path | None = None,
) -> IngestResult:
    """Ingest a completed ResearchSession into the knowledge vault.

    This is a non-fatal operation: ingest errors are logged as warnings
    but do not raise exceptions.
    """
    warnings: list[str] = []

    try:
        vault_root(config_path).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        warnings.append(f"Could not create vault root: {exc}")

    try:
        init_vault(config_path)
    except Exception as exc:
        warnings.append(f"Could not initialize vault: {exc}")

    # Always use a persisted SQLite index when vault is available
    try:
        db_path = graph_sqlite_path(config_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        index = GraphIndex(db_path)
    except Exception as exc:
        warnings.append(f"Could not open graph index: {exc}")
        index = GraphIndex()

    try:
        _snapshot_session(session, config_path=config_path)
        _snapshot_report(session.session_id, report_md, config_path=config_path)
        _snapshot_sources(session, config_path=config_path)
    except Exception as exc:
        warnings.append(f"Could not snapshot raw artifacts: {exc}")

    nodes: list[KnowledgeNode] = []
    edges: list[KnowledgeEdge] = []

    try:
        session_node = _ingest_session_page(session, config_path=config_path)
        nodes.append(session_node)
        index.upsert_node(session_node)
    except Exception as exc:
        warnings.append(f"Could not ingest session page: {exc}")

    # Ingest sources
    sources_ingested = 0
    for source in session.sources:
        try:
            src_node = _ingest_source_page(source, session.session_id, config_path=config_path)
            nodes.append(src_node)
            index.upsert_node(src_node)

            edge_id = f"session-source:{session.session_id}:{src_node.id}"
            edge = KnowledgeEdge(
                id=edge_id,
                source_id=session_node.id,
                target_id=src_node.id,
                kind=EdgeKind.CITED,
            )
            edges.append(edge)
            index.upsert_edge(edge)
            sources_ingested += 1
        except Exception as exc:
            warnings.append(f"Could not ingest source {source.url}: {exc}")

    # Ingest claims from cross_reference_claims in analysis metadata
    claims_ingested = 0
    analysis = session.metadata.get("analysis", {})
    cross_ref_claims: list[CrossReferenceClaim] = []
    try:
        raw_claims = analysis.get("cross_reference_claims", [])
        from cc_deep_research.models.quality import CrossReferenceClaim

        for raw in raw_claims:
            try:
                if isinstance(raw, CrossReferenceClaim):
                    cross_ref_claims.append(raw)
                else:
                    cross_ref_claims.append(CrossReferenceClaim.model_validate(raw))
            except Exception:
                pass
    except Exception:
        pass

    for claim in cross_ref_claims:
        try:
            claim_node, claim_edges = _ingest_claim_page(
                claim, session.session_id, config_path=config_path
            )
            nodes.append(claim_node)
            index.upsert_node(claim_node)
            for edge in claim_edges:
                edges.append(edge)
                index.upsert_edge(edge)
            claims_ingested += 1
        except Exception as exc:
            warnings.append(f"Could not ingest claim: {exc}")

    # Ingest gaps
    gaps_ingested = 0
    raw_gaps = analysis.get("gaps", [])
    for raw_gap in raw_gaps:
        try:
            gap_desc = (raw_gap.get("gap_description") if isinstance(raw_gap, dict) else str(raw_gap)) or ""
            gap_queries = raw_gap.get("suggested_queries", []) if isinstance(raw_gap, dict) else []
            gap_importance = raw_gap.get("importance") if isinstance(raw_gap, dict) else None

            gap_node = _ingest_gap_page(
                gap_desc,
                gap_queries,
                session.session_id,
                gap_importance,
                config_path=config_path,
            )
            nodes.append(gap_node)
            index.upsert_node(gap_node)
            gaps_ingested += 1
        except Exception as exc:
            warnings.append(f"Could not ingest gap: {exc}")

    # Count findings from key_findings
    findings_ingested = 0
    key_findings = analysis.get("key_findings", [])
    findings_ingested = len(key_findings)

    # Write manifest
    try:
        _ingest_manifest(
            session.session_id,
            sources_count=sources_ingested,
            claims_count=claims_ingested,
            findings_count=findings_ingested,
            gaps_count=gaps_ingested,
            config_path=config_path,
        )
    except Exception as exc:
        warnings.append(f"Could not write manifest: {exc}")

    # Append to log
    try:
        _append_log_entry(
            session.session_id,
            f"ingested (sources={sources_ingested} claims={claims_ingested} gaps={gaps_ingested})",
            config_path=config_path,
        )
    except Exception:
        pass

    try:
        index.commit()
        index.close()
    except Exception:
        pass

    return IngestResult(
        session_id=session.session_id,
        nodes_ingested=len(nodes),
        edges_ingested=len(edges),
        sources_ingested=sources_ingested,
        claims_ingested=claims_ingested,
        findings_ingested=findings_ingested,
        gaps_ingested=gaps_ingested,
        warnings=warnings,
    )


class IngestResult:
    """Outcome of an ingest operation."""

    def __init__(
        self,
        session_id: str,
        nodes_ingested: int,
        edges_ingested: int,
        sources_ingested: int,
        claims_ingested: int,
        findings_ingested: int,
        gaps_ingested: int,
        warnings: list[str],
    ) -> None:
        self.session_id = session_id
        self.nodes_ingested = nodes_ingested
        self.edges_ingested = edges_ingested
        self.sources_ingested = sources_ingested
        self.claims_ingested = claims_ingested
        self.findings_ingested = findings_ingested
        self.gaps_ingested = gaps_ingested
        self.warnings = warnings

    def __repr__(self) -> str:
        return (
            f"IngestResult(session_id={self.session_id!r}, "
            f"nodes={self.nodes_ingested}, edges={self.edges_ingested}, "
            f"sources={self.sources_ingested}, claims={self.claims_ingested})"
        )


__all__ = ["IngestResult", "ingest_session"]
