'use client';

import { GitCompare, ArrowRight, ArrowLeft, Check, X, Minus } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { SessionPromptMetadata } from '@/types/telemetry';

const AGENT_LABELS: Record<string, string> = {
  analyzer: 'Analyzer',
  deep_analyzer: 'Deep Analyzer',
  report_quality_evaluator: 'Report Quality Evaluator',
};

interface PromptDiffItem {
  agentId: string;
  agentLabel: string;
  status: 'added' | 'removed' | 'changed' | 'unchanged';
  sessionAOverrides?: {
    prompt_prefix?: string | null;
    system_prompt?: string | null;
  };
  sessionBOverrides?: {
    prompt_prefix?: string | null;
    system_prompt?: string | null;
  };
}

function truncateText(text: string, maxLength: number = 150): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

function compareOverrideValues(
  valA: string | null | undefined,
  valB: string | null | undefined
): boolean {
  const a = valA?.trim() ?? '';
  const b = valB?.trim() ?? '';
  return a === b;
}

export function computePromptDiff(
  sessionA: SessionPromptMetadata | undefined,
  sessionB: SessionPromptMetadata | undefined
): PromptDiffItem[] {
  const allAgents = new Set<string>();
  
  if (sessionA?.effective_overrides) {
    Object.keys(sessionA.effective_overrides).forEach((a) => allAgents.add(a));
  }
  if (sessionB?.effective_overrides) {
    Object.keys(sessionB.effective_overrides).forEach((a) => allAgents.add(a));
  }
  if (sessionA?.default_prompts_used) {
    sessionA.default_prompts_used.forEach((a) => allAgents.add(a));
  }
  if (sessionB?.default_prompts_used) {
    sessionB.default_prompts_used.forEach((a) => allAgents.add(a));
  }

  const results: PromptDiffItem[] = [];

  for (const agentId of allAgents) {
    const agentLabel = AGENT_LABELS[agentId] || agentId;
    const overridesA = sessionA?.effective_overrides?.[agentId];
    const overridesB = sessionB?.effective_overrides?.[agentId];
    const hasOverrideA = Boolean(overridesA?.prompt_prefix || overridesA?.system_prompt);
    const hasOverrideB = Boolean(overridesB?.prompt_prefix || overridesB?.system_prompt);

    const prefixChanged = !compareOverrideValues(overridesA?.prompt_prefix, overridesB?.prompt_prefix);
    const systemChanged = !compareOverrideValues(overridesA?.system_prompt, overridesB?.system_prompt);

    let status: PromptDiffItem['status'];
    if (!hasOverrideA && hasOverrideB) {
      status = 'added';
    } else if (hasOverrideA && !hasOverrideB) {
      status = 'removed';
    } else if (prefixChanged || systemChanged) {
      status = 'changed';
    } else {
      status = 'unchanged';
    }

    results.push({
      agentId,
      agentLabel,
      status,
      sessionAOverrides: hasOverrideA ? overridesA : undefined,
      sessionBOverrides: hasOverrideB ? overridesB : undefined,
    });
  }

  return results.sort((a, b) => a.agentLabel.localeCompare(b.agentLabel));
}

interface PromptDiffCardProps {
  sessionA: SessionPromptMetadata | undefined;
  sessionB: SessionPromptMetadata | undefined;
  sessionALabel: string;
  sessionBLabel: string;
}

