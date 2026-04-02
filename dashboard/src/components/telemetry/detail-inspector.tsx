import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getStatusBadgeVariant } from '@/lib/utils';
import type { TelemetryEvent, ToolExecution, LLMReasoning } from '@/types/telemetry';

function statusAccent(status: string) {
  return getStatusBadgeVariant(status) as 'success' | 'warning' | 'destructive' | 'secondary' | 'default' | 'info';
}

export function DetailInspector({
  event,
  toolExecution,
  reasoning,
}: {
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
        {toolExecution && (
          <div className="space-y-3 rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{toolExecution.toolName}</div>
              <Badge variant={statusAccent(toolExecution.status)}>{toolExecution.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {toolExecution.agentId} &bull; {toolExecution.duration} ms &bull; {toolExecution.phase ?? 'No phase'}
            </div>
            <pre className="overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
              {JSON.stringify(toolExecution.request.parameters, null, 2)}
            </pre>
          </div>
        )}
        {reasoning && (
          <div className="space-y-3 rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{reasoning.operation}</div>
              <Badge variant={statusAccent(reasoning.status)}>{reasoning.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {reasoning.provider}/{reasoning.transport} &bull; {reasoning.model} &bull; {reasoning.totalTokens} tokens &bull; {reasoning.latency} ms
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <pre className="overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
                {reasoning.prompt || 'No prompt preview captured.'}
              </pre>
              <pre className="overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
                {reasoning.response || 'No response preview captured.'}
              </pre>
            </div>
          </div>
        )}
        {event && (
          <div className="space-y-3 rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{event.name}</div>
              <Badge variant={statusAccent(event.status)}>{event.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {event.eventType} &bull; {event.category} &bull; {event.agentId ?? 'system'}
            </div>
            <pre className="overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-800 dark:bg-slate-900 dark:text-slate-200">
              {JSON.stringify(event.metadata, null, 2)}
            </pre>
          </div>
        )}
        {!event && !toolExecution && !reasoning && (
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
