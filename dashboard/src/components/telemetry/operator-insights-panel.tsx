'use client';

import { AlertCircle, ArrowRight, CheckCircle2, FileText, HelpCircle, List, Search, Zap } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { OperatorInsight, InsightStatus, OperatorInsightAction } from '@/types/telemetry';

const STATUS_CONFIG: Record<InsightStatus, { icon: typeof AlertCircle; className: string; bgClass: string }> = {
  healthy: {
    icon: CheckCircle2,
    className: 'text-success',
    bgClass: 'bg-success-muted/20',
  },
  warning: {
    icon: AlertCircle,
    className: 'text-warning',
    bgClass: 'bg-warning-muted/20',
  },
  error: {
    icon: AlertCircle,
    className: 'text-error',
    bgClass: 'bg-error-muted/20',
  },
  unknown: {
    icon: HelpCircle,
    className: 'text-muted-foreground',
    bgClass: 'bg-surface-raised/40',
  },
};

const ACTION_ICONS: Record<OperatorInsightAction['actionType'], typeof List> = {
  inspect_tool_failures: Zap,
  review_llm_reasoning: Search,
  open_report: FileText,
  view_phases: List,
  view_decisions: List,
  compare_runs: ArrowRight,
};

interface OperatorInsightsPanelProps {
  insights: OperatorInsight[];
  className?: string;
  onAction?: (action: OperatorInsightAction) => void;
}

export function OperatorInsightsPanel({ insights, className, onAction }: OperatorInsightsPanelProps) {
  const router = useRouter();

  const handleAction = (action: OperatorInsightAction) => {
    if (onAction) {
      onAction(action);
      return;
    }

    switch (action.actionType) {
      case 'inspect_tool_failures':
        router.push('#tools');
        break;
      case 'review_llm_reasoning':
        router.push('#llm');
        break;
      case 'open_report':
        router.push('report');
        break;
      case 'view_phases':
        router.push('#graph');
        break;
      case 'view_decisions':
        router.push('#decision_graph');
        break;
      case 'compare_runs':
        router.push('/compare');
        break;
    }
  };

  if (insights.length === 0) {
    return null;
  }

  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardHeader className="border-b border-border/60 bg-surface-raised/45 py-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Search className="h-4 w-4 text-primary" />
          Operator Insights
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 p-3">
        {insights.map((insight) => {
          const config = STATUS_CONFIG[insight.status];
          const StatusIcon = config.icon;

          return (
            <div
              key={insight.id}
              className={cn(
                'rounded-lg border p-3',
                config.bgClass,
                insight.status === 'error' && 'border-error/25',
                insight.status === 'warning' && 'border-warning/25',
                insight.status === 'healthy' && 'border-success/25',
                insight.status === 'unknown' && 'border-border/70'
              )}
            >
              <div className="flex items-start gap-2">
                <StatusIcon className={cn('mt-0.5 h-4 w-4 flex-shrink-0', config.className)} />
                <div className="flex-1 space-y-1.5">
                  <p className="text-sm font-medium leading-tight text-foreground">{insight.title}</p>
                  <p className="text-xs text-muted-foreground">{insight.description}</p>
                  {insight.actions.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1.5">
                      {insight.actions.map((action, idx) => {
                        const ActionIcon = ACTION_ICONS[action.actionType] ?? ArrowRight;
                        return (
                          <Button
                            key={idx}
                            size="sm"
                            variant="outline"
                            className="h-6 gap-1 px-2 text-xs"
                            onClick={() => handleAction(action)}
                          >
                            <ActionIcon className="h-3 w-3" />
                            {action.label}
                          </Button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
