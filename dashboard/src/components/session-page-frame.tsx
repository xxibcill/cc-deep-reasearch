'use client';

import Link from 'next/link';
import { FileText, Radar, ScrollText, TimerReset } from 'lucide-react';

import { RunStatusSummary } from '@/components/run-status-summary';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { buttonVariants } from '@/components/ui/button';
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
    <div className="mx-auto max-w-content space-y-6 px-page-x py-page-y">
      <Breadcrumb
        items={[
          { label: 'Research', href: '/' },
          { label: resolvedSessionId ? `Session ${resolvedSessionId.slice(0, 8)}` : 'Session', href: resolvedSessionId ? `/session/${resolvedSessionId}` : undefined },
          { label: viewMeta[view].label },
        ]}
      />

      {isRunRoute ? (
        <RunStatusSummary
          runId={routeId}
          onSessionIdResolved={setResolvedSessionId}
          onStatusChange={setRunStatus}
          onStatusLoaded={handleRunStatusLoaded}
        />
      ) : null}

      {!resolvedSessionId ? (
        <Card className="border-dashed">
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Waiting for the backend to allocate a session ID before the session workspace can load.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="overflow-hidden">
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

                <nav
                  aria-label="Session workspace routes"
                  className="inline-flex flex-wrap gap-1 rounded-lg border bg-muted/40 p-1"
                >
                  {(Object.entries(viewMeta) as Array<[SessionView, (typeof viewMeta)[SessionView]]>).map(
                    ([key, item]) => {
                      const Icon = item.icon;
                      const active = key === view;

                      return (
                        <Link
                          key={key}
                          href={item.href(resolvedSessionId)}
                          className={cn(
                            buttonVariants({
                              variant: active ? 'default' : 'ghost',
                              size: 'sm',
                            }),
                            'gap-2',
                            active
                              ? 'shadow-sm'
                              : 'text-muted-foreground'
                          )}
                          aria-current={active ? 'page' : undefined}
                        >
                          <Icon className="h-4 w-4" />
                          {item.label}
                        </Link>
                      );
                    }
                  )}
                </nav>
              </div>
            </CardHeader>

            {sessionError ? (
              <CardContent className="border-t p-4">
                <Alert className="flex items-start gap-3" variant="warning">
                  <TimerReset className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="space-y-1">
                    <AlertTitle>Session route is still resolving</AlertTitle>
                    <AlertDescription>{sessionError}</AlertDescription>
                  </div>
                </Alert>
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
