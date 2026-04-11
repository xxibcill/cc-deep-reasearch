'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';

import type {
  DecisionGraph as DecisionGraphModel,
  DecisionGraphNode,
  TelemetryEvent,
} from '@/types/telemetry';

const KIND_ORDER: DecisionGraphNode['kind'][] = [
  'event',
  'decision',
  'outcome',
  'state_change',
  'degradation',
  'failure',
];

const NODE_COLORS: Record<DecisionGraphNode['kind'], string> = {
  event: '#64748b',
  decision: '#0f766e',
  outcome: '#0369a1',
  state_change: '#2563eb',
  degradation: '#d97706',
  failure: '#b91c1c',
};

const SEVERITY_COLORS: Record<string, string> = {
  info: '#38bdf8',
  warning: '#f59e0b',
  error: '#ef4444',
  critical: '#dc2626',
};

function truncateLabel(label: string, maxLength = 28): string {
  if (label.length <= maxLength) {
    return label;
  }
  return `${label.slice(0, maxLength - 1)}…`;
}

function sanitizeTestId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, '-');
}

function formatKind(kind: DecisionGraphNode['kind']): string {
  return kind.replace(/_/g, ' ');
}

function getNodeSubtitle(node: DecisionGraphNode): string {
  const fragments = [formatKind(node.kind)];
  if (node.actor_id) {
    fragments.push(node.actor_id);
  }
  if (node.severity && node.severity !== 'info') {
    fragments.push(node.severity);
  }
  return fragments.join(' • ');
}

function layoutNodes(nodes: DecisionGraphNode[]) {
  const grouped = new Map<DecisionGraphNode['kind'], DecisionGraphNode[]>();
  for (const node of nodes) {
    const list = grouped.get(node.kind) ?? [];
    list.push(node);
    grouped.set(node.kind, list);
  }

  const positions = new Map<string, { x: number; y: number }>();
  KIND_ORDER.forEach((kind, columnIndex) => {
    const group = [...(grouped.get(kind) ?? [])].sort((left, right) => {
      const sequenceOrder = (left.sequence_number ?? 0) - (right.sequence_number ?? 0);
      if (sequenceOrder !== 0) {
        return sequenceOrder;
      }
      return (left.timestamp ?? '').localeCompare(right.timestamp ?? '');
    });

    group.forEach((node, rowIndex) => {
      positions.set(node.id, {
        x: 132 + columnIndex * 228,
        y: 110 + rowIndex * 108,
      });
    });
  });

  return positions;
}

function edgePath(
  source: { x: number; y: number },
  target: { x: number; y: number }
): string {
  const controlX = source.x + (target.x - source.x) / 2;
  return `M ${source.x} ${source.y} C ${controlX} ${source.y}, ${controlX} ${target.y}, ${target.x} ${target.y}`;
}

function graphBounds(positions: Map<string, { x: number; y: number }>) {
  const values = [...positions.values()];
  const maxX = values.length > 0 ? Math.max(...values.map((position) => position.x)) : 0;
  const maxY = values.length > 0 ? Math.max(...values.map((position) => position.y)) : 0;
  return {
    width: Math.max(maxX + 190, 980),
    height: Math.max(maxY + 160, 460),
  };
}

