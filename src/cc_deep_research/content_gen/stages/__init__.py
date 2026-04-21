"""Per-stage orchestrators for the content generation pipeline.

This subpackage contains per-stage orchestrator classes that handle
individual pipeline stages. The ContentGenPipeline coordinates these stages.
"""

from __future__ import annotations

from .angle import AngleStageOrchestrator
from .argument_map import ArgumentMapStageOrchestrator
from .backlog import BacklogStageOrchestrator
from .base import BaseStageOrchestrator
from .opportunity import OpportunityStageOrchestrator
from .packaging import PackagingStageOrchestrator
from .production import ProductionStageOrchestrator
from .publish import PublishStageOrchestrator
from .qc import QCStageOrchestrator
from .research import ResearchStageOrchestrator
from .scripting import ScriptingStageOrchestrator
from .strategy import StrategyStageOrchestrator
from .visual import VisualStageOrchestrator

__all__ = [
    "AngleStageOrchestrator",
    "ArgumentMapStageOrchestrator",
    "BacklogStageOrchestrator",
    "BaseStageOrchestrator",
    "OpportunityStageOrchestrator",
    "PackagingStageOrchestrator",
    "ProductionStageOrchestrator",
    "PublishStageOrchestrator",
    "QCStageOrchestrator",
    "ResearchStageOrchestrator",
    "ScriptingStageOrchestrator",
    "StrategyStageOrchestrator",
    "VisualStageOrchestrator",
]
