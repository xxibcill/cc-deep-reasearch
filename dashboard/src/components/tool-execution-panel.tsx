import { ToolExecution } from '@/types/telemetry';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

function statusVariant(status: string): 'success' | 'warning' | 'destructive' | 'secondary' {
  if (status === 'completed' || status === 'success') {
    return 'success';
  }
  if (status === 'failed' || status === 'error') {
    return 'destructive';
  }
  if (status === 'timeout') {
    return 'warning';
  }
  return 'secondary';
}

export function ToolExecutionPanel({
  executions,
  selectedExecutionId,
  onSelectExecution,
}: {
  executions: ToolExecution[];
  selectedExecutionId: string | null;
  onSelectExecution: (execution: ToolExecution) => void;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Tool Executions</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-[28rem] space-y-3">
          <div className="space-y-3">
            {executions.map((execution) => (
              <button
                key={execution.id}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${
                  execution.id === selectedExecutionId
                    ? 'border-primary/35 bg-surface-raised/72 shadow-card'
                    : 'border-border/70 bg-surface/56 hover:bg-surface-raised/56'
                }`}
                onClick={() => onSelectExecution(execution)}
                type="button"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="font-semibold">{execution.toolName}</div>
                  <Badge variant={statusVariant(execution.status)}>{execution.status}</Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                  {execution.agentId} • {execution.phase ?? 'No phase'} • {execution.duration} ms
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-foreground/82">{execution.summary}</p>
              </button>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