export function DecisionGraph({
  graph,
  eventIndex,
  selectedEventId,
  selectedNodeId,
  onSelectEvent,
}: {
  graph: DecisionGraphModel;
  eventIndex: Map<string, TelemetryEvent>;
  selectedEventId: string | null;
  selectedNodeId: string | null;
  onSelectEvent: (event: TelemetryEvent | null, node: DecisionGraphNode) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomLayerRef = useRef<SVGGElement | null>(null);
  const positions = useMemo(() => layoutNodes(graph.nodes), [graph.nodes]);
  const { width, height } = useMemo(() => graphBounds(positions), [positions]);
  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId]
  );

  useEffect(() => {
    const element = svgRef.current;
    const zoomLayer = zoomLayerRef.current;
    if (!element || !zoomLayer) {
      return;
    }

    const svg = d3.select<SVGSVGElement, unknown>(element);
    const zoomLayerSelection = d3.select<SVGGElement, unknown>(zoomLayer);
    svg.on('.zoom', null);
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.5, 2.4])
        .on('zoom', (event) => {
          zoomLayerSelection.attr('transform', event.transform.toString());
        })
    );
  }, [graph.edges.length, graph.nodes.length]);

  if (graph.nodes.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
        No decision graph nodes matched the current filters.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span className="rounded-full bg-surface-raised px-3 py-1">
          {graph.summary.node_count} nodes
        </span>
        <span className="rounded-full bg-surface-raised px-3 py-1">
          {graph.summary.explicit_edge_count} explicit edges
        </span>
        <span className="rounded-full bg-surface-raised px-3 py-1">
          {graph.summary.inferred_edge_count} inferred edges
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="rounded-2xl border border-border/70 bg-surface-raised/42 p-4 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Read the graph fast</p>
          <p className="mt-1">
            Solid links come directly from telemetry. Dashed links are inferred causal joins.
            Warning and error nodes get a bright severity marker so they stand out before you open
            the inspector.
          </p>
        </div>
        <div className="rounded-2xl border border-border/70 bg-surface-raised/42 p-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="h-0.5 w-8 rounded-full bg-foreground" />
            Explicit telemetry link
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="h-0.5 w-8 rounded-full border-t-2 border-dashed border-border" />
            Inferred domain link
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-warning" />
            High-severity decision path
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.14),transparent_35%),linear-gradient(180deg,rgba(31,27,23,0.98),rgba(42,35,30,0.96))]">
        <svg
          ref={svgRef}
          className="h-[560px] w-full"
          viewBox={`0 0 ${width} ${height}`}
          aria-label="Decision graph"
        >
          <defs>
            <marker
              id="decision-graph-arrow"
              markerWidth="10"
              markerHeight="10"
              refX="8"
              refY="3"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path d="M0,0 L0,6 L9,3 z" fill="#b0a89c" />
            </marker>
          </defs>

          <g ref={zoomLayerRef}>
            <rect width={width} height={height} fill="transparent" />

            {graph.edges.map((edge) => {
              const source = positions.get(edge.source);
              const target = positions.get(edge.target);
              if (!source || !target) {
                return null;
              }

              return (
                <path
                  key={edge.id}
                  d={edgePath(source, target)}
                  fill="none"
                  markerEnd="url(#decision-graph-arrow)"
                  stroke={edge.inferred ? '#b0a89c' : '#f5f5f4'}
                  strokeDasharray={edge.inferred ? '7 6' : '0'}
                  strokeOpacity={edge.inferred ? 0.7 : 0.82}
                  strokeWidth={edge.inferred ? 2 : 2.4}
                  data-edge-inferred={edge.inferred ? 'true' : 'false'}
                  data-testid={`decision-graph-edge-${sanitizeTestId(edge.id)}`}
                />
              );
            })}

            {KIND_ORDER.map((kind, index) => (
              <g key={kind}>
                <text
                  x={132 + index * 228}
                  y={40}
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight="700"
                  fill="#d6d0c7"
                  letterSpacing="0.12em"
                >
                  {formatKind(kind).toUpperCase()}
                </text>
              </g>
            ))}

            {graph.nodes.map((node) => {
              const position = positions.get(node.id);
              if (!position) {
                return null;
              }

              const isSelected =
                node.id === selectedNodeId
                || (node.event_id !== null && node.event_id === selectedEventId);
              const background = NODE_COLORS[node.kind];
              const event = node.event_id ? eventIndex.get(node.event_id) ?? null : null;
              const severityColor =
                node.severity && node.severity !== 'info'
                  ? SEVERITY_COLORS[node.severity] ?? SEVERITY_COLORS.warning
                  : null;

              return (
                <g
                  key={node.id}
                  role="button"
                  tabIndex={0}
                  transform={`translate(${position.x}, ${position.y})`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelectEvent(event, node)}
                  onKeyDown={(keyboardEvent) => {
                    if (keyboardEvent.key === 'Enter' || keyboardEvent.key === ' ') {
                      keyboardEvent.preventDefault();
                      onSelectEvent(event, node);
                    }
                  }}
                  aria-label={node.label}
                  data-testid={`decision-graph-node-${sanitizeTestId(node.id)}`}
                >
                  <rect
                    x={-78}
                    y={-30}
                    rx={18}
                    width={156}
                    height={60}
                    fill={background}
                    opacity={node.inferred ? 0.82 : 0.96}
                    stroke={isSelected ? '#fbbf24' : 'rgba(245,245,244,0.22)'}
                    strokeWidth={isSelected ? 4 : 2}
                  />
                  {severityColor ? (
                    <circle cx={58} cy={-16} r={6} fill={severityColor} />
                  ) : null}
                  <text
                    textAnchor="middle"
                    y={-5}
                    fontSize="12"
                    fontWeight="700"
                    fill="#f8fafc"
                  >
                    {truncateLabel(node.label)}
                  </text>
                  <text
                    textAnchor="middle"
                    y={14}
                    fontSize="10"
                    fill="rgba(248,250,252,0.92)"
                  >
                    {truncateLabel(getNodeSubtitle(node), 30)}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {selectedNode ? (
        <div className="rounded-2xl border border-amber-400/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-50">
          <span className="font-semibold text-amber-100">Selected:</span> {selectedNode.label}
          <span className="ml-2 text-amber-100/80">
            {selectedNode.inferred ? 'Inferred link context.' : 'Explicit telemetry context.'}
            {selectedNode.severity && selectedNode.severity !== 'info'
              ? ` Severity: ${selectedNode.severity}.`
              : ''}
          </span>
        </div>
      ) : null}
    </div>
  );
}
