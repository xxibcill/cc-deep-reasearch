'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';

import { TelemetryEvent, WorkflowEdge, WorkflowNode } from '@/types/telemetry';

const STATUS_COLORS: Record<string, string> = {
  running: '#2563eb',
  started: '#2563eb',
  selected: '#0f766e',
  completed: '#16a34a',
  success: '#16a34a',
  failed: '#dc2626',
  error: '#dc2626',
  timeout: '#f59e0b',
  fallback: '#7c3aed',
  unknown: '#64748b',
  pending: '#94a3b8',
  scheduled: '#0ea5e9',
  recorded: '#475569',
};

function layoutNodes(nodes: WorkflowNode[]) {
  const groups = new Map<WorkflowNode['type'], WorkflowNode[]>();
  for (const node of nodes) {
    const list = groups.get(node.type) ?? [];
    list.push(node);
    groups.set(node.type, list);
  }

  const levels: WorkflowNode['type'][] = ['session', 'phase', 'agent'];
  const positioned = new Map<string, { x: number; y: number }>();

  levels.forEach((level, index) => {
    const group = groups.get(level) ?? [];
    group.forEach((node, nodeIndex) => {
      positioned.set(node.id, {
        x: 160 + nodeIndex * 220,
        y: 100 + index * 180,
      });
    });
  });

  return positioned;
}

export function WorkflowGraph({
  nodes,
  edges,
  selectedEventId,
  eventIndex,
  onSelectEvent,
}: {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedEventId: string | null;
  eventIndex: Map<string, TelemetryEvent>;
  onSelectEvent: (event: TelemetryEvent | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const positions = useMemo(() => layoutNodes(nodes), [nodes]);

  useEffect(() => {
    const element = svgRef.current;
    if (!element) {
      return;
    }

    const svg = d3.select<SVGSVGElement, unknown>(element);
    svg.selectAll('*').remove();

    const width = 980;
    const height = 520;
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const root = svg.append('g');
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.6, 2.2])
        .on('zoom', (event) => root.attr('transform', event.transform.toString()))
    );

    root
      .append('rect')
      .attr('width', width)
      .attr('height', height)
      .attr('fill', 'transparent');

    root
      .selectAll('path.edge')
      .data(edges)
      .enter()
      .append('path')
      .attr('class', 'edge')
      .attr('d', (edge) => {
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) {
          return '';
        }
        const midY = (source.y + target.y) / 2;
        return `M ${source.x} ${source.y} C ${source.x} ${midY}, ${target.x} ${midY}, ${target.x} ${target.y}`;
      })
      .attr('fill', 'none')
      .attr('stroke', (edge) => STATUS_COLORS[edge.status] ?? STATUS_COLORS.unknown)
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', (edge) => (edge.status === 'running' || edge.status === 'started' ? '8 6' : '0'))
      .attr('opacity', 0.7);

    const nodeGroup = root
      .selectAll('g.node')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .attr('transform', (node) => {
        const position = positions.get(node.id);
        return `translate(${position?.x ?? 0}, ${position?.y ?? 0})`;
      })
      .style('cursor', 'pointer')
      .on('click', (_event, node) => {
        const eventId = node.latestEventId ?? node.eventIds.at(-1) ?? null;
        onSelectEvent(eventId ? eventIndex.get(eventId) ?? null : null);
      });

    nodeGroup
      .append('circle')
      .attr('r', (node) => (node.type === 'session' ? 30 : 24))
      .attr('fill', (node) => STATUS_COLORS[node.status] ?? STATUS_COLORS.unknown)
      .attr('stroke', (node) =>
        node.latestEventId && node.latestEventId === selectedEventId ? '#fbbf24' : '#44403c'
      )
      .attr('stroke-width', (node) => (node.latestEventId === selectedEventId ? 4 : 2));

    nodeGroup
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 48)
      .attr('font-size', 13)
      .attr('font-weight', 600)
      .attr('fill', '#f5f5f4')
      .text((node) => node.name);

    nodeGroup
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 64)
      .attr('font-size', 11)
      .attr('fill', '#b0a89c')
      .text((node) => node.status);
  }, [edges, eventIndex, nodes, onSelectEvent, positions, selectedEventId]);

  return <svg ref={svgRef} className="h-[520px] w-full rounded-xl bg-surface" />;
}
