import { LLMReasoning } from '@/types/telemetry';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

function variant(status: string): 'success' | 'warning' | 'destructive' | 'secondary' {
  if (status === 'completed' || status === 'success') {
    return 'success';
  }
  if (status === 'failed' || status === 'error') {
    return 'destructive';
  }
  if (status === 'timeout' || status === 'fallback') {
    return 'warning';
  }
  return 'secondary';
}

export function LLMReasoningPanel({
  items,
  selectedReasoningId,
  onSelectReasoning,
}: {
  items: LLMReasoning[];
  selectedReasoningId: string | null;
  onSelectReasoning: (item: LLMReasoning) => void;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>LLM Reasoning</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-[28rem]">
          <div className="space-y-3">
            {items.map((item) => (
              <button
                key={item.id}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${
                  item.id === selectedReasoningId ? 'border-slate-900 bg-slate-50' : 'hover:bg-slate-50'
                }`}
                onClick={() => onSelectReasoning(item)}
                type="button"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="font-semibold">{item.operation}</div>
                  <Badge variant={variant(item.status)}>{item.status}</Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                  {item.agentId} • {item.provider}/{item.transport} • {item.model}
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                  <span>{item.totalTokens} tokens</span>
                  <span>{item.latency} ms</span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-slate-700">
                  {item.prompt || item.response || 'No prompt or response preview was captured for this interaction.'}
                </p>
              </button>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
