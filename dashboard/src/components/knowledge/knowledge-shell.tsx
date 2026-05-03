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
  initVault,
  backfillVault,
  rebuildIndex,
  fetchVaultStatus,
} from '@/lib/knowledge-client';
import { KnowledgeGraph } from './knowledge-graph';
import { NodeInspector } from './node-inspector';
import { KnowledgeFilters } from './knowledge-filters';
import { LintQueue } from './lint-queue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, Database, RefreshCw, Upload } from 'lucide-react';

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
  const [showSettings, setShowSettings] = useState(false);
  const [vaultInitialized, setVaultInitialized] = useState(false);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [backfillLimit, setBackfillLimit] = useState<string>('');
  const [dryRunMode, setDryRunMode] = useState(false);

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

        <div className="mt-auto border-t pt-3">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="flex w-full items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <Database className="h-3 w-3" />
            Infrastructure
          </button>

          {showSettings && (
            <div className="mt-3 space-y-3 rounded-lg border bg-surface-raised/50 p-3">
              {!vaultInitialized && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">Initialize the knowledge vault first.</p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      setActionStatus('Initializing vault...');
                      try {
                        const result = await initVault(undefined, dryRunMode);
                        if (dryRunMode) {
                          setActionStatus(`Dry run: would create ${Object.keys(result.created).length} items`);
                        } else {
                          setVaultInitialized(true);
                          setActionStatus('Vault initialized successfully');
                          loadGraph();
                        }
                      } catch {
                        setActionStatus('Failed to initialize vault');
                      }
                    }}
                    className="w-full text-xs"
                  >
                    <Upload className="mr-1 h-3 w-3" />
                    {dryRunMode ? 'Preview Init' : 'Initialize Vault'}
                  </Button>
                </div>
              )}

              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Backfill Sessions</p>
                <div className="flex gap-1">
                  <Input
                    placeholder="Limit (optional)"
                    value={backfillLimit}
                    onChange={(e) => setBackfillLimit(e.target.value)}
                    className="h-7 w-20 text-xs"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      setActionStatus('Running backfill...');
                      try {
                        const limit = backfillLimit ? parseInt(backfillLimit, 10) : undefined;
                        const result = await backfillVault(limit, dryRunMode);
                        if (dryRunMode) {
                          setActionStatus(`Dry run: would ingest ${result.total_sessions} sessions`);
                        } else {
                          setActionStatus(`Backfill: ${result.ingested} ingested, ${result.failed} failed`);
                          loadGraph();
                        }
                      } catch {
                        setActionStatus('Backfill failed');
                      }
                    }}
                    className="flex-1 text-xs"
                  >
                    {dryRunMode ? 'Preview' : 'Run'}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Rebuild Index</p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    setActionStatus('Rebuilding index...');
                    try {
                      await rebuildIndex();
                      setActionStatus('Index rebuilt successfully');
                      loadGraph();
                    } catch {
                      setActionStatus('Rebuild failed');
                    }
                  }}
                  className="w-full text-xs"
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Rebuild Index
                </Button>
                <p className="text-[10px] text-muted-foreground">
                  Clears all nodes and edges. Use backfill to repopulate.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="dry-run-mode"
                  checked={dryRunMode}
                  onChange={(e) => setDryRunMode(e.target.checked)}
                  className="h-3 w-3"
                />
                <label htmlFor="dry-run-mode" className="text-[10px] text-muted-foreground">
                  Dry-run mode
                </label>
              </div>

              {actionStatus && (
                <div className="flex items-center gap-1 rounded bg-muted/50 p-2">
                  <AlertTriangle className="h-3 w-3 text-muted-foreground" />
                  <p className="text-[10px] text-muted-foreground">{actionStatus}</p>
                </div>
              )}
            </div>
          )}
        </div>
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
