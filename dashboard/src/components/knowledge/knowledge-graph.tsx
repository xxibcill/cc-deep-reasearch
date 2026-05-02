'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { KnowledgeNode, KnowledgeEdge } from '@/lib/knowledge-client';

interface GraphData {
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
}

interface KnowledgeGraphProps {
  data: GraphData;
  selectedNodeId: string | null;
  onSelectNode: (node: KnowledgeNode | null) => void;
  width?: number;
  height?: number;
}

const NODE_COLORS: Record<string, string> = {
  session: '#6366f1',
  source: '#10b981',
  query: '#f59e0b',
  concept: '#8b5cf6',
  entity: '#06b6d4',
  claim: '#ef4444',
  finding: '#22c55e',
  gap: '#f97316',
  question: '#3b82f6',
  wiki_page: '#64748b',
};

const DEFAULT_COLOR = '#94a3b8';

function nodeColor(kind: string): string {
  return NODE_COLORS[kind] ?? DEFAULT_COLOR;
}

export function KnowledgeGraph({
  data,
  selectedNodeId,
  onSelectNode,
  width = 800,
  height = 500,
}: KnowledgeGraphProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const simulation = useMemo(() => {
    if (data.nodes.length === 0) return null;

    const nodeData = data.nodes.map((n) => ({ ...n }));
    const edgeData = data.edges.map((e) => ({ ...e }));

    return d3
      .forceSimulation(nodeData as d3.SimulationNodeDatum[])
      .force(
        'link',
        d3
          .forceLink(edgeData)
          .id((d: d3.SimulationNodeDatum) => (d as KnowledgeNode).id)
          .distance(80),
      )
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(24));
  }, [data, width, height]);

  useEffect(() => {
    const element = svgRef.current;
    if (!element || !simulation) return;

    const svg = d3.select<SVGSVGElement, unknown>(element);
    svg.on('dblclick.zoom', null);
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on('zoom', (event) => {
          svg.select('g.graph-layer').attr('transform', event.transform.toString());
        }),
    );

    return () => {
      simulation.stop();
    };
  }, [simulation]);

  const getNodePositions = useCallback(() => {
    if (!simulation) return new Map<string, { x: number; y: number }>();
    const positions = new Map<string, { x: number; y: number }>();
    // @ts-expect-error - simulation nodes are typed loosely
    for (const node of simulation.nodes()) {
      positions.set(node.id, { x: node.x ?? 0, y: node.y ?? 0 });
    }
    return positions;
  }, [simulation]);

  const positions = getNodePositions();

  if (data.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-dashed p-8 text-sm text-muted-foreground">
        No knowledge graph data. Initialize the vault and ingest sessions first.
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-xl border bg-background">
      <svg
        ref={svgRef}
        className="h-full w-full"
        viewBox={`0 0 ${width} ${height}`}
        aria-label="Knowledge graph"
      >
        <defs>
          <marker
            id="kg-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L0,6 L8,3 z" fill="#64748b" />
          </marker>
        </defs>

        <g className="graph-layer">
          {data.edges.map((edge) => {
            const source = positions.get(edge.source_id);
            const target = positions.get(edge.target_id);
            if (!source || !target) return null;
            return (
              <line
                key={edge.id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="#475569"
                strokeWidth={1.5}
                markerEnd="url(#kg-arrow)"
                opacity={0.6}
              />
            );
          })}

          {data.nodes.map((node) => {
            const pos = positions.get(node.id);
            if (!pos) return null;
            const isSelected = node.id === selectedNodeId;
            const isHovered = node.id === hoveredNode;
            const color = nodeColor(node.kind);

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x},${pos.y})`}
                onClick={() => onSelectNode(isSelected ? null : node)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                style={{ cursor: 'pointer' }}
              >
                <circle
                  r={isSelected || isHovered ? 14 : 10}
                  fill={color}
                  stroke={isSelected ? '#fff' : 'transparent'}
                  strokeWidth={isSelected ? 2 : 0}
                  opacity={0.9}
                />
                <text
                  dy="24"
                  textAnchor="middle"
                  className="select-none text-xs"
                  fill="#94a3b8"
                  fontSize="11"
                >
                  {node.label.length > 18
                    ? `${node.label.slice(0, 16)}…`
                    : node.label}
                </text>
                <title>{`${node.kind}: ${node.label}`}</title>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