export function PromptDiffCard({
  sessionA,
  sessionB,
  sessionALabel,
  sessionBLabel,
}: PromptDiffCardProps) {
  const diff = computePromptDiff(sessionA, sessionB);
  
  const hasAnyOverridesA = sessionA?.overrides_applied ?? false;
  const hasAnyOverridesB = sessionB?.overrides_applied ?? false;
  const hasChanges = diff.some((item) => item.status !== 'unchanged');
  
  const addedCount = diff.filter((d) => d.status === 'added').length;
  const removedCount = diff.filter((d) => d.status === 'removed').length;
  const changedCount = diff.filter((d) => d.status === 'changed').length;
  const unchangedCount = diff.filter((d) => d.status === 'unchanged').length;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border/70">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 text-sm text-primary">
            <GitCompare className="h-4 w-4" />
            <span className="font-display text-[0.86rem] uppercase tracking-[0.14em]">
              Prompt Configuration
            </span>
          </div>
          {hasChanges ? (
            <Badge variant="warning">Differences Found</Badge>
          ) : (
            <Badge variant="outline">Identical</Badge>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground mt-1">
          <span>{sessionALabel}</span>
          <ArrowRight className="h-3 w-3" />
          <span>{sessionBLabel}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        {!hasAnyOverridesA && !hasAnyOverridesB ? (
          <div className="rounded-lg border border-border/70 bg-muted/40 p-4 text-sm text-muted-foreground">
            Both sessions used default prompts with no overrides.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 text-xs">
              {addedCount > 0 && (
                <Badge variant="success" className="bg-success/20 text-success">
                  +{addedCount} Added
                </Badge>
              )}
              {removedCount > 0 && (
                <Badge variant="warning" className="bg-warning/20 text-warning">
                  -{removedCount} Removed
                </Badge>
              )}
              {changedCount > 0 && (
                <Badge variant="info" className="bg-info/20 text-info">
                  ~{changedCount} Changed
                </Badge>
              )}
              {unchangedCount > 0 && (
                <Badge variant="outline" className="bg-muted/40">
                  {unchangedCount} Unchanged
                </Badge>
              )}
            </div>

            <div className="space-y-3">
              {diff.map((item) => (
                <PromptDiffItemRow key={item.agentId} item={item} />
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function PromptDiffItemRow({ item }: { item: PromptDiffItem }) {
  const statusIcon = {
    added: <Check className="h-3.5 w-3.5 text-success" />,
    removed: <X className="h-3.5 w-3.5 text-warning" />,
    changed: <ArrowRight className="h-3.5 w-3.5 text-info" />,
    unchanged: <Minus className="h-3.5 w-3.5 text-muted-foreground" />,
  };

  const statusColor = {
    added: 'border-success/30 bg-success-muted/15',
    removed: 'border-warning/30 bg-warning-muted/15',
    changed: 'border-info/30 bg-info-muted/15',
    unchanged: 'border-border/70 bg-muted/30',
  };

  return (
    <div className={`rounded-lg border p-3 ${statusColor[item.status]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-foreground">{item.agentLabel}</span>
        <div className="flex items-center gap-1.5 text-xs">
          {statusIcon[item.status]}
          <span className="capitalize text-muted-foreground">{item.status}</span>
        </div>
      </div>
      
      {(item.status === 'added' || item.status === 'removed' || item.status === 'changed') && (
        <div className="grid gap-2 text-xs">
          {(item.sessionAOverrides?.prompt_prefix || item.sessionBOverrides?.prompt_prefix) && (
            <div className="space-y-1">
              <span className="text-muted-foreground font-medium">Prompt Prefix:</span>
              <div className="flex items-center gap-2">
                {item.sessionAOverrides?.prompt_prefix && (
                  <span className="flex-1 rounded bg-background/80 p-1.5 font-mono text-muted-foreground line-through">
                    {truncateText(item.sessionAOverrides.prompt_prefix)}
                  </span>
                )}
                {item.sessionAOverrides?.prompt_prefix && item.sessionBOverrides?.prompt_prefix && (
                  <ArrowRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                )}
                {item.sessionBOverrides?.prompt_prefix && (
                  <span className="flex-1 rounded bg-background/80 p-1.5 font-mono text-foreground">
                    {truncateText(item.sessionBOverrides.prompt_prefix)}
                  </span>
                )}
              </div>
            </div>
          )}
          
          {(item.sessionAOverrides?.system_prompt || item.sessionBOverrides?.system_prompt) && (
            <div className="space-y-1">
              <span className="text-muted-foreground font-medium">System Prompt:</span>
              <div className="flex items-center gap-2">
                {item.sessionAOverrides?.system_prompt && (
                  <span className="flex-1 rounded bg-background/80 p-1.5 font-mono text-muted-foreground line-through">
                    {truncateText(item.sessionAOverrides.system_prompt)}
                  </span>
                )}
                {item.sessionAOverrides?.system_prompt && item.sessionBOverrides?.system_prompt && (
                  <ArrowRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                )}
                {item.sessionBOverrides?.system_prompt && (
                  <span className="flex-1 rounded bg-background/80 p-1.5 font-mono text-foreground">
                    {truncateText(item.sessionBOverrides.system_prompt)}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      
      {item.status === 'unchanged' && (
        <p className="text-xs text-muted-foreground">
          Using default prompts in both sessions
        </p>
      )}
    </div>
  );
}