"""Ingestion quality gates for validating records before graph mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from cc_deep_research.knowledge import KnowledgeNode, NodeKind


class IngestCheck(StrEnum):
    """Types of quality checks applied during ingestion."""

    REQUIRED_FIELDS = "required_fields"
    SOURCE_PROVENANCE = "source_provenance"
    NORMALIZED_TEXT = "normalized_text"
    CLAIM_SHAPE = "claim_shape"
    DUPLICATE_DENSITY = "duplicate_density"


@dataclass
class CheckResult:
    """Result of a single ingestion quality check."""

    check: IngestCheck
    passed: bool
    message: str


@dataclass
class IngestValidationResult:
    """Result of validating a single record for ingestion."""

    valid: bool
    record_id: str
    check_results: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejection_reason: str | None = None


@dataclass
class BatchValidationResult:
    """Result of validating a batch of records before ingestion."""

    total: int = 0
    accepted: int = 0
    warned: int = 0
    rejected: int = 0
    results: list[IngestValidationResult] = field(default_factory=list)


def validate_record(node: KnowledgeNode) -> IngestValidationResult:
    """Validate a single node for ingestion.

    Checks:
    - REQUIRED_FIELDS: id, kind, label are present and non-empty
    - NORMALIZED_TEXT: label has actual content
    - CLAIM_SHAPE: claims have minimum useful content (10+ chars, word diversity)
    - SOURCE_PROVENANCE: claims have source_ids or session_ids backing them
    """
    record_id = node.id
    check_results: list[CheckResult] = []
    warnings: list[str] = []
    rejection_reason: str | None = None

    # REQUIRED_FIELDS check
    if not node.id or not node.id.strip():
        check_results.append(CheckResult(
            check=IngestCheck.REQUIRED_FIELDS,
            passed=False,
            message="Node id is required and non-empty",
        ))
        rejection_reason = "Missing required field: id"
    elif node.kind is None or not isinstance(node.kind, NodeKind):
        check_results.append(CheckResult(
            check=IngestCheck.REQUIRED_FIELDS,
            passed=False,
            message="Node kind must be a valid NodeKind",
        ))
        rejection_reason = "Missing required field: kind"
    elif not node.label or not node.label.strip():
        check_results.append(CheckResult(
            check=IngestCheck.REQUIRED_FIELDS,
            passed=False,
            message="Node label is required and non-empty",
        ))
        rejection_reason = "Missing required field: label"
    else:
        check_results.append(CheckResult(
            check=IngestCheck.REQUIRED_FIELDS,
            passed=True,
            message="All required fields present",
        ))

    # NORMALIZED_TEXT check (only if basic fields passed)
    if node.label:
        stripped = node.label.strip()
        if not stripped:
            check_results.append(CheckResult(
                check=IngestCheck.NORMALIZED_TEXT,
                passed=False,
                message="Label is only whitespace",
            ))
            if not rejection_reason:
                rejection_reason = "Label is empty or whitespace only"
        elif len(stripped) < 2:
            check_results.append(CheckResult(
                check=IngestCheck.NORMALIZED_TEXT,
                passed=False,
                message="Label is too short to be meaningful",
            ))
            if not rejection_reason:
                rejection_reason = "Label too short"
        else:
            check_results.append(CheckResult(
                check=IngestCheck.NORMALIZED_TEXT,
                passed=True,
                message="Label has normalized content",
            ))

    # CLAIM_SHAPE check
    if node.kind == NodeKind.CLAIM:
        label = node.label or ""
        words = label.split()
        word_count = len([w for w in words if w.strip()])
        unique_word_ratio = len(set(w.lower() for w in words)) / max(len(words), 1)

        if len(label) < 10:
            check_results.append(CheckResult(
                check=IngestCheck.CLAIM_SHAPE,
                passed=False,
                message=f"Claim text too short ({len(label)} chars, minimum 10)",
            ))
            if not rejection_reason:
                rejection_reason = "Claim text too short"
        elif word_count < 3:
            check_results.append(CheckResult(
                check=IngestCheck.CLAIM_SHAPE,
                passed=False,
                message=f"Claim has too few words ({word_count}, minimum 3)",
            ))
            if not rejection_reason:
                rejection_reason = "Claim has too few words"
        elif unique_word_ratio < 0.5 and len(words) > 3:
            check_results.append(CheckResult(
                check=IngestCheck.CLAIM_SHAPE,
                passed=False,
                message=f"Claim lacks word diversity (ratio {unique_word_ratio:.2f})",
            ))
            if not rejection_reason:
                rejection_reason = "Claim lacks word diversity"
        else:
            check_results.append(CheckResult(
                check=IngestCheck.CLAIM_SHAPE,
                passed=True,
                message="Claim has sufficient shape and diversity",
            ))
    else:
        check_results.append(CheckResult(
            check=IngestCheck.CLAIM_SHAPE,
            passed=True,
            message="Not a claim node",
        ))

    # SOURCE_PROVENANCE check for claims
    if node.kind == NodeKind.CLAIM:
        source_ids = node.properties.get("source_ids", [])
        session_ids = node.properties.get("session_ids", [])
        has_provenance = bool(source_ids) or bool(session_ids)
        has_confidence = node.properties.get("confidence", 0) >= 0.5

        if not has_provenance and not has_confidence:
            check_results.append(CheckResult(
                check=IngestCheck.SOURCE_PROVENANCE,
                passed=False,
                message="Claim lacks source_ids and has low confidence",
            ))
            if not rejection_reason:
                rejection_reason = "Claim missing source provenance and low confidence"
        else:
            check_results.append(CheckResult(
                check=IngestCheck.SOURCE_PROVENANCE,
                passed=True,
                message="Claim has source or confidence backing",
            ))
    else:
        check_results.append(CheckResult(
            check=IngestCheck.SOURCE_PROVENANCE,
            passed=True,
            message="Not a claim node",
        ))

    valid = rejection_reason is None

    return IngestValidationResult(
        valid=valid,
        record_id=record_id,
        check_results=check_results,
        warnings=warnings,
        rejection_reason=rejection_reason,
    )


def validate_batch(nodes: list[KnowledgeNode]) -> BatchValidationResult:
    """Validate a batch of nodes before ingestion.

    Includes DUPLICATE_DENSITY check across the batch.
    """
    results: list[IngestValidationResult] = []
    duplicate_warnings: list[str] = []

    # Check for duplicate density across the batch
    # Only warn when multiple nodes share the same (label, kind) pair
    if len(nodes) > 1:
        label_kind_counts: dict[tuple[str, str], int] = {}
        for node in nodes:
            key = (node.label.lower().strip(), node.kind.value)
            label_kind_counts[key] = label_kind_counts.get(key, 0) + 1

        for (label, kind), count in label_kind_counts.items():
            # Only warn when same (label, kind) appears more than once
            if count > 1:
                duplicate_warnings.append(
                    f"Duplicate density: {count} nodes with label '{label}' (kind={kind})"
                )

    accepted = 0
    warned = 0
    rejected = 0

    for node in nodes:
        result = validate_record(node)
        result.warnings.extend(duplicate_warnings)

        if result.valid:
            if duplicate_warnings:
                warned += 1
            else:
                accepted += 1
            if duplicate_warnings:
                result.warnings.append(f"Batch duplicate density: {len(duplicate_warnings)} warning(s)")
        else:
            rejected += 1

        results.append(result)

    return BatchValidationResult(
        total=len(nodes),
        accepted=accepted,
        warned=warned,
        rejected=rejected,
        results=results,
    )


class IngestGate:
    """Service for validating records before ingestion."""

    def validate_nodes(self, nodes: list[KnowledgeNode]) -> BatchValidationResult:
        """Validate a list of nodes before ingestion."""
        return validate_batch(nodes)

    def validate_session_for_ingest(self, session) -> BatchValidationResult:
        """Validate what would be ingested from a research session.

        Simulates the node creation from ingest_session without writing to graph.
        Returns BatchValidationResult for the nodes that would be created.
        """
        from cc_deep_research.knowledge import KnowledgeNode as KNode

        nodes_to_validate: list[KNode] = []

        # Session node
        session_node = KNode(
            id=f"session:{session.session_id}",
            kind=NodeKind.SESSION,
            label=session.query or "Untitled session",
            properties={
                "depth": session.depth.value if session.depth else None,
                "source_count": session.total_sources or 0,
            },
        )
        nodes_to_validate.append(session_node)

        # Source nodes
        for source in (session.sources or []):
            from urllib.parse import urlparse
            url_path = urlparse(source.url).path.strip("/")
            stem = url_path.split("/")[-1] or urlparse(source.url).netloc
            src_node = KNode(
                id=f"source:{stem}",
                kind=NodeKind.SOURCE,
                label=source.title or source.url,
                properties={
                    "url": source.url,
                    "score": source.score,
                },
            )
            nodes_to_validate.append(src_node)

        # Claim nodes from cross_reference_claims
        analysis = session.metadata.get("analysis", {}) or {}
        cross_ref_claims = analysis.get("cross_reference_claims", []) or []
        for raw_claim in cross_ref_claims:
            claim_text = raw_claim.claim if hasattr(raw_claim, "claim") else str(raw_claim.get("claim", ""))
            if len(claim_text) > 60:
                claim_text = claim_text[:60]
            claim_node = KNode(
                id=f"claim:{claim_text[:40].lower().replace(' ', '-')}",
                kind=NodeKind.CLAIM,
                label=claim_text,
                properties={
                    "confidence": getattr(raw_claim, "confidence", 0.5) if hasattr(raw_claim, "confidence") else 0.5,
                    "freshness": getattr(raw_claim, "freshness", None),
                },
            )
            nodes_to_validate.append(claim_node)

        # Gap nodes
        raw_gaps = analysis.get("gaps", []) or []
        for raw_gap in raw_gaps:
            gap_desc = raw_gap.get("gap_description", "") if isinstance(raw_gap, dict) else str(raw_gap)
            if gap_desc:
                gap_node = KNode(
                    id=f"gap:{gap_desc[:40].lower().replace(' ', '-')}",
                    kind=NodeKind.GAP,
                    label=gap_desc[:80],
                    properties={"importance": raw_gap.get("importance") if isinstance(raw_gap, dict) else None},
                )
                nodes_to_validate.append(gap_node)

        return validate_batch(nodes_to_validate)

    def dry_run_ingest(self, session) -> BatchValidationResult:
        """Alias for validate_session_for_ingest for API compatibility."""
        return self.validate_session_for_ingest(session)


__all__ = [
    "BatchValidationResult",
    "CheckResult",
    "IngestCheck",
    "IngestGate",
    "IngestValidationResult",
    "validate_batch",
    "validate_record",
]
