'use client';

import type { KnowledgeNode, KnowledgeEdge } from '@/lib/knowledge-client';
import { Badge } from '@/components/ui/badge';

interface NodeInspectorProps {
  node: KnowledgeNode | null;
  neighbors?: KnowledgeNode[];
  edges?: KnowledgeEdge[];
  onClose: () => void;
}

const KIND_LABELS: Record<string, string> = {
  session: 'Research Session',
  source: 'Source',
  query: 'Query',
  concept: 'Concept',
  entity: 'Entity',
  claim: 'Claim',
  finding: 'Finding',
  gap: 'Gap',
  question: 'Question',
  wiki_page: 'Wiki Page',
};

function formatKind(kind: string): string {
  return KIND_LABELS[kind] ?? kind.replace(/_/g, ' ');
}

export function NodeInspector({ node, neighbors = [], edges = [], onClose }: NodeInspectorProps) {
  if (!node) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Select a node to inspect
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {formatKind(node.kind)}
          </Badge>
          <span className="text-xs text-muted-foreground">Node Inspector</span>
        </div>
        <button
          onClick={onClose}
          className="text-xs text-muted-foreground hover:text-foreground"
          aria-label="Close inspector"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <h3 className="break-words text-sm font-semibold">{node.label}</h3>
        <p className="mt-1 text-xs text-muted-foreground">{node.id}</p>

        {node.properties && Object.keys(node.properties).length > 0 && (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">Properties</h4>
            <dl className="space-y-1.5">
              {Object.entries(node.properties).map(([key, value]) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <dt className="text-xs text-muted-foreground">{key}</dt>
                  <dd className="break-all text-xs">
                    {typeof value === 'string'
                      ? value.length > 100
                        ? `${value.slice(0, 100)}…`
                        : value
                      : JSON.stringify(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {neighbors.length > 0 && (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">
              Connected ({neighbors.length})
            </h4>
            <ul className="space-y-1">
              {neighbors.slice(0, 10).map((n) => (
                <li key={n.id} className="flex items-center gap-2 text-xs">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: '#94a3b8' }}
                  />
                  <span className="text-muted-foreground">{n.kind}:</span>
                  <span className="truncate">{n.label}</span>
                </li>
              ))}
              {neighbors.length > 10 && (
                <li className="text-xs text-muted-foreground">
                  +{neighbors.length - 10} more
                </li>
              )}
            </ul>
          </div>
        )}

        {edges.length > 0 && (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">
              Edges ({edges.length})
            </h4>
            <ul className="space-y-1">
              {edges.slice(0, 10).map((e) => (
                <li key={e.id} className="flex items-center gap-1 text-xs text-muted-foreground">
                  <span className="font-medium">{e.kind}</span>
                  <span>→</span>
                  <span className="truncate">
                    {e.source_id === node.id ? e.target_id : e.source_id}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
