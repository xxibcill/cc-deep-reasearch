from __future__ import annotations

import ast
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_MODELS_PATH = REPO_ROOT / "src/cc_deep_research/content_gen/models.py"
FRONTEND_TYPES_PATH = REPO_ROOT / "dashboard/src/types/content-gen.ts"


def _load_backend_pipeline_stages() -> list[str]:
    module = ast.parse(BACKEND_MODELS_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue

        if not any(isinstance(target, ast.Name) and target.id == "PIPELINE_STAGES" for target in targets):
            continue
        if not isinstance(value, ast.List):
            raise AssertionError("PIPELINE_STAGES is no longer a list literal")
        return [
            elt.value
            for elt in value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
    raise AssertionError("PIPELINE_STAGES assignment not found")


def _load_frontend_pipeline_stages() -> list[str]:
    text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"export const PIPELINE_STAGE_ORDER: PipelineStageName\[\] = \[(.*?)\];",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("PIPELINE_STAGE_ORDER declaration not found")
    return re.findall(r"'([^']+)'", match.group(1))


def test_dashboard_pipeline_stage_order_matches_backend_contract() -> None:
    """The dashboard stage list should stay in lockstep with backend pipeline ordering."""
    assert _load_frontend_pipeline_stages() == _load_backend_pipeline_stages()
