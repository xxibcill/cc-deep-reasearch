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
} from '@/lib/knowledge-client';
import { KnowledgeGraph } from './knowledge-graph';
import { NodeInspector } from './node-inspector';
import { KnowledgeFilters, type KnowledgeNodeKind } from './knowledge-filters';
import { LintQueue } from './lint-queue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  const [selectedKinds, setSelectedKinds] = useState<KnowledgeNodeKind[]>([]);
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

  function handleToggleKind(kind: KnowledgeNodeKind) {
    setSelectedKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind],
    );
  }

  function handleClearKinds() {
    setSelectedKinds([]);
  }

  const filteredNodes = (graph?.nodes ?? []).filter((n) => {
    if (selectedKinds.length > 0 && !selectedKinds.some((kind) => kind === n.kind)) return false;
    if (searchQuery && !n.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const filteredEdges = (graph?.edges ?? []).filter(
    (e) =>
      filteredNodes.some((n) => n.id === e.source_id) &&
      filteredNodes.some((n) => n.id === e.target_id),
  );
  const nodeLabels = new Map(filteredNodes.map((node) => [node.id, node.label]));

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 flex-col gap-3 overflow-x-hidden overflow-y-auto p-3 sm:p-4 lg:flex-row lg:gap-4 lg:overflow-hidden">
      {/* Left sidebar */}
      <div className="flex w-full min-w-0 shrink-0 flex-col gap-3 lg:w-64">
        <KnowledgeFilters
          selectedKinds={selectedKinds}
          onToggleKind={handleToggleKind}
          onClearKinds={handleClearKinds}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        <div className="flex items-center justify-between gap-3">
          <span aria-live="polite" className="text-xs text-muted-foreground">
            {filteredNodes.length} nodes
          </span>
          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => loadGraph()}
              className="min-h-11 rounded-md px-3 text-xs font-medium text-muted-foreground hover:bg-surface-raised hover:text-foreground lg:min-h-8 lg:px-2"
            >
              Reload
            </button>
            <button
              type="button"
              onClick={() => {
                setShowLint(!showLint);
                if (!showLint && findings.length === 0) loadFindings();
              }}
              aria-expanded={showLint}
              aria-controls="knowledge-lint-queue"
              className="min-h-11 rounded-md px-3 text-xs font-medium text-muted-foreground hover:bg-surface-raised hover:text-foreground lg:min-h-8 lg:px-2"
            >
              {showLint ? 'Hide Lint' : 'Lint'}
            </button>
          </div>
        </div>

        {showLint && (
          <div id="knowledge-lint-queue">
            <LintQueue findings={findings} onRefresh={loadFindings} />
          </div>
        )}

        <div className="mt-auto border-t pt-3">
          <button
            type="button"
            onClick={() => setShowSettings(!showSettings)}
            aria-expanded={showSettings}
            aria-controls="knowledge-infrastructure-controls"
            className="flex min-h-11 w-full items-center gap-2 rounded-md px-2 text-xs font-medium text-muted-foreground hover:bg-surface-raised hover:text-foreground lg:min-h-8"
          >
            <Database className="h-3 w-3" />
            Infrastructure
            <span
              aria-hidden="true"
              className={`ml-auto transition-transform ${showSettings ? 'rotate-180' : ''}`}
            >
              ▾
            </span>
          </button>

          {showSettings && (
            <div
              id="knowledge-infrastructure-controls"
              className="mt-3 space-y-3 rounded-lg border bg-surface-raised/50 p-3"
            >
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
                    className="min-h-11 w-full text-xs lg:min-h-8"
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
                    aria-label="Maximum sessions to backfill"
                    inputMode="numeric"
                    placeholder="Limit (optional)"
                    value={backfillLimit}
                    onChange={(e) => setBackfillLimit(e.target.value)}
                    className="h-11 min-w-0 flex-1 text-base lg:h-8 lg:w-24 lg:flex-none lg:text-xs"
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
                    className="min-h-11 flex-1 text-xs lg:min-h-8"
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
                  className="min-h-11 w-full text-xs lg:min-h-8"
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Rebuild Index
                </Button>
                <p className="text-[10px] text-muted-foreground">
                  Clears all nodes and edges. Use backfill to repopulate.
                </p>
              </div>

              <label
                htmlFor="dry-run-mode"
                className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md px-2 hover:bg-background/40 lg:min-h-8"
              >
                <input
                  type="checkbox"
                  id="dry-run-mode"
                  checked={dryRunMode}
                  onChange={(e) => setDryRunMode(e.target.checked)}
                  className="h-4 w-4"
                />
                <span className="text-xs text-muted-foreground">
                  Dry-run mode
                </span>
              </label>

              {actionStatus && (
                <div
                  role="status"
                  aria-live="polite"
                  className="flex items-center gap-1 rounded bg-muted/50 p-2"
                >
                  <AlertTriangle className="h-3 w-3 text-muted-foreground" />
                  <p className="text-[10px] text-muted-foreground">{actionStatus}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main graph area */}
      <section
        aria-label="Knowledge graph explorer"
        className="relative flex w-full min-w-0 shrink-0 flex-col gap-2 lg:flex-1"
      >
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/60">
            <span className="text-sm text-muted-foreground">Loading…</span>
          </div>
        )}

        {graph ? (
          <div
            data-testid="knowledge-graph-region"
            className="h-[clamp(22rem,62svh,36rem)] min-h-[22rem] w-full flex-none overflow-hidden rounded-xl border bg-background lg:h-96 lg:min-h-0 lg:flex-1"
          >
            <KnowledgeGraph
              data={{ nodes: filteredNodes, edges: filteredEdges }}
              selectedNodeId={selectedNode?.id ?? null}
              onSelectNode={handleSelectNode}
              width={800}
              height={380}
            />
          </div>
        ) : (
          <div
            data-testid="knowledge-graph-region"
            className="flex h-[clamp(22rem,62svh,36rem)] min-h-[22rem] w-full flex-none items-center justify-center rounded-xl border border-dashed p-4 text-sm text-muted-foreground lg:h-96 lg:min-h-0 lg:flex-1"
          >
            <div className="text-center">
              <p>No knowledge graph data.</p>
              <button
                type="button"
                onClick={loadGraph}
                className="mt-2 min-h-11 rounded-md px-3 text-xs font-medium text-warning hover:bg-warning-muted lg:min-h-8"
              >
                Load Graph
              </button>
            </div>
          </div>
        )}

        {graph && filteredNodes.length > 0 ? (
          <details className="shrink-0 rounded-lg border border-border/70 bg-surface/45">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-3 text-sm font-medium text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
              <span>Graph data</span>
              <span className="text-xs font-normal text-muted-foreground">
                {filteredNodes.length} nodes · {filteredEdges.length} relationships
              </span>
            </summary>
            <div className="grid gap-5 border-t border-border/60 p-3 xl:grid-cols-2">
              <section aria-labelledby="knowledge-node-list-heading" className="min-w-0">
                <h3 id="knowledge-node-list-heading" className="text-sm font-semibold text-foreground">
                  Nodes
                </h3>
                <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto pr-1 text-xs text-muted-foreground">
                  {filteredNodes.map((node) => (
                    <li key={node.id} className="rounded-md bg-background/60 px-2 py-1.5">
                      <span className="font-medium text-foreground">{node.label}</span>
                      <span className="ml-2">{node.kind.replace(/_/g, ' ')}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section aria-labelledby="knowledge-relationship-list-heading" className="min-w-0">
                <h3
                  id="knowledge-relationship-list-heading"
                  className="text-sm font-semibold text-foreground"
                >
                  Relationships
                </h3>
                {filteredEdges.length > 0 ? (
                  <div
                    aria-label="Knowledge graph relationships"
                    className="mt-2 max-h-48 overflow-auto"
                    role="region"
                    tabIndex={0}
                  >
                    <table className="w-full min-w-[28rem] text-left text-xs">
                      <thead className="text-muted-foreground">
                        <tr>
                          <th scope="col" className="px-2 py-1.5 font-medium">Source</th>
                          <th scope="col" className="px-2 py-1.5 font-medium">Relationship</th>
                          <th scope="col" className="px-2 py-1.5 font-medium">Target</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50 text-foreground">
                        {filteredEdges.map((edge) => (
                          <tr key={edge.id}>
                            <td className="px-2 py-1.5">{nodeLabels.get(edge.source_id) ?? edge.source_id}</td>
                            <td className="px-2 py-1.5 text-muted-foreground">
                              {edge.kind.replace(/_/g, ' ')}
                            </td>
                            <td className="px-2 py-1.5">{nodeLabels.get(edge.target_id) ?? edge.target_id}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">
                    No relationships match the current filters.
                  </p>
                )}
              </section>
            </div>
          </details>
        ) : null}
      </section>

      {/* Right inspector */}
      <aside
        aria-label="Node inspector"
        data-testid="knowledge-node-inspector"
        className="w-full min-w-0 shrink-0 overflow-hidden rounded-xl border bg-background lg:w-72"
      >
        <NodeInspector
          node={selectedNode}
          neighbors={neighbors}
          edges={neighborEdges}
          onClose={() => setSelectedNode(null)}
        />
      </aside>
    </div>
  );
}
