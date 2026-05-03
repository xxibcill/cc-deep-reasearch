"""Claim trace helpers for scripting and QC stages."""

from __future__ import annotations

from cc_deep_research.content_gen.models.research import (
    ClaimTraceEntry,
    ClaimTraceLedger,
    ResearchPack,
    ScriptClaimStatement,
)
from cc_deep_research.content_gen.models.script import ArgumentMap, ScriptingContext
from cc_deep_research.content_gen.models.shared import ClaimTraceStage, ClaimTraceStatus


def build_claim_ledger(
    research_pack: ResearchPack | None,
    argument_map: ArgumentMap | None,
    scripting: ScriptingContext | None,
) -> ClaimTraceLedger:
    """Build a claim ledger from research, argument-map, and script evidence."""
    ledger = ClaimTraceLedger(idea_id=_resolve_idea_id(research_pack, argument_map))
    _add_research_claims(ledger, research_pack)
    _add_argument_claims(ledger, argument_map)
    _add_script_claims(ledger, argument_map, scripting)
    return ledger


def format_research_context(research_pack: ResearchPack | None) -> str:
    """Format a research pack into the compact context passed to scripting."""
    if research_pack is None:
        return ""

    sections: list[str] = []
    if research_pack.findings:
        findings = [finding.finding for finding in research_pack.findings[:5] if finding.finding]
        if findings:
            sections.append("Key findings:\n- " + "\n- ".join(findings))
    if research_pack.claims:
        claims = [claim.claim for claim in research_pack.claims[:5] if claim.claim]
        if claims:
            sections.append("Supported claims:\n- " + "\n- ".join(claims))
    if research_pack.counterpoints:
        counterpoints = [
            counterpoint.counterpoint
            for counterpoint in research_pack.counterpoints[:3]
            if counterpoint.counterpoint
        ]
        if counterpoints:
            sections.append("Counterpoints:\n- " + "\n- ".join(counterpoints))
    if research_pack.evidence_gaps:
        sections.append("Evidence gaps:\n- " + "\n- ".join(research_pack.evidence_gaps[:3]))
    if research_pack.claims_requiring_verification:
        sections.append(
            "Claims requiring verification:\n- "
            + "\n- ".join(research_pack.claims_requiring_verification[:3])
        )
    if research_pack.unsafe_or_uncertain_claims:
        sections.append(
            "Unsafe or uncertain claims:\n- "
            + "\n- ".join(research_pack.unsafe_or_uncertain_claims[:3])
        )

    return "\n\n".join(sections)


def _resolve_idea_id(
    research_pack: ResearchPack | None,
    argument_map: ArgumentMap | None,
) -> str:
    if research_pack and research_pack.idea_id:
        return research_pack.idea_id
    if argument_map and argument_map.idea_id:
        return argument_map.idea_id
    return ""


def _add_research_claims(
    ledger: ClaimTraceLedger,
    research_pack: ResearchPack | None,
) -> None:
    if research_pack is None:
        return

    for claim in research_pack.claims:
        status = ClaimTraceStatus.SUPPORTED if claim.source_ids else ClaimTraceStatus.UNSUPPORTED
        ledger.entries.append(
            ClaimTraceEntry(
                claim_id=claim.claim_id,
                claim=claim.claim,
                status=status,
                source_ids=list(claim.source_ids),
                stage=ClaimTraceStage.RESEARCH_PACK,
                evidence_strength=1.0 if claim.source_ids else 0.0,
            )
        )
        if status == ClaimTraceStatus.UNSUPPORTED:
            ledger.unverified_claims.append(claim.claim_id)

    for claim_text in research_pack.claims_requiring_verification:
        _append_text_claim(ledger, claim_text, ClaimTraceStatus.PENDING)

    for claim_text in research_pack.unsafe_or_uncertain_claims:
        _append_text_claim(ledger, claim_text, ClaimTraceStatus.WEAK)


