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
  event: '#cbd5e1',
  decision: '#0f766e',
  outcome: '#0369a1',
  state_change: '#2563eb',
  degradation: '#d97706',
  failure: '#dc2626',
};

function truncateLabel(label: string, maxLength = 26): string {
  if (label.length <= maxLength) {
    return label;
  }
  return `${label.slice(0, maxLength - 1)}…`;
}

function sanitizeTestId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, '-');
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
        x: 120 + columnIndex * 220,
        y: 90 + rowIndex * 96,
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
    width: Math.max(maxX + 180, 900),
    height: Math.max(maxY + 140, 420),
  };
}

export function DecisionGraph({
  graph,
  eventIndex,
  selectedEventId,
  onSelectEvent,
}: {
  graph: DecisionGraphModel;
  eventIndex: Map<string, TelemetryEvent>;
  selectedEventId: string | null;
  onSelectEvent: (event: TelemetryEvent | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const zoomLayerRef = useRef<SVGGElement | null>(null);
  const positions = useMemo(() => layoutNodes(graph.nodes), [graph.nodes]);
  const { width, height } = useMemo(() => graphBounds(positions), [positions]);

  useEffect(() => {
    const element = svgRef.current;
    const zoomLayer = zoomLayerRef.current;
    if (!element || !zoomLayer) {
      return;
    }

    const svg = d3.select<SVGSVGElement, unknown>(element);
    const zoomLayerSelection = d3.select<SVGGElement, unknown>(zoomLayer);
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
        <span className="rounded-full bg-slate-100 px-3 py-1">
          {graph.summary.node_count} nodes
        </span>
        <span className="rounded-full bg-slate-100 px-3 py-1">
          {graph.summary.explicit_edge_count} explicit edges
        </span>
        <span className="rounded-full bg-slate-100 px-3 py-1">
          {graph.summary.inferred_edge_count} inferred edges
        </span>
      </div>

      <div className="overflow-hidden rounded-2xl border bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.10),transparent_35%),linear-gradient(180deg,#f8fafc,#eef2ff)]">
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
              <path d="M0,0 L0,6 L9,3 z" fill="#64748b" />
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
                  stroke={edge.inferred ? '#64748b' : '#0f172a'}
                  strokeDasharray={edge.inferred ? '7 6' : '0'}
                  strokeOpacity={edge.inferred ? 0.65 : 0.88}
                  strokeWidth={edge.inferred ? 2 : 2.4}
                  data-edge-inferred={edge.inferred ? 'true' : 'false'}
                  data-testid={`decision-graph-edge-${sanitizeTestId(edge.id)}`}
                />
              );
            })}

            {KIND_ORDER.map((kind, index) => (
              <g key={kind}>
                <text
                  x={120 + index * 220}
                  y={36}
                  textAnchor="middle"
                  fontSize="12"
                  fontWeight="700"
                  fill="#475569"
                  letterSpacing="0.12em"
                >
                  {kind.replace('_', ' ').toUpperCase()}
                </text>
              </g>
            ))}

            {graph.nodes.map((node) => {
              const position = positions.get(node.id);
              if (!position) {
                return null;
              }

              const isSelected = Boolean(node.event_id && node.event_id === selectedEventId);
              const background = NODE_COLORS[node.kind];
              const event = node.event_id ? eventIndex.get(node.event_id) ?? null : null;
              return (
                <g
                  key={node.id}
                  role="button"
                  tabIndex={0}
                  transform={`translate(${position.x}, ${position.y})`}
                  style={{ cursor: node.event_id ? 'pointer' : 'default' }}
                  onClick={() => onSelectEvent(event)}
                  onKeyDown={(keyboardEvent) => {
                    if (keyboardEvent.key === 'Enter' || keyboardEvent.key === ' ') {
                      keyboardEvent.preventDefault();
                      onSelectEvent(event);
                    }
                  }}
                  aria-label={node.label}
                  data-testid={`decision-graph-node-${sanitizeTestId(node.id)}`}
                >
                  <rect
                    x={-72}
                    y={-26}
                    rx={16}
                    width={144}
                    height={52}
                    fill={background}
                    opacity={node.inferred ? 0.78 : 0.96}
                    stroke={isSelected ? '#0f172a' : '#ffffff'}
                    strokeWidth={isSelected ? 4 : 2}
                  />
                  <text
                    textAnchor="middle"
                    y={-2}
                    fontSize="12"
                    fontWeight="700"
                    fill="#f8fafc"
                  >
                    {truncateLabel(node.label)}
                  </text>
                  <text
                    textAnchor="middle"
                    y={15}
                    fontSize="10"
                    fill="rgba(248,250,252,0.88)"
                  >
                    {node.event_type ?? node.kind}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="h-0.5 w-8 rounded-full bg-slate-900" />
          Explicit telemetry link
        </div>
        <div className="flex items-center gap-2">
          <span className="h-0.5 w-8 rounded-full border-t-2 border-dashed border-slate-500" />
          Inferred domain link
        </div>
      </div>
    </div>
  );
}
