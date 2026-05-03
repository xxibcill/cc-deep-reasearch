"""Knowledge graph HTTP API routes for dashboard integration."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from cc_deep_research.knowledge import (
    NodeKind,
)
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.ingest import ingest_session
from cc_deep_research.knowledge.planning_integration import KnowledgePlanningService
from cc_deep_research.knowledge.vault import (
    init_vault,
    vault_root,
    wiki_index_path,
)
from cc_deep_research.session_store import SessionStore, get_default_session_dir


def _open_graph_index(config_path: Path | None = None) -> GraphIndex | None:
    """Open the graph index if the vault exists."""
    from cc_deep_research.knowledge.vault import graph_sqlite_path

    vault = vault_root(config_path)
    if not vault.exists():
        return None

    db_path = graph_sqlite_path(config_path)
    if not db_path.exists():
        return None

    return GraphIndex(db_path)


def _graph_to_summary(index: GraphIndex) -> dict:
    """Build a summary of the graph for the dashboard."""
    nodes = index.all_nodes()
    edges = index.all_edges()

    nodes_by_kind: dict[str, int] = {}
    for node in nodes:
        kind = node.kind.value
        nodes_by_kind[kind] = nodes_by_kind.get(kind, 0) + 1

    edges_by_kind: dict[str, int] = {}
    for edge in edges:
        kind = edge.kind.value
        edges_by_kind[kind] = edges_by_kind.get(kind, 0) + 1

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes_by_kind": nodes_by_kind,
        "edges_by_kind": edges_by_kind,
    }


def register_knowledge_routes(app: FastAPI) -> None:
    """Register knowledge graph API routes.

    Args:
        app: The FastAPI application instance.
    """

    @app.get("/api/knowledge/summary")
    async def get_knowledge_graph_summary() -> JSONResponse:
        """Get a summary of the knowledge graph."""
        index = _open_graph_index()
        if index is None:
            return JSONResponse(
                content={
                    "total_nodes": 0,
                    "total_edges": 0,
                    "nodes_by_kind": {},
                    "edges_by_kind": {},
                    "vault_initialized": False,
                },
            )

        summary = _graph_to_summary(index)
        summary["vault_initialized"] = True
        return JSONResponse(content=summary)

    @app.get("/api/knowledge/nodes/{node_id}")
    async def get_knowledge_node(node_id: str) -> JSONResponse:
        """Get details for a specific node."""
        index = _open_graph_index()
        if index is None:
            return JSONResponse(
                content={"error": "Vault not initialized"},
                status_code=404,
            )

        node = index.node(node_id)
        if node is None:
            return JSONResponse(
                content={"error": f"Node not found: {node_id}"},
                status_code=404,
            )

        data = node.model_dump(mode="json")
        data["kind"] = node.kind.value
        return JSONResponse(content=data)

    @app.get("/api/knowledge/nodes")
    async def list_knowledge_nodes(
        kind: str | None = Query(default=None, description="Filter by node kind"),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> JSONResponse:
        """List knowledge graph nodes."""
        index = _open_graph_index()
        if index is None:
            return JSONResponse(content={"nodes": [], "total": 0})

        all_nodes = index.all_nodes()

        if kind:
            try:
                node_kind = NodeKind(kind)
                all_nodes = [n for n in all_nodes if n.kind == node_kind]
            except ValueError:
                return JSONResponse(
                    content={"error": f"Unknown node kind: {kind}"},
                    status_code=400,
                )

        total = len(all_nodes)
        paginated = all_nodes[offset : offset + limit]

        return JSONResponse(content={
            "nodes": [n.model_dump(mode="json") for n in paginated],
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    @app.get("/api/knowledge/edges/{edge_id}")
    async def get_knowledge_edge(edge_id: str) -> JSONResponse:
        """Get details for a specific edge."""
        index = _open_graph_index()
        if index is None:
            return JSONResponse(
                content={"error": "Vault not initialized"},
                status_code=404,
            )

        edge = index.edge(edge_id)
        if edge is None:
            return JSONResponse(
                content={"error": f"Edge not found: {edge_id}"},
                status_code=404,
            )

        data = edge.model_dump(mode="json")
        data["kind"] = edge.kind.value
        return JSONResponse(content=data)

    @app.get("/api/knowledge/pages/{page_kind}")
    async def get_knowledge_pages(
        page_kind: str,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> JSONResponse:
        """List wiki pages of a given kind.

        page_kind: one of sessions, sources, claims, gaps, questions, concepts, entities
        """
        from cc_deep_research.knowledge.vault import (
            claims_dir,
            concepts_dir,
            entities_dir,
            questions_dir,
            sessions_dir,
            sources_dir,
        )

        vault = vault_root()
        if not vault.exists():
            return JSONResponse(content={"pages": [], "total": 0})

        kind_to_dir = {
            "sessions": sessions_dir,
            "sources": sources_dir,
            "claims": claims_dir,
            "gaps": questions_dir,
            "questions": questions_dir,
            "concepts": concepts_dir,
            "entities": entities_dir,
        }

        dir_fn = kind_to_dir.get(page_kind)
        if dir_fn is None:
            return JSONResponse(
                content={"error": f"Unknown page kind: {page_kind}"},
                status_code=400,
            )

        dir_path = dir_fn()
        if not dir_path.exists():
            return JSONResponse(content={"pages": [], "total": 0})

        md_files = sorted(
            (f for f in dir_path.iterdir() if f.suffix == ".md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:limit]

        pages = []
        for f in md_files:
            try:
                content = f.read_text(encoding="utf-8")
                # Extract title from first H1 or use filename
                title = content.split("\n")[0].lstrip("# ").strip() if content else f.stem
                pages.append({
                    "path": str(f),
                    "filename": f.name,
                    "title": title,
                    "size": f.stat().st_size,
                })
            except Exception:
                continue

        return JSONResponse(content={"pages": pages, "total": len(pages)})

    @app.get("/api/knowledge/lint-findings")
    async def get_lint_findings() -> JSONResponse:
        """Get lint findings for the knowledge vault."""
        vault = vault_root()
        if not vault.exists():
            return JSONResponse(
                content={"findings": [], "total": 0, "message": "Vault not initialized"},
            )

        findings: list[dict] = []

        # Check for missing index
        index_path = wiki_index_path()
        if not index_path.exists():
            findings.append({
                "severity": "error",
                "category": "missing_index",
                "message": "Vault index.md is missing",
                "page_path": str(index_path),
            })

        # Check empty directories
        for subdir in ["claims", "sessions", "sources", "concepts", "entities", "questions"]:
            dir_path = vault / "wiki" / subdir
            if dir_path.exists() and not any(dir_path.iterdir()):
                findings.append({
                    "severity": "info",
                    "category": "empty_directory",
                    "message": f"Empty directory: wiki/{subdir}",
                    "page_path": str(dir_path),
                })

        # Check for claims without source links
        claims_dir_path = vault / "wiki" / "claims"
        if claims_dir_path.exists():
            for cf in claims_dir_path.iterdir():
                if cf.suffix != ".md":
                    continue
                try:
                    content = cf.read_text(encoding="utf-8")
                    has_link = "http" in content
                    if not has_link:
                        findings.append({
                            "severity": "warning",
                            "category": "unsupported_claim",
                            "message": "Claim page may lack source backing",
                            "page_path": str(cf),
                        })
                except Exception:
                    continue

        return JSONResponse(content={
            "findings": findings,
            "total": len(findings),
            "error_count": sum(1 for f in findings if f["severity"] == "error"),
            "warning_count": sum(1 for f in findings if f["severity"] == "warning"),
            "info_count": sum(1 for f in findings if f["severity"] == "info"),
        })

    @app.get("/api/knowledge/session-contribution/{session_id}")
    async def get_session_contribution(session_id: str) -> JSONResponse:
        """Get knowledge contribution trace for a session."""
        service = KnowledgePlanningService()
        influence = service.summarize_influence(session_id)

        if not influence:
            return JSONResponse(
                content={
                    "session_id": session_id,
                    "knowledge_nodes_influenced": 0,
                    "influenced_node_ids": [],
                    "note": "No knowledge influence found for this session",
                },
            )

        return JSONResponse(content=influence)

    @app.get("/api/knowledge/export")
    async def export_knowledge_graph(
        format: str = Query(default="json", description="Export format: json or markdown"),
    ) -> JSONResponse:
        """Export the knowledge graph as JSON or markdown."""
        index = _open_graph_index()
        if index is None:
            return JSONResponse(
                content={"error": "Vault not initialized or graph index not found"},
                status_code=404,
            )

        if format == "markdown":
            snap = index.snapshot()
            lines = [
                "# Knowledge Graph Snapshot",
                "",
                f"Exported: {snap.exported_at.isoformat()}",
                f"Nodes: {len(snap.nodes)}",
                f"Edges: {len(snap.edges)}",
                "",
                "## Nodes",
                "",
            ]
            for node in snap.nodes:
                lines.append(f"### {node.id} ({node.kind.value})")
                lines.append(f"- label: {node.label}")
                if node.properties:
                    for k, v in node.properties.items():
                        lines.append(f"  - {k}: {v}")
                lines.append("")

            lines.append("## Edges")
            for edge in snap.edges:
                lines.append(f"- **{edge.kind.value}**: {edge.source_id} → {edge.target_id}")

            return JSONResponse(content={"format": "markdown", "content": "\n".join(lines)})

        # JSON
        snap = index.snapshot()
        return JSONResponse(content=snap.model_dump(mode="json"))

    @app.get("/api/knowledge/status")
    async def get_knowledge_vault_status() -> JSONResponse:
        """Get the status of the knowledge vault."""
        vault = vault_root()
        initialized = vault.exists()

        if not initialized:
            return JSONResponse(content={
                "initialized": False,
                "vault_path": str(vault),
                "can_initialize": True,
            })

        # Check what exists
        wiki_index = wiki_index_path()
        graph_path = vault / "graph" / "graph.sqlite"
        raw_dir = vault / "raw"
        wiki_dir = vault / "wiki"

        raw_sessions = 0
        if (raw_dir / "sessions").exists():
            raw_sessions = len(list((raw_dir / "sessions").iterdir()))

        wiki_pages = 0
        if wiki_dir.exists():
            for subdir in wiki_dir.iterdir():
                if subdir.is_dir():
                    wiki_pages += len(list(subdir.glob("*.md")))

        return JSONResponse(content={
            "initialized": True,
            "vault_path": str(vault),
            "has_index": wiki_index.exists(),
            "has_graph_index": graph_path.exists(),
            "raw_session_count": raw_sessions,
            "wiki_page_count": wiki_pages,
        })

    @app.get("/api/knowledge/graph")
    async def get_knowledge_graph_full() -> JSONResponse:
        """Get the full knowledge graph snapshot for D3 visualization.

        P8-T5: Returns nodes and edges in a format suitable for force-directed graph rendering.
        """
        index = _open_graph_index()
        if index is None:
            return JSONResponse(
                content={"error": "Vault not initialized or graph index not found"},
                status_code=404,
            )

        snap = index.snapshot()
        return JSONResponse(content=snap.model_dump(mode="json"))

    @app.get("/api/knowledge/nodes/{node_id}/neighbors")
    async def get_knowledge_node_neighbors(node_id: str) -> JSONResponse:
        """Get neighboring nodes and edges for a given node.

        P8-T5: Returns node neighborhood for graph expansion on selection.
        """
        index = _open_graph_index()
        if index is None:
            return JSONResponse(
                content={"error": "Vault not initialized"},
                status_code=404,
            )

        node = index.node(node_id)
        if node is None:
            return JSONResponse(
                content={"error": f"Node not found: {node_id}"},
                status_code=404,
            )

        # Get edges connected to this node
        all_edges = index.all_edges()
        neighbors_edges = [e for e in all_edges if e.source_id == node_id or e.target_id == node_id]

        # Get neighbor nodes
        neighbor_ids: set[str] = set()
        for edge in neighbors_edges:
            if edge.source_id == node_id:
                neighbor_ids.add(edge.target_id)
            else:
                neighbor_ids.add(edge.source_id)

        neighbor_nodes = []
        for nid in neighbor_ids:
            n = index.node(nid)
            if n is not None:
                neighbor_nodes.append(n)

        return JSONResponse(content={
            "node": node.model_dump(mode="json"),
            "neighbors": [n.model_dump(mode="json") for n in neighbor_nodes],
            "edges": [e.model_dump(mode="json") for e in neighbors_edges],
        })

    @app.post("/api/knowledge/init")
    async def init_knowledge_vault(
        config_path: Path | None = Query(default=None, description="Path to config file"),
        dry_run: bool = Query(default=False, description="Show what would be created without creating"),
    ) -> JSONResponse:
        """Initialize the knowledge vault (creates directories and seed files)."""
        try:
            result = init_vault(config_path, dry_run=dry_run)
            return JSONResponse(content={
                "initialized": not dry_run,
                "dry_run": dry_run,
                "created": {name: str(path) for name, path in result.items()},
            })
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to initialize vault: {str(e)}"},
                status_code=500,
            )

    @app.post("/api/knowledge/backfill")
    async def backfill_knowledge_vault(
        limit: int | None = Query(default=None, ge=1, description="Limit number of sessions to ingest"),
        dry_run: bool = Query(default=False, description="Show sessions to ingest without ingesting"),
    ) -> JSONResponse:
        """Ingest all saved sessions into the knowledge vault."""
        store = SessionStore()
        sessions_dir = get_default_session_dir()

        if not sessions_dir.exists():
            return JSONResponse(
                content={"error": f"Sessions directory not found: {sessions_dir}"},
                status_code=404,
            )

        session_files = sorted(sessions_dir.glob("*.json"))
        if limit is not None:
            session_files = session_files[:limit]

        if dry_run:
            return JSONResponse(content={
                "dry_run": True,
                "total_sessions": len(session_files),
                "session_ids": [sf.stem for sf in session_files],
                "ingested": 0,
                "failed": 0,
            })

        ingested = 0
        failed = 0
        errors: list[dict[str, str]] = []
        for sf in session_files:
            session_id = sf.stem
            session = store.load_session(session_id)
            if session is None:
                failed += 1
                errors.append({"session_id": session_id, "error": "could not load"})
                continue

            try:
                result = ingest_session(session, config_path=None)
                ingested += 1
            except Exception as exc:
                failed += 1
                errors.append({"session_id": session_id, "error": str(exc)})

        return JSONResponse(content={
            "dry_run": False,
            "total_sessions": len(session_files),
            "ingested": ingested,
            "failed": failed,
            "errors": errors,
        })

    @app.post("/api/knowledge/rebuild-index")
    async def rebuild_knowledge_index(
        config_path: Path | None = Query(default=None, description="Path to config file"),
    ) -> JSONResponse:
        """Clear and rebuild the SQLite graph index."""
        from cc_deep_research.knowledge.vault import graph_sqlite_path

        vault = vault_root(config_path)

        if not vault.exists():
            return JSONResponse(
                content={"error": "Vault not initialized. Run init first."},
                status_code=400,
            )

        db_path = graph_sqlite_path(config_path)

        try:
            index = GraphIndex(db_path)
            index.clear()
            index.commit()
            index.close()
        except Exception as exc:
            return JSONResponse(
                content={"error": f"Failed to rebuild index: {str(exc)}"},
                status_code=500,
            )

        return JSONResponse(content={
            "rebuilt": True,
            "db_path": str(db_path),
        })


__all__ = ["register_knowledge_routes"]
