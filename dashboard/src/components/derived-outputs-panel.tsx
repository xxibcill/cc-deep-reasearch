import { useState } from 'react';
import { AlertTriangle, ArrowRight, Bug, Clock, GitBranch, Info, Lightbulb, AlertCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import type {
  ApiTelemetryEvent,
  CriticalPath,
  Decision,
  Degradation,
  Failure,
  StateChange,
} from '@/types/telemetry';

type DerivedView = 'narrative' | 'cause_chain' | 'state_changes' | 'issues';

interface DerivedOutputsPanelProps {
  narrative: ApiTelemetryEvent[];
  criticalPath: CriticalPath;
  stateChanges: StateChange[];
  decisions: Decision[];
  degradations: Degradation[];
  failures: Failure[];
  onSelectEvent: (eventId: string) => void;
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return '-';
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toLocaleTimeString();
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '-';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function NarrativeView({
  narrative,
  onSelectEvent,
}: {
  narrative: ApiTelemetryEvent[];
  onSelectEvent: (eventId: string) => void;
}) {
  if (narrative.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        No narrative events available for this session.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {narrative.map((event) => (
        <div
          key={event.event_id}
          className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 hover:bg-accent"
          onClick={() => event.event_id && onSelectEvent(event.event_id)}
        >
          <div className="mt-0.5">
            <Clock className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {formatTimestamp(event.timestamp)}
              </span>
              <Badge variant="secondary" className="text-xs">
                {event.event_type}
              </Badge>
            </div>
            <div className="mt-1 truncate font-medium">{event.name}</div>
            {event.status && (
              <div className="mt-1 text-xs text-muted-foreground">
                Status: {event.status}
                {event.duration_ms !== null && ` • ${formatDuration(event.duration_ms)}`}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function CauseChainView({
  criticalPath,
  decisions,
  onSelectEvent,
}: {
  criticalPath: CriticalPath;
  decisions: Decision[];
  onSelectEvent: (eventId: string) => void;
}) {
  const hasPath = criticalPath.path && criticalPath.path.length > 0;
  const hasDecisions = decisions.length > 0;

  if (!hasPath && !hasDecisions) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        No cause chain data available for this session.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Critical Path */}
      {hasPath && (
        <div>
          <h4 className="mb-3 flex items-center gap-2 font-semibold">
            <GitBranch className="h-4 w-4" />
            Critical Path
            <span className="text-xs font-normal text-muted-foreground">
              ({formatDuration(criticalPath.total_duration_ms)} total)
            </span>
          </h4>
          <div className="space-y-2">
            {criticalPath.path.map((step, index) => (
              <div
                key={index}
                className="flex cursor-pointer items-center gap-2 rounded-lg border p-3 hover:bg-accent"
                onClick={() => step.start_event_id && onSelectEvent(step.start_event_id)}
              >
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">
                      {step.type}
                    </Badge>
                    <span className="font-medium">{step.name || '-'}</span>
                  </div>
                  {step.duration_ms !== null && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      Duration: {formatDuration(step.duration_ms)}
                      {step.agent_id && ` • Agent: ${step.agent_id}`}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          {criticalPath.bottleneck_event && (
            <div className="mt-4 rounded-lg border border-yellow-200 bg-yellow-50 p-3">
              <div className="flex items-center gap-2 text-yellow-800">
                <AlertTriangle className="h-4 w-4" />
                <span className="font-medium">Bottleneck Detected</span>
              </div>
              <div className="mt-1 text-sm text-yellow-700">
                {criticalPath.bottleneck_event.name} took{' '}
                {formatDuration(criticalPath.bottleneck_event.duration_ms)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Decisions */}
      {hasDecisions && (
        <div>
          <h4 className="mb-3 flex items-center gap-2 font-semibold">
            <Lightbulb className="h-4 w-4" />
            Decisions ({decisions.length})
          </h4>
          <div className="space-y-2">
            {decisions.map((decision, index) => (
              <div
                key={decision.event_id || index}
                className="cursor-pointer rounded-lg border p-3 hover:bg-accent"
                onClick={() => decision.event_id && onSelectEvent(decision.event_id)}
              >
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {decision.decision_type || 'decision'}
                  </Badge>
                  {decision.confidence !== null && (
                    <span className="text-xs text-muted-foreground">
                      Confidence: {(decision.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <div className="mt-1 font-medium">
                  {decision.chosen_option || 'No option recorded'}
                </div>
                {decision.reason_code && (
                  <div className="mt-1 text-sm text-muted-foreground">
                    Reason: {decision.reason_code}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StateChangesView({
  stateChanges,
  onSelectEvent,
}: {
  stateChanges: StateChange[];
  onSelectEvent: (eventId: string) => void;
}) {
  if (stateChanges.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        No state changes recorded for this session.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {stateChanges.map((change, index) => (
        <div
          key={change.event_id || index}
          className="cursor-pointer rounded-lg border p-3 hover:bg-accent"
          onClick={() => change.event_id && onSelectEvent(change.event_id)}
        >
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {change.change_type || 'change'}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {change.state_scope} / {change.state_key}
            </span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs font-medium text-muted-foreground">Before</div>
              <pre className="mt-1 overflow-auto rounded bg-muted p-2 text-xs">
                {JSON.stringify(change.before, null, 2)}
              </pre>
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground">After</div>
              <pre className="mt-1 overflow-auto rounded bg-muted p-2 text-xs">
                {JSON.stringify(change.after, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function IssuesView({
  failures,
  degradations,
  onSelectEvent,
}: {
  failures: Failure[];
  degradations: Degradation[];
  onSelectEvent: (eventId: string) => void;
}) {
  const hasIssues = failures.length > 0 || degradations.length > 0;

  if (!hasIssues) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        No issues detected in this session.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Failures */}
      {failures.length > 0 && (
        <div>
          <h4 className="mb-3 flex items-center gap-2 font-semibold text-red-600">
            <Bug className="h-4 w-4" />
            Failures ({failures.length})
          </h4>
          <div className="space-y-2">
            {failures.map((failure, index) => (
              <div
                key={failure.event_id || index}
                className="cursor-pointer rounded-lg border border-red-200 bg-red-50 p-3 hover:bg-red-100"
                onClick={() => failure.event_id && onSelectEvent(failure.event_id)}
              >
                <div className="flex items-center gap-2">
                  <Badge variant="destructive" className="text-xs">
                    {failure.severity || 'error'}
                  </Badge>
                  <span className="font-medium">{failure.name || failure.event_type}</span>
                </div>
                {failure.error_message && (
                  <div className="mt-1 text-sm text-red-700">{failure.error_message}</div>
                )}
                <div className="mt-1 text-xs text-red-600">
                  {failure.phase && `Phase: ${failure.phase}`}
                  {failure.actor_id && ` • Actor: ${failure.actor_id}`}
                  {failure.duration_ms !== null && ` • ${formatDuration(failure.duration_ms)}`}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Degradations */}
      {degradations.length > 0 && (
        <div>
          <h4 className="mb-3 flex items-center gap-2 font-semibold text-yellow-600">
            <AlertTriangle className="h-4 w-4" />
            Degradations ({degradations.length})
          </h4>
          <div className="space-y-2">
            {degradations.map((degradation, index) => (
              <div
                key={degradation.event_id || index}
                className="cursor-pointer rounded-lg border border-yellow-200 bg-yellow-50 p-3 hover:bg-yellow-100"
                onClick={() => degradation.event_id && onSelectEvent(degradation.event_id)}
              >
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      degradation.severity === 'high'
                        ? 'destructive'
                        : degradation.severity === 'medium'
                          ? 'default'
                          : 'secondary'
                    }
                    className="text-xs"
                  >
                    {degradation.severity || 'warning'}
                  </Badge>
                  <span className="font-medium">{degradation.reason_code || 'Degradation'}</span>
                  {degradation.inferred && (
                    <Badge variant="secondary" className="text-xs">
                      Inferred
                    </Badge>
                  )}
                </div>
                {degradation.impact && (
                  <div className="mt-1 text-sm text-yellow-700">{degradation.impact}</div>
                )}
                {degradation.mitigation && (
                  <div className="mt-1 text-xs text-yellow-600">
                    Mitigation: {degradation.mitigation}
                  </div>
                )}
                <div className="mt-1 text-xs text-yellow-600">
                  Scope: {degradation.scope || 'unknown'}
                  {degradation.recoverable !== null &&
                    ` • ${degradation.recoverable ? 'Recoverable' : 'Not recoverable'}`}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function DerivedOutputsPanel({
  narrative,
  criticalPath,
  stateChanges,
  decisions,
  degradations,
  failures,
  onSelectEvent,
}: DerivedOutputsPanelProps) {
  const [activeView, setActiveView] = useState<DerivedView>('narrative');

  const views: Array<{ key: DerivedView; label: string; icon: typeof Info; count?: number }> = [
    {
      key: 'narrative',
      label: 'Narrative',
      icon: Clock,
      count: narrative.length,
    },
    {
      key: 'cause_chain',
      label: 'Cause Chain',
      icon: GitBranch,
    },
    {
      key: 'state_changes',
      label: 'State Changes',
      icon: ArrowRight,
      count: stateChanges.length,
    },
    {
      key: 'issues',
      label: 'Issues',
      icon: AlertCircle,
      count: failures.length + degradations.length,
    },
  ];

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Info className="h-5 w-5" />
          Derived Outputs
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          {views.map(({ key, label, icon: Icon, count }) => (
            <button
              key={key}
              onClick={() => setActiveView(key)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                activeView === key
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
              {count !== undefined && count > 0 && (
                <span
                  className={`ml-1 rounded-full px-1.5 py-0.5 text-xs ${
                    activeView === key
                      ? 'bg-primary-foreground/20 text-primary-foreground'
                      : 'bg-background text-foreground'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[500px] pr-4">
          {activeView === 'narrative' && (
            <NarrativeView narrative={narrative} onSelectEvent={onSelectEvent} />
          )}
          {activeView === 'cause_chain' && (
            <CauseChainView
              criticalPath={criticalPath}
              decisions={decisions}
              onSelectEvent={onSelectEvent}
            />
          )}
          {activeView === 'state_changes' && (
            <StateChangesView stateChanges={stateChanges} onSelectEvent={onSelectEvent} />
          )}
          {activeView === 'issues' && (
            <IssuesView
              failures={failures}
              degradations={degradations}
              onSelectEvent={onSelectEvent}
            />
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
