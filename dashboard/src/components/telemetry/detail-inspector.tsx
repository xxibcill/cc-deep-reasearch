import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getStatusBadgeVariant } from '@/lib/utils';
import type {
  DecisionGraphNode,
  LLMReasoning,
  TelemetryEvent,
  ToolExecution,
} from '@/types/telemetry';

const JSON_TRUNCATE_LENGTH = 500;

function statusAccent(status: string) {
  return getStatusBadgeVariant(status) as 'success' | 'warning' | 'destructive' | 'secondary' | 'default' | 'info' | 'outline';
}

function JsonBlock({ data }: { data: Record<string, unknown> | null }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!data || Object.keys(data).length === 0) {
    return <p className="text-xs text-muted-foreground">No data available.</p>;
  }

  const json = JSON.stringify(data, null, 2);
  const isLong = json.length > JSON_TRUNCATE_LENGTH;
  const display = !expanded && isLong ? json.slice(0, JSON_TRUNCATE_LENGTH) + '...' : json;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available
    }
  };

  return (
    <div className="relative">
      <pre className="overflow-auto rounded-lg border border-border/70 bg-background p-3 text-xs text-foreground">
        {display}
      </pre>
      <div className="mt-1 flex items-center justify-between">
        {isLong && (
          <button
            className="text-xs text-primary hover:underline"
            onClick={() => setExpanded(!expanded)}
            type="button"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
        <Button
          className="ml-auto h-6 px-2 py-1 text-xs"
          onClick={handleCopy}
          size="sm"
          type="button"
          variant="ghost"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
    </div>
  );
}

function explainDecisionNode(node: DecisionGraphNode): string {
  const linkType = node.inferred ? 'inferred from related telemetry' : 'taken directly from telemetry';

  switch (node.kind) {
    case 'decision':
      return `This decision node was ${linkType} and represents a concrete branch or routing choice.`;
    case 'outcome':
      return `This outcome node shows what the selected path produced and how the decision propagated.`;
    case 'failure':
      return `This failure node highlights where the path degraded into an operator-visible error or stop condition.`;
    case 'degradation':
      return `This degradation node marks a weakened path or fallback condition that can still affect the run outcome.`;
    case 'state_change':
      return `This state-change node records a meaningful transition that followed the upstream decision path.`;
    case 'event':
    default:
      return `This event node anchors the graph to a concrete telemetry event so you can inspect the raw payload.`;
  }
}

export function DetailInspector({
  decisionNode,
  event,
  toolExecution,
  reasoning,
}: {
  decisionNode: DecisionGraphNode | null;
  event: TelemetryEvent | null;
  toolExecution: ToolExecution | null;
  reasoning: LLMReasoning | null;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Inspection</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {decisionNode && (
          <div className="space-y-3 rounded-xl border border-amber-400/25 bg-amber-500/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="font-semibold text-amber-100">{decisionNode.label}</div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{decisionNode.kind.replace(/_/g, ' ')}</Badge>
                <Badge variant="outline">{decisionNode.inferred ? 'inferred' : 'explicit'}</Badge>
                {decisionNode.severity ? (
                  <Badge variant="outline">{decisionNode.severity}</Badge>
                ) : null}
              </div>
            </div>
            <p className="text-sm text-amber-50/90">{explainDecisionNode(decisionNode)}</p>
            <div className="text-xs text-amber-50/75">
              {decisionNode.event_type ?? 'No event type'} &bull; {decisionNode.actor_id ?? 'system'}
              {' '}• seq {decisionNode.sequence_number ?? 'n/a'}
            </div>
            <JsonBlock data={decisionNode.metadata} />
          </div>
        )}
        {toolExecution && (
          <div className="space-y-3 rounded-xl border border-border/70 bg-surface/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{toolExecution.toolName}</div>
              <Badge variant={statusAccent(toolExecution.status)}>{toolExecution.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {toolExecution.agentId} &bull; {toolExecution.duration} ms &bull; {toolExecution.phase ?? 'No phase'}
            </div>
            <JsonBlock data={toolExecution.request.parameters} />
          </div>
        )}
        {reasoning && (
          <div className="space-y-3 rounded-xl border border-border/70 bg-surface/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{reasoning.operation}</div>
              <Badge variant={statusAccent(reasoning.status)}>{reasoning.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {reasoning.provider}/{reasoning.transport} &bull; {reasoning.model} &bull; {reasoning.totalTokens} tokens &bull; {reasoning.latency} ms
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <pre className="overflow-auto rounded-lg border border-border/70 bg-background p-3 text-xs text-foreground">
                {reasoning.prompt || 'No prompt preview captured.'}
              </pre>
              <pre className="overflow-auto rounded-lg border border-border/70 bg-background p-3 text-xs text-foreground">
                {reasoning.response || 'No response preview captured.'}
              </pre>
            </div>
          </div>
        )}
        {event && (
          <div className="space-y-3 rounded-xl border border-border/70 bg-surface/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{event.name}</div>
              <Badge variant={statusAccent(event.status)}>{event.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {event.eventType} &bull; {event.category} &bull; {event.agentId ?? 'system'}
            </div>
            <JsonBlock data={event.metadata} />
          </div>
        )}
        {!decisionNode && !event && !toolExecution && !reasoning && (
          <Alert className="border-dashed" variant="default">
            <AlertTitle>Nothing selected yet</AlertTitle>
            <AlertDescription>
              Select a graph node, timeline span, event row, tool execution, or LLM interaction to
              inspect structured details.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
