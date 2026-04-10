import { useState } from 'react';
import { FileText, ChevronDown, ChevronRight, ShieldCheck, ShieldAlert } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SessionPromptMetadata } from '@/types/telemetry';

const AGENT_LABELS: Record<string, string> = {
  analyzer: 'Analyzer',
  deep_analyzer: 'Deep Analyzer',
  report_quality_evaluator: 'Report Quality Evaluator',
};

const PROMPT_PREVIEW_MAX_LENGTH = 300;

function TruncatedContent({
  content,
  label,
}: {
  content: string;
  label: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const isLong = content.length > PROMPT_PREVIEW_MAX_LENGTH;
  const displayContent = isLong && !expanded
    ? content.slice(0, PROMPT_PREVIEW_MAX_LENGTH) + '...'
    : content;

  return (
    <div className="space-y-2">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <pre className="max-h-48 overflow-auto rounded-lg border border-border/70 bg-background p-2 text-xs text-foreground whitespace-pre-wrap break-words">
        {displayContent}
      </pre>
      {isLong && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(!expanded)}
          className="h-6 px-2 text-xs"
        >
          {expanded ? (
            <>
              <ChevronDown className="mr-1 h-3 w-3" />
              Collapse
            </>
          ) : (
            <>
              <ChevronRight className="mr-1 h-3 w-3" />
              Expand full content ({content.length} chars)
            </>
          )}
        </Button>
      )}
    </div>
  );
}

function AgentOverrideCard({
  agentId,
  override,
}: {
  agentId: string;
  override: SessionPromptMetadata['effective_overrides'][string];
}) {
  const hasPrefix = Boolean(override.prompt_prefix);
  const hasSystem = Boolean(override.system_prompt);
  const agentLabel = AGENT_LABELS[agentId] || agentId;

  return (
    <div className="rounded-xl border border-border/70 space-y-3 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="default" className="bg-primary/90 text-primary-foreground">
            Override Applied
          </Badge>
          <span className="text-sm font-semibold text-foreground">{agentLabel}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5 text-success" />
          <span>Custom</span>
        </div>
      </div>
      <div className="space-y-3">
        {hasPrefix && (
          <TruncatedContent content={override.prompt_prefix!} label="Prompt Prefix Override" />
        )}
        {hasSystem && (
          <TruncatedContent content={override.system_prompt!} label="System Prompt Override" />
        )}
        {!hasPrefix && !hasSystem && (
          <p className="text-xs text-muted-foreground">No overrides recorded</p>
        )}
      </div>
    </div>
  );
}

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

  const overrideCount = Object.keys(promptMetadata.effective_overrides).length;
  const defaultCount = promptMetadata.default_prompts_used.length;
  const totalAgents = overrideCount + defaultCount;
  const hasAnyOverrides = promptMetadata.overrides_applied;

  return (
    <Card className="h-full">
      <CardHeader className="border-b border-border/60">
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Prompt Audit
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {hasAnyOverrides ? (
            <>
              <Badge variant="default" className="bg-primary/90 text-primary-foreground">
                {overrideCount} Override{overrideCount !== 1 ? 's' : ''} Applied
              </Badge>
              {defaultCount > 0 && (
                <Badge variant="outline">
                  {defaultCount} Using Default
                </Badge>
              )}
            </>
          ) : (
            <Badge variant="secondary">
              <ShieldCheck className="mr-1.5 h-3 w-3" />
              All Default Prompts
            </Badge>
          )}
        </div>

        <div className="text-xs text-muted-foreground">
          {totalAgents} total agent{totalAgents !== 1 ? 's' : ''} in session
        </div>

        {hasAnyOverrides && Object.keys(promptMetadata.effective_overrides).length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground border-b border-border/50 pb-2">
              Overridden Agents
            </h4>
            {Object.entries(promptMetadata.effective_overrides).map(([agentId, override]) => (
              <AgentOverrideCard key={agentId} agentId={agentId} override={override} />
            ))}
          </div>
        )}

        {promptMetadata.default_prompts_used.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground border-b border-border/50 pb-2">
              Agents Using Default Prompts
            </h4>
            <div className="flex flex-wrap gap-2">
              {promptMetadata.default_prompts_used.map((agentId) => (
                <Badge key={agentId} variant="outline" className="bg-muted/40">
                  <ShieldCheck className="mr-1.5 h-3 w-3 text-muted-foreground" />
                  {AGENT_LABELS[agentId] || agentId}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {!hasAnyOverrides && (
          <Alert variant="default" className="bg-muted/50 border-border/70">
            <ShieldCheck className="h-4 w-4" />
            <AlertTitle className="text-sm">Baseline Run</AlertTitle>
            <AlertDescription className="text-xs">
              No prompt overrides were applied to this session. All agents used their default prompts.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
