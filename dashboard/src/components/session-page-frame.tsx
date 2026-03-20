'use client';

import Link from 'next/link';
import { FileText, Radar, ScrollText, TimerReset } from 'lucide-react';

import { RunStatusSummary } from '@/components/run-status-summary';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useSessionRoute } from '@/hooks/useSessionRoute';
import { runStatusBadgeVariant } from '@/lib/session-route';
import { cn } from '@/lib/utils';
import type { ResearchRunStatus, Session } from '@/types/telemetry';

type SessionView = 'details' | 'monitor' | 'report';

interface SessionPageFrameProps {
  routeId: string;
  view: SessionView;
  title: string;
  description: string;
  children: (context: {
    sessionId: string;
    runStatus: ResearchRunStatus | null;
    sessionSummary: Session | null;
  }) => React.ReactNode;
}

const viewMeta: Record<
  SessionView,
  { icon: typeof ScrollText; label: string; href: (sessionId: string) => string }
> = {
  details: {
    icon: ScrollText,
    label: 'Details',
    href: (sessionId) => `/session/${sessionId}`,
  },
  monitor: {
    icon: Radar,
    label: 'Monitor',
    href: (sessionId) => `/session/${sessionId}/monitor`,
  },
  report: {
    icon: FileText,
    label: 'Report',
    href: (sessionId) => `/session/${sessionId}/report`,
  },
};

export function SessionPageFrame({
  routeId,
  view,
  title,
  description,
  children,
}: SessionPageFrameProps) {
  const {
    isRunRoute,
    resolvedSessionId,
    runStatus,
    sessionSummary,
    sessionError,
    setResolvedSessionId,
    setRunStatus,
    handleRunStatusLoaded,
  } = useSessionRoute(routeId);

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 px-4 py-6">
      {isRunRoute ? (
        <RunStatusSummary
          runId={routeId}
          onSessionIdResolved={setResolvedSessionId}
          onStatusChange={setRunStatus}
          onStatusLoaded={handleRunStatusLoaded}
        />
      ) : null}

      {!resolvedSessionId ? (
        <Card className="border-dashed border-slate-300/90 shadow-sm">
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Waiting for the backend to allocate a session ID before the session workspace can load.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="overflow-hidden border-slate-200/80 shadow-sm">
            <CardHeader className="gap-4 border-b bg-[linear-gradient(160deg,rgba(15,23,42,0.04),rgba(125,211,252,0.18))]">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    {(() => {
                      const Icon = viewMeta[view].icon;
                      return (
                        <CardTitle className="flex items-center gap-2">
                          <Icon className="h-5 w-5 text-sky-700" />
                          {title}
                        </CardTitle>
                      );
                    })()}
                    <Badge variant={runStatusBadgeVariant(runStatus)}>{runStatus ?? 'loading'}</Badge>
                    {sessionSummary?.hasReport ? <Badge variant="success">Report Ready</Badge> : null}
                  </div>
                  <p className="text-sm text-muted-foreground">{description}</p>
                  <p className="text-xs text-muted-foreground">
                    Session <span className="font-mono text-foreground">{resolvedSessionId}</span>
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  {(Object.entries(viewMeta) as Array<[SessionView, (typeof viewMeta)[SessionView]]>).map(
                    ([key, item]) => {
                      const Icon = item.icon;
                      const active = key === view;

                      return (
                        <Link
                          key={key}
                          href={item.href(resolvedSessionId)}
                          className={cn(
                            'inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors',
                            active
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-border bg-background hover:bg-accent hover:text-accent-foreground'
                          )}
                        >
                          <Icon className="h-4 w-4" />
                          {item.label}
                        </Link>
                      );
                    }
                  )}
                </div>
              </div>
            </CardHeader>

            {sessionError ? (
              <CardContent className="border-t bg-amber-50/80 p-4">
                <div className="flex items-start gap-3 text-sm text-amber-800">
                  <TimerReset className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{sessionError}</span>
                </div>
              </CardContent>
            ) : null}
          </Card>

          {children({
            sessionId: resolvedSessionId,
            runStatus,
            sessionSummary,
          })}
        </>
      )}
    </div>
  );
}
