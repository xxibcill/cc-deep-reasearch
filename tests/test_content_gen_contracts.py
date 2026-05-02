"""Contract tests for content-gen prompt, parser, and model alignment.

These tests validate that:
1. All CONTENT_GEN_STAGE_CONTRACTS entries are well-formed.
2. Prompt modules that declare CONTRACT_VERSION match the registry.
3. Parser functions accept valid fixtures and reject malformed ones.
4. Required output fields from the registry are accepted by parsers and models.

Run without LLM credentials:
    uv run pytest tests/test_content_gen_contracts.py -x
    uv run mypy src/cc_deep_research/content_gen/models src/cc_deep_research/content_gen/agents
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import pytest

from cc_deep_research.content_gen.models.contracts import CONTENT_GEN_STAGE_CONTRACTS
from cc_deep_research.content_gen.models.contracts import ContentGenStageContract
from tests.helpers.fixture_loader import load_text_fixture


# ---------------------------------------------------------------------------
# Registry Iteration Tests
# ---------------------------------------------------------------------------

class TestContractRegistry:
    """Validate CONTENT_GEN_STAGE_CONTRACTS structure and metadata."""

    def test_all_contracts_have_required_fields_or_graceful(self) -> None:
        """Every contract must have non-empty required_fields, or a graceful failure_mode."""
        for stage_name, contract in CONTENT_GEN_STAGE_CONTRACTS.items():
            has_required = bool(contract.required_fields)
            is_graceful = contract.failure_mode in ("tolerant", "human_gated")
            assert has_required or is_graceful, (
                f"{stage_name}: required_fields is empty and failure_mode is not "
                f"'tolerant' or 'human_gated'"
            )

    def test_all_contracts_reference_valid_modules(self) -> None:
        """prompt_module and parser_location must reference real paths."""
        content_gen_root = Path("src/cc_deep_research/content_gen")
        for stage_name, contract in CONTENT_GEN_STAGE_CONTRACTS.items():
            prompt_path = content_gen_root / contract.prompt_module
            assert prompt_path.exists(), f"{stage_name}: prompt_module not found: {contract.prompt_module}"

            # parser_location format: "agents/X.py::func_name" or "agents/X.py (JSON first, legacy fallback)"
            parser_path_str = contract.parser_location.split("::")[0].split(" (")[0]
            parser_path = content_gen_root / parser_path_str
            assert parser_path.exists(), f"{stage_name}: parser_location not found: {parser_path_str}"

    def test_all_contracts_have_valid_failure_mode(self) -> None:
        """failure_mode must be one of the defined literals."""
        valid_modes = {"fail_fast", "tolerant", "human_gated"}
        for stage_name, contract in CONTENT_GEN_STAGE_CONTRACTS.items():
            assert contract.failure_mode in valid_modes, (
                f"{stage_name}: unknown failure_mode '{contract.failure_mode}'"
            )

    def test_contract_versions_are_semver_like(self) -> None:
        """Contract versions should follow semver-style numbering."""
        for stage_name, contract in CONTENT_GEN_STAGE_CONTRACTS.items():
            assert re.match(r"\d+\.\d+\.\d+", contract.contract_version), (
                f"{stage_name}: contract_version '{contract.contract_version}' is not semver"
            )


# ---------------------------------------------------------------------------
# Version Consistency Tests
# ---------------------------------------------------------------------------

class TestPromptVersionConsistency:
    """Verify prompt modules declare CONTRACT_VERSION matching the registry."""

    PROMPT_MODULE_ROOTS = [
        Path("src/cc_deep_research/content_gen/prompts"),
    ]

    def _discover_prompt_modules_with_version(self):
        """Yield (stage_name, prompt_module_path, declared_version)."""
        for root in self.PROMPT_MODULE_ROOTS:
            for py_file in root.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    continue
                if hasattr(module, "CONTRACT_VERSION"):
                    # Match the prompt module to its contract entry
                    # by inferring stage_name from the filename
                    stage_name = py_file.stem.replace("_", "_")
                    yield stage_name, py_file, module.CONTRACT_VERSION

    def test_prompt_versions_match_registry(self) -> None:
        """Prompt CONTRACT_VERSION should match the registry contract_version.

        If a prompt module declares CONTRACT_VERSION but the registry entry
        has a different version, the test fails — prompting a coordinated update.
        """
        mismatches: list[tuple[str, str, str, str]] = []  # (stage, prompt_ver, registry_ver)

        for stage_name, prompt_path, prompt_version in self._discover_prompt_modules_with_version():
            # Look up by prompt_module path relative to content_gen root
            rel_path = str(prompt_path.relative_to(Path("src/cc_deep_research/content_gen")))
            for registry_stage, contract in CONTENT_GEN_STAGE_CONTRACTS.items():
                if contract.prompt_module == rel_path:
                    if prompt_version != contract.contract_version:
                        mismatches.append((registry_stage, prompt_version, contract.contract_version))
                    break

        if mismatches:
            msg = "\n".join(
                f"  {stage}: prompt={prompt_ver} registry={registry_ver}"
                for stage, prompt_ver, registry_ver in mismatches
            )
            pytest.fail(f"Version mismatches between prompt modules and registry:\n{msg}")


# ---------------------------------------------------------------------------
# Parser Fixture Tests
# ---------------------------------------------------------------------------

class TestBacklogParserFixtures:
    """Validate backlog agent parser behavior with fixtures."""

    def test_backlog_happy_fixture_parses_correctly(self) -> None:
        """Happy-path backlog output produces valid BacklogItems."""
        from cc_deep_research.content_gen.agents.backlog import _parse_backlog_items

        text = load_text_fixture("content_gen_backlog_happy.txt")
        items = _parse_backlog_items(text)

        assert len(items) == 2
        assert items[0].title == "The 10-minute weekly finance review that stops founder cash surprises"
        assert items[0].category == "evergreen"
        assert items[1].category == "authority-building"

    def test_backlog_malformed_fixture_gracefully_handles_missing_title(self) -> None:
        """Malformed backlog output skips blocks without required 'title' field."""
        from cc_deep_research.content_gen.agents.backlog import _parse_backlog_items

        text = load_text_fixture("content_gen_backlog_malformed.txt")
        items = _parse_backlog_items(text)

        # Second block has no title — should be skipped
        assert len(items) == 1
        assert items[0].category == "evergreen"


class TestResearchPackParserFixtures:
    """Validate research pack agent parser behavior with fixtures."""

    def test_research_pack_happy_fixture_parses_correctly(self) -> None:
        """Happy-path research pack produces valid ResearchPack."""
        from cc_deep_research.content_gen.agents.research_pack import _parse_research_pack

        text = load_text_fixture("content_gen_research_pack_happy.txt")
        pack = _parse_research_pack(text, idea_id="test-001", angle_id="angle-001")

        assert pack.idea_id == "test-001"
        assert len(pack.findings) == 6
        assert len(pack.claims) == 4
        assert len(pack.counterpoints) == 1
        assert len(pack.uncertainty_flags) == 2
        assert pack.research_stop_reason == "Enough evidence to build a practical teardown without hard performance claims"

    def test_research_pack_sparse_fixture_parses_without_errors(self) -> None:
        """Sparse but valid research pack parses without raising."""
        from cc_deep_research.content_gen.agents.research_pack import _parse_research_pack

        text = load_text_fixture("content_gen_research_pack_sparse.txt")
        pack = _parse_research_pack(text, idea_id="test-002", angle_id="angle-002")

        # Tolerant parser — should not raise, may have fewer items
        assert pack.idea_id == "test-002"
        assert len(pack.findings) == 1
        assert pack.assets_needed == []  # Not present in sparse fixture


class TestArgumentMapParserFixtures:
    """Validate argument map agent parser behavior with fixtures."""

    def _load_argument_map_fixtures(self) -> tuple[str, str]:
        """Load argument map happy and malformed fixtures."""
        happy = load_text_fixture("content_gen_argument_map_happy.txt")
        malformed = load_text_fixture("content_gen_argument_map_malformed.txt")
        return happy, malformed

    def test_argument_map_happy_fixture_parses_correctly(self) -> None:
        """Happy-path argument map output produces valid ArgumentMap."""
        from cc_deep_research.content_gen.agents.argument_map import _parse_argument_map

        happy, _ = self._load_argument_map_fixtures()
        result = _parse_argument_map(happy, idea_id="idea-001", angle_id="angle-001")

        assert result.idea_id == "idea-001"
        assert result.angle_id == "angle-001"
        assert result.thesis != ""
        assert result.core_mechanism != ""
        assert len(result.proof_anchors) >= 1
        assert len(result.safe_claims) >= 1

    def test_argument_map_malformed_fixture_rejects_missing_thesis(self) -> None:
        """Argument map missing required 'thesis' field raises ValueError."""
        from cc_deep_research.content_gen.agents.argument_map import _parse_argument_map

        _, malformed = self._load_argument_map_fixtures()
        with pytest.raises(ValueError, match="missing required field 'thesis'"):
            _parse_argument_map(malformed, idea_id="idea-002", angle_id="angle-002")


class TestScriptingParserFixtures:
    """Validate scripting agent parser behavior with fixtures."""

    def test_scripting_choose_structure_happy(self) -> None:
        """Happy-path scripting choose_structure output parses correctly."""
        from cc_deep_research.content_gen.agents.scripting import (
            _extract_beat_list,
            _extract_field,
        )

        text = load_text_fixture("content_gen_scripting_choose_structure_happy.txt")

        chosen = _extract_field(text, "Chosen Structure")
        assert chosen == "Contrarian reveal"

        beats = _extract_beat_list(text)
        assert len(beats) == 5
        assert "Hook: Call out the pricing mistake buyers spot first" in beats[0]

    def test_scripting_choose_structure_malformed_missing_beats(self) -> None:
        """Malformed scripting output with no beat list returns empty list."""
        from cc_deep_research.content_gen.agents.scripting import _extract_beat_list

        text = load_text_fixture("content_gen_scripting_choose_structure_malformed.txt")
        beats = _extract_beat_list(text)

        # Malformed fixture has no numbered beats — should return empty
        assert beats == []


class TestQCOutputFixtures:
    """Validate QC output parser behavior."""

    def test_qc_happy_fixture_contains_required_checks(self) -> None:
        """Happy QC output fixture has parseable Pass/Fail checks."""
        from cc_deep_research.content_gen.agents.scripting import _extract_qc_checks

        text = load_text_fixture("content_gen_qc_happy.txt")
        checks = _extract_qc_checks(text)

        assert len(checks) >= 1
        # At least one check should be parseable
        assert any(hasattr(c, "passed") for c in checks)

    def test_qc_sparse_fixture_does_not_raise(self) -> None:
        """Sparse QC fixture parses without errors."""
        from cc_deep_research.content_gen.agents.scripting import _extract_qc_checks

        text = load_text_fixture("content_gen_qc_sparse.txt")
        checks = _extract_qc_checks(text)

        # Sparse fixture has no parseable checks — should return empty list
        assert checks == []


# ---------------------------------------------------------------------------
# Required Fields Tests (Registry Contract vs Parser)
# ---------------------------------------------------------------------------

class TestRequiredFieldsContract:
    """Verify required_fields from registry are parseable from fixtures."""

    @pytest.mark.parametrize(
        "stage_name",
        [
            "build_backlog",
            "score_ideas",
            "generate_angles",
            "build_research_pack",
            "build_argument_map",
            "run_scripting",
        ],
    )
    def test_required_fields_are_parseable(self, stage_name: str) -> None:
        """Required fields declared in contract must be extractable from valid fixtures.

        For each stage, the fixture that exercises it should contain the required
        fields so the parser can find them. This guards against required fields
        that are documented but not actually emitted by the prompt.
        """
        contract = CONTENT_GEN_STAGE_CONTRACTS.get(stage_name)
        assert contract is not None, f"No contract for stage: {stage_name}"

        fixture_map = {
            "build_backlog": "content_gen_backlog_happy.txt",
            "score_ideas": None,  # Score ideas uses structured blocks — tested separately
            "generate_angles": "content_gen_angle_happy.txt",
            "build_research_pack": "content_gen_research_pack_happy.txt",
            "build_argument_map": "content_gen_argument_map_happy.txt",
            "run_scripting": "content_gen_scripting_choose_structure_happy.txt",
        }

        fixture_name = fixture_map.get(stage_name)
        if fixture_name is None:
            pytest.skip(f"No fixture mapped for {stage_name}")

        text = load_text_fixture(fixture_name)
        for field in contract.required_fields:
            # idea_id and angle_id are pipeline-level identifiers assigned before
            # the stage runs — the prompt never emits these. Skip them.
            if field in ("idea_id", "angle_id"):
                continue
            # Check the field appears in the fixture in some form
            # (either as "Field Name: value" or as a section header)
            field_pattern = re.compile(rf"{re.escape(field)}:", re.IGNORECASE)
            assert field_pattern.search(text), (
                f"Stage '{stage_name}': required field '{field}' not found in fixture '{fixture_name}'"
            )


# ---------------------------------------------------------------------------
# Negative Fixtures — Missing / Renamed Required Fields
# ---------------------------------------------------------------------------

class TestNegativeFixtures:
    """Parser behavior on malformed or incomplete outputs."""

    def test_backlog_rejects_block_without_title(self) -> None:
        """A backlog block missing 'title' is skipped by _parse_backlog_items."""
        from cc_deep_research.content_gen.agents.backlog import _parse_backlog_items

        # Block with no title, just category
        text = "---\ncategory: authority-building\nproblem: vague\n---"
        items = _parse_backlog_items(text)
        assert len(items) == 0  # Title is required; block is dropped

    def test_argument_map_rejects_missing_proof_anchor(self) -> None:
        """Argument map without any proof anchors raises ValueError."""
        from cc_deep_research.content_gen.agents.argument_map import _parse_argument_map

        text = (
            "thesis: Pricing pages confuse buyers with too many choices\n"
            "core_mechanism: Anchoring changes perceived value before feature inspection\n"
            "proof_anchors:\n"
            # Intentionally empty proof_anchors section
        )
        with pytest.raises(ValueError, match="missing at least one proof anchor"):
            _parse_argument_map(text, idea_id="x", angle_id="y")

    def test_research_pack_tolerates_empty_sections(self) -> None:
        """Research pack parser tolerates empty optional sections."""
        from cc_deep_research.content_gen.agents.research_pack import _parse_research_pack

        text = (
            "findings:\n"
            "---\n"
            "claims:\n"
            "counterpoints:\n"
            "uncertainty_flags:\n"
            "research_stop_reason: Done\n"
        )
        pack = _parse_research_pack(text, idea_id="x", angle_id="y")
        assert pack.findings == []
        assert pack.claims == []
        assert pack.uncertainty_flags == []
        assert pack.research_stop_reason == "Done"


# ---------------------------------------------------------------------------
# Contract Update Documentation Test
# ---------------------------------------------------------------------------

class TestContractUpdateDocumentation:
    """Verify that the contract update workflow is documented."""

    def test_prompt_modules_have_parser_expectations_documented(self) -> None:
        """Prompt modules that have CONTRACT_VERSION and are in CONTENT_GEN_STAGE_CONTRACTS should have parser notes.

        JSON-only output prompts (backlog_triage, execution_brief, backlog_chat, next_action,
        brief_assistant) are exempt from the "Parser expectations" requirement because
        they output structured JSON rather than text blocks.
        """
        prompts_root = Path("src/cc_deep_research/content_gen/prompts")
        # Prompt modules that output JSON only — no text-block parser expectations
        json_only_modules = {
            "backlog_triage.py",
            "execution_brief.py",
            "backlog_chat.py",
            "next_action.py",
            "brief_assistant.py",
        }
        documented = []
        undocumented = []

        for py_file in prompts_root.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            if py_file.name in json_only_modules:
                continue
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception:
                continue

            if hasattr(module, "CONTRACT_VERSION"):
                # Check for parser expectations in the docstring
                doc = inspect.getdoc(module)
                has_parser_notes = doc is not None and "Parser expectations" in doc
                if has_parser_notes:
                    documented.append(py_file.name)
                else:
                    undocumented.append(py_file.name)

        assert len(undocumented) == 0, (
            f"Prompt modules with CONTRACT_VERSION missing 'Parser expectations' docs: {undocumented}"
        )

    def test_all_contracts_have_format_notes(self) -> None:
        """Every contract in CONTENT_GEN_STAGE_CONTRACTS should have non-empty format_notes."""
        for stage_name, contract in CONTENT_GEN_STAGE_CONTRACTS.items():
            assert contract.format_notes, f"{stage_name}: format_notes is empty or missing"