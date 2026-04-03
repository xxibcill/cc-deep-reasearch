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
          <section className="panel-shell overflow-hidden rounded-[1.45rem]">
            <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
              <div className="space-y-4">
                <p className="eyebrow">Session workspace</p>
                <div className="flex flex-wrap items-center gap-2">
                  {(() => {
                    const Icon = viewMeta[view].icon;
                    return (
                      <CardTitle className="flex items-center gap-3 text-[2.6rem]">
                        <Icon className="h-6 w-6 text-primary" />
                        {title}
                      </CardTitle>
                    );
                  })()}
                  <Badge variant={runStatusBadgeVariant(runStatus)}>{runStatus ?? 'loading'}</Badge>
                  {sessionSummary?.hasReport ? <Badge variant="success">Report ready</Badge> : null}
                </div>
                <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
                <p className="font-mono text-[0.74rem] uppercase tracking-[0.18em] text-muted-foreground">
                  Session <span className="text-foreground">{resolvedSessionId}</span>
                </p>
              </div>

              <nav
                aria-label="Session workspace routes"
                className="grid gap-2 rounded-[1.1rem] border border-border/75 bg-surface/72 p-2 sm:grid-cols-3"
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
                          'justify-start px-4',
                          !active ? 'text-muted-foreground' : undefined
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

            {sessionError ? (
              <div className="border-t border-border/70 p-4">
                <Alert className="flex items-start gap-3" variant="warning">
                  <TimerReset className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="space-y-1">
                    <AlertTitle>Session route is still resolving</AlertTitle>
                    <AlertDescription>{sessionError}</AlertDescription>
                  </div>
                </Alert>
              </div>
            ) : null}
          </section>

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
