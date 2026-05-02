'use client';

import { useState } from 'react';
import type {
  KnowledgeNode,
  KnowledgeEdge,
  GraphSnapshot,
  LintFinding,
} from '@/lib/knowledge-client';
import {
  fetchGraphFull,
  fetchLintFindings,
  fetchNodeNeighbors,
} from '@/lib/knowledge-client';
import { KnowledgeGraph } from './knowledge-graph';
import { NodeInspector } from './node-inspector';
import { KnowledgeFilters } from './knowledge-filters';
import { LintQueue } from './lint-queue';

interface KnowledgeShellProps {
  initialGraph?: GraphSnapshot;
  initialFindings?: LintFinding[];
}

export function KnowledgeShell({ initialGraph, initialFindings }: KnowledgeShellProps) {
  const [graph, setGraph] = useState<GraphSnapshot | null>(initialGraph ?? null);
  const [findings, setFindings] = useState<LintFinding[]>(initialFindings ?? []);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [neighbors, setNeighbors] = useState<KnowledgeNode[]>([]);
  const [neighborEdges, setNeighborEdges] = useState<KnowledgeEdge[]>([]);
  const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [showLint, setShowLint] = useState(false);

  async function loadGraph() {
    setLoading(true);
    try {
      const g = await fetchGraphFull();
      setGraph(g);
    } catch {
      // Keep existing graph on error
    } finally {
      setLoading(false);
    }
  }

  async function loadFindings() {
    try {
      const f = await fetchLintFindings();
      setFindings(f.findings);
    } catch {
      // Keep existing findings on error
    }
  }

  async function handleSelectNode(node: KnowledgeNode | null) {
    setSelectedNode(node);
    if (node) {
      try {
        const nb = await fetchNodeNeighbors(node.id);
        setNeighbors(nb.neighbors);
        setNeighborEdges(nb.edges);
      } catch {
        setNeighbors([]);
        setNeighborEdges([]);
      }
    } else {
      setNeighbors([]);
      setNeighborEdges([]);
    }
  }

  function handleToggleKind(kind: string) {
    if (!kind) {
      setSelectedKinds([]);
      return;
    }
    setSelectedKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind],
    );
  }

  const filteredNodes = (graph?.nodes ?? []).filter((n) => {
    if (selectedKinds.length > 0 && !selectedKinds.includes(n.kind)) return false;
    if (searchQuery && !n.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const filteredEdges = (graph?.edges ?? []).filter(
    (e) =>
      filteredNodes.some((n) => n.id === e.source_id) &&
      filteredNodes.some((n) => n.id === e.target_id),
  );

  return (
    <div className="flex h-full gap-4 p-4">
      {/* Left sidebar */}
      <div className="flex w-64 shrink-0 flex-col gap-3">
        <KnowledgeFilters
          selectedKinds={selectedKinds}
          onToggleKind={handleToggleKind}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {filteredNodes.length} nodes
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => loadGraph()}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Reload
            </button>
            <button
              onClick={() => {
                setShowLint(!showLint);
                if (!showLint && findings.length === 0) loadFindings();
              }}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              {showLint ? 'Hide Lint' : 'Lint'}
            </button>
          </div>
        </div>

        {showLint && <LintQueue findings={findings} onRefresh={loadFindings} />}
      </div>

      {/* Main graph area */}
      <div className="relative flex min-w-0 flex-1 flex-col gap-2">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/60">
            <span className="text-sm text-muted-foreground">Loading…</span>
          </div>
        )}

        {graph ? (
          <div className="h-96 min-h-0 flex-1 rounded-xl border bg-background">
            <KnowledgeGraph
              data={{ nodes: filteredNodes, edges: filteredEdges }}
              selectedNodeId={selectedNode?.id ?? null}
              onSelectNode={handleSelectNode}
              width={800}
              height={380}
            />
          </div>
        ) : (
          <div className="flex h-96 flex-1 items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground">
            <div className="text-center">
              <p>No knowledge graph data.</p>
              <button
                onClick={loadGraph}
                className="mt-2 text-xs text-primary hover:underline"
              >
                Load Graph
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Right inspector */}
      <div className="w-72 shrink-0 overflow-hidden rounded-xl border bg-background">
        <NodeInspector
          node={selectedNode}
          neighbors={neighbors}
          edges={neighborEdges}
          onClose={() => setSelectedNode(null)}
        />
      </div>
    </div>
  );
}
