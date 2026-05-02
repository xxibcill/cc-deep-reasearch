"""Shared service composition for content-gen route handlers.

All route handlers should receive their dependencies through closures
captured at registration time, rather than constructing services inline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cc_deep_research.config import Config
from cc_deep_research.content_gen.backlog_api_service import BacklogApiService
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.brief_api_service import BriefApiService
from cc_deep_research.content_gen.brief_service import BriefService
from cc_deep_research.content_gen.maintenance_api_service import MaintenanceApiService
from cc_deep_research.content_gen.pipeline_run_service import PipelineRunService
from cc_deep_research.content_gen.publish_queue_audit_service import PublishQueueAuditService
from cc_deep_research.content_gen.scripting_api_service import ScriptingApiService
from cc_deep_research.content_gen.storage import AuditStore
from cc_deep_research.event_router import EventRouter
from cc_deep_research.content_gen.progress import PipelineRunJobRegistry

if TYPE_CHECKING:
    from cc_deep_research.content_gen.strategy_api_service import StrategyApiService


class ContentGenServices:
    """Composed content-gen service graph for route handler consumption.

    All services are constructed once and shared across route handlers.
    Individual services accept optional overrides for testing.
    """

    def __init__(
        self,
        config: Config,
        event_router: EventRouter,
        job_registry: PipelineRunJobRegistry,
        *,
        pipeline_service: PipelineRunService | None = None,
        backlog_service: BacklogService | None = None,
        audit_store: AuditStore | None = None,
        brief_service: BriefService | None = None,
        scripting_api_service: ScriptingApiService | None = None,
        strategy_api_service: StrategyApiService | None = None,
        publish_queue_audit_service: PublishQueueAuditService | None = None,
    ) -> None:
        self._config = config
        self._event_router = event_router
        self._job_registry = job_registry

        # Audit store shared across services
        self._audit_store = audit_store or AuditStore(config=config)

        # Pipeline service
        self._pipeline_service = pipeline_service or PipelineRunService(
            job_registry=job_registry,
            event_router=event_router,
        )

        # Backlog service + API service
        self._backlog_service = backlog_service or BacklogService(config)
        self._backlog_service.set_audit_store(self._audit_store)
        self._backlog_api_service = BacklogApiService(
            backlog_service=self._backlog_service,
            pipeline_service=self._pipeline_service,
        )

        # Brief service + API service
        self._brief_service = brief_service or BriefService(config)
        self._brief_service.set_audit_store(self._audit_store)
        self._brief_api_service = BriefApiService(
            brief_service=self._brief_service,
            audit_store=self._audit_store,
        )

        # Scripting service
        self._scripting_api_service = scripting_api_service or ScriptingApiService()

        # Strategy service
        if strategy_api_service is not None:
            self._strategy_api_service = strategy_api_service
        else:
            from cc_deep_research.content_gen.strategy_api_service import StrategyApiService

            self._strategy_api_service = StrategyApiService()

        # Publish queue audit service
        self._publish_queue_audit_service = (
            publish_queue_audit_service or PublishQueueAuditService()
        )

        # Maintenance API service
        from cc_deep_research.content_gen.maintenance_api_service import MaintenanceApiService

        self._maintenance_api_service = MaintenanceApiService()

    @property
    def config(self) -> Config:
        return self._config

    @property
    def pipeline_service(self) -> PipelineRunService:
        return self._pipeline_service

    @property
    def backlog_api_service(self) -> BacklogApiService:
        return self._backlog_api_service

    @property
    def backlog_service(self) -> BacklogService:
        return self._backlog_service

    @property
    def brief_api_service(self) -> BriefApiService:
        return self._brief_api_service

    @property
    def brief_service(self) -> BriefService:
        return self._brief_service

    @property
    def audit_store(self) -> AuditStore:
        return self._audit_store

    @property
    def scripting_api_service(self) -> ScriptingApiService:
        return self._scripting_api_service

    @property
    def strategy_api_service(self) -> StrategyApiService:
        return self._strategy_api_service

    @property
    def publish_queue_audit_service(self) -> PublishQueueAuditService:
        return self._publish_queue_audit_service

    @property
    def maintenance_api_service(self) -> MaintenanceApiService:
        return self._maintenance_api_service


def build_content_gen_services(
    config: Config,
    event_router: EventRouter,
    job_registry: PipelineRunJobRegistry,
    *,
    pipeline_service: PipelineRunService | None = None,
    backlog_service: BacklogService | None = None,
    audit_store: AuditStore | None = None,
    brief_service: BriefService | None = None,
    scripting_api_service: ScriptingApiService | None = None,
    strategy_api_service: StrategyApiService | None = None,
    publish_queue_audit_service: PublishQueueAuditService | None = None,
) -> ContentGenServices:
    """Build a ContentGenServices instance with composed dependencies.

    All keyword arguments are optional overrides for testing. When omitted,
    services are constructed from the provided config.
    """
    return ContentGenServices(
        config=config,
        event_router=event_router,
        job_registry=job_registry,
        pipeline_service=pipeline_service,
        backlog_service=backlog_service,
        audit_store=audit_store,
        brief_service=brief_service,
        scripting_api_service=scripting_api_service,
        strategy_api_service=strategy_api_service,
        publish_queue_audit_service=publish_queue_audit_service,
    )
