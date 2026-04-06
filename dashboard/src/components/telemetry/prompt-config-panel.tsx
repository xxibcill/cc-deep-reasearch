import { FileText } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SessionPromptMetadata } from '@/types/telemetry';

const AGENT_LABELS: Record<string, string> = {
  analyzer: 'Analyzer',
  deep_analyzer: 'Deep Analyzer',
  report_quality_evaluator: 'Report Quality Evaluator',
};

export function PromptConfigurationPanel({
  promptMetadata,
}: {
  promptMetadata?: SessionPromptMetadata;
}) {
  if (!promptMetadata) {
    return (
      <Card className="h-full">
        <CardContent className="py-10">
          <Alert variant="default">
            <AlertTitle>Prompt configuration unavailable</AlertTitle>
            <AlertDescription>
              This data is loaded from historical sessions and is not available for the current
              view.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
      <Card className="h-full">
      <CardHeader className="border-b border-border/60">
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Prompt Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge variant={promptMetadata.overrides_applied ? 'default' : 'secondary'}>
            {promptMetadata.overrides_applied ? 'Custom Prompts Applied' : 'Default Prompts'}
          </Badge>
        </div>

        {promptMetadata.overrides_applied && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium">Effective Overrides</h4>
            {Object.entries(promptMetadata.effective_overrides).map(([agentId, override]) => (
              <div key={agentId} className="rounded-xl border p-3 space-y-2">
                <div className="font-medium text-sm">
                  {AGENT_LABELS[agentId] || agentId}
                </div>
                {override.prompt_prefix && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Prompt Prefix:</span>
                    <pre className="max-h-32 overflow-auto rounded-lg border border-border/70 bg-background p-2 text-xs text-foreground">
                      {override.prompt_prefix}
                    </pre>
                  </div>
                )}
                {override.system_prompt && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">System Prompt Override:</span>
                    <pre className="max-h-32 overflow-auto rounded-lg border border-border/70 bg-background p-2 text-xs text-foreground">
                      {override.system_prompt}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {promptMetadata.default_prompts_used.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Agents Using Default Prompts</h4>
            <div className="flex flex-wrap gap-2">
              {promptMetadata.default_prompts_used.map((agentId) => (
                <Badge key={agentId} variant="outline">
                  {AGENT_LABELS[agentId] || agentId}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