def _add_argument_claims(
    ledger: ClaimTraceLedger,
    argument_map: ArgumentMap | None,
) -> None:
    if argument_map is None:
        return

    for claim in argument_map.safe_claims:
        status = (
            ClaimTraceStatus.SUPPORTED
            if claim.supporting_proof_ids
            else ClaimTraceStatus.UNSUPPORTED
        )
        entry = _upsert_claim_entry(
            ledger,
            claim_id=claim.claim_id,
            claim_text=claim.claim,
            status=status,
            stage=ClaimTraceStage.ARGUMENT_MAP,
        )
        if claim.supporting_proof_ids:
            entry.notes = _append_note(
                entry.notes,
                "Proof anchors: " + ", ".join(claim.supporting_proof_ids),
            )
        else:
            ledger.unverified_claims.append(claim.claim_id)

    for claim in argument_map.unsafe_claims:
        _upsert_claim_entry(
            ledger,
            claim_id=claim.claim_id,
            claim_text=claim.claim,
            status=ClaimTraceStatus.UNSUPPORTED,
            stage=ClaimTraceStage.ARGUMENT_MAP,
        )
        ledger.unsupported_script_claims.append(claim.claim_id)

    for beat in argument_map.beat_claim_plan:
        for claim_id in beat.claim_ids:
            entry = ledger.get_claim(claim_id)
            if entry is None:
                entry = ClaimTraceEntry(
                    claim_id=claim_id,
                    claim="",
                    status=ClaimTraceStatus.PENDING,
                    stage=ClaimTraceStage.ARGUMENT_MAP,
                )
                ledger.entries.append(entry)
            entry.notes = _append_note(entry.notes, f"Beat: {beat.beat_id}")


def _add_script_claims(
    ledger: ClaimTraceLedger,
    argument_map: ArgumentMap | None,
    scripting: ScriptingContext | None,
) -> None:
    script_text = _extract_script_text(scripting)
    if not script_text:
        return

    lower_script = script_text.lower()
    argument_claim_ids: set[str] = set()
    safe_claims = argument_map.safe_claims if argument_map else []
    for claim in safe_claims:
        argument_claim_ids.add(claim.claim_id)
        if not claim.claim or claim.claim.lower() not in lower_script:
            ledger.dropped_claims.append(claim.claim_id)
            continue
        entry = ledger.get_claim(claim.claim_id)
        if entry is None:
            continue
        _append_script_claim(ledger, entry)

    for entry in list(ledger.entries):
        if entry.claim_id in argument_claim_ids or not entry.claim:
            continue
        if entry.claim.lower() in lower_script:
            ledger.introduced_late_claims.append(entry.claim_id)
            _append_script_claim(ledger, entry)


def _extract_script_text(scripting: ScriptingContext | None) -> str:
    if scripting is None:
        return ""
    if scripting.qc and scripting.qc.final_script:
        return scripting.qc.final_script

    parts: list[str] = [scripting.hook]
    for beat in scripting.beats:
        parts.extend(beat.talking_points)
        parts.extend([beat.hook, beat.cta])
    parts.append(scripting.cta)

    for attr in ("tightened", "draft"):
        legacy_version = getattr(scripting, attr, None)
        content = getattr(legacy_version, "content", "")
        if content:
            parts.append(content)

    return "\n".join(part for part in parts if part)


def _append_script_claim(ledger: ClaimTraceLedger, entry: ClaimTraceEntry) -> None:
    ledger.script_claims.append(
        ScriptClaimStatement(
            claim_id=entry.claim_id,
            claim=entry.claim,
            sourcing_required=entry.status != ClaimTraceStatus.SUPPORTED,
        )
    )
    if entry.status == ClaimTraceStatus.UNSUPPORTED:
        ledger.unsupported_script_claims.append(entry.claim_id)


def _append_text_claim(
    ledger: ClaimTraceLedger,
    claim_text: str,
    status: ClaimTraceStatus,
) -> None:
    if not claim_text:
        return
    claim_id = f"claim_{len(ledger.entries) + 1}"
    ledger.entries.append(
        ClaimTraceEntry(
            claim_id=claim_id,
            claim=claim_text,
            status=status,
            stage=ClaimTraceStage.RESEARCH_PACK,
        )
    )
    if status == ClaimTraceStatus.PENDING:
        ledger.unverified_claims.append(claim_id)
    if status == ClaimTraceStatus.WEAK:
        ledger.weak_claims.append(claim_id)


def _upsert_claim_entry(
    ledger: ClaimTraceLedger,
    *,
    claim_id: str,
    claim_text: str,
    status: ClaimTraceStatus,
    stage: ClaimTraceStage,
) -> ClaimTraceEntry:
    entry = ledger.get_claim(claim_id)
    if entry is not None:
        entry.claim = entry.claim or claim_text
        entry.status = status
        entry.stage = stage
        entry.evidence_strength = 1.0 if status == ClaimTraceStatus.SUPPORTED else 0.0
        return entry

    entry = next((item for item in ledger.entries if item.claim == claim_text), None)
    if entry is not None:
        entry.claim_id = claim_id
        entry.status = status
        entry.stage = stage
        entry.evidence_strength = 1.0 if status == ClaimTraceStatus.SUPPORTED else 0.0
        return entry

    entry = ClaimTraceEntry(
        claim_id=claim_id,
        claim=claim_text,
        status=status,
        stage=stage,
        evidence_strength=1.0 if status == ClaimTraceStatus.SUPPORTED else 0.0,
    )
    ledger.entries.append(entry)
    return entry


def _append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}; {note}"
