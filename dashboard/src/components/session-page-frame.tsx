'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { FileText, Radar, ScrollText, TimerReset } from 'lucide-react';

import { RunStatusSummary } from '@/components/run-status-summary';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { useNotifications } from '@/components/ui/notification-center';
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
    label: 'Overview',
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

function WorkspaceNav({
  sessionId,
  currentView,
}: {
  sessionId: string;
  currentView: SessionView;
}) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Session workspace views"
      className="flex items-center gap-1 rounded-[0.85rem] border border-border/60 bg-muted/40 p-1"
    >
      {(Object.entries(viewMeta) as Array<[SessionView, (typeof viewMeta)[SessionView]]>).map(
        ([key, item]) => {
          const Icon = item.icon;
          const isActive = pathname === item.href(sessionId);

          return (
            <Link
              key={key}
              href={item.href(sessionId)}
              className={cn(
                buttonVariants({
                  variant: 'ghost',
                  size: 'sm',
                }),
                'gap-2 px-3 py-1.5 text-sm font-medium transition-all',
                isActive
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        }
      )}
    </nav>
  );
}

export function SessionPageFrame({
  routeId,
  view,
  title,
  description,
  children,
}: SessionPageFrameProps) {
  const { notify } = useNotifications();
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
  const previousRunStatusRef = useRef<ResearchRunStatus | null>(null);

  const showRunStatus = isRunRoute && !resolvedSessionId;

  useEffect(() => {
    const previousStatus = previousRunStatusRef.current;
    previousRunStatusRef.current = runStatus;

    if (!isRunRoute || !runStatus || !previousStatus || previousStatus === runStatus) {
      return;
    }

    if (previousStatus !== 'queued' && previousStatus !== 'running') {
      return;
    }

    if (!resolvedSessionId) {
      return;
    }

    if (runStatus === 'completed') {
      notify({
        variant: 'success',
        title: 'Run completed',
        description: `Session ${resolvedSessionId} finished successfully and is ready for follow-up review.`,
        actions: [
          { label: 'Open monitor', href: `/session/${resolvedSessionId}/monitor` },
          { label: 'Open report', href: `/session/${resolvedSessionId}/report` },
        ],
      });
      return;
    }

    if (runStatus === 'failed') {
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Run failed',
        description: 'The run ended in failure. Review the monitor and session history before retrying.',
        actions: [{ label: 'Open monitor', href: `/session/${resolvedSessionId}/monitor` }],
      });
      return;
    }

    if (runStatus === 'cancelled') {
      notify({
        variant: 'warning',
        persistent: true,
        title: 'Run cancelled',
        description: 'The run stopped before completion. Historical telemetry remains available for review.',
        actions: [{ label: 'Open monitor', href: `/session/${resolvedSessionId}/monitor` }],
      });
    }
  }, [isRunRoute, notify, resolvedSessionId, runStatus]);

  return (
    <div className="mx-auto max-w-content space-y-5 px-page-x py-page-y">
      {showRunStatus ? (
        <RunStatusSummary
          runId={routeId}
          onSessionIdResolved={setResolvedSessionId}
          onStatusChange={setRunStatus}
          onStatusLoaded={handleRunStatusLoaded}
        />
      ) : null}

      {!resolvedSessionId && !showRunStatus ? (
        <Card className="border-dashed">
          <CardContent className="flex min-h-[180px] items-center justify-center py-10">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-foreground" />
              <span>Loading session workspace...</span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <Breadcrumb
            items={[
              { label: 'Research', href: '/' },
              {
                label: resolvedSessionId
                  ? `Session ${resolvedSessionId.slice(0, 8)}`
                  : 'Session',
                href: resolvedSessionId ? `/session/${resolvedSessionId}` : undefined,
              },
              { label: viewMeta[view].label },
            ]}
          />

          <section className="rounded-[1.35rem] border border-border/75 bg-gradient-to-b from-background to-muted/20 shadow-sm">
            <div className="flex flex-col gap-5 border-b border-border/60 px-6 py-5">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-3">
                    {(() => {
                      const Icon = viewMeta[view].icon;
                      return (
                        <CardTitle className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight">
                          <Icon className="h-5 w-5 text-primary" />
                          {title}
                        </CardTitle>
                      );
                    })()}
                    <Badge variant={runStatusBadgeVariant(runStatus)} className="px-2.5 py-0.5">
                      {runStatus ?? 'loading'}
                    </Badge>
                    {sessionSummary?.hasReport ? (
                      <Badge variant="success" className="px-2.5 py-0.5">
                        Report ready
                      </Badge>
                    ) : null}
                  </div>
                  <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                    {description}
                  </p>
                </div>

                <div className="flex flex-col items-start gap-3 xl:items-end">
                  {resolvedSessionId && (
                    <WorkspaceNav sessionId={resolvedSessionId} currentView={view} />
                  )}
                  {resolvedSessionId && (
                    <p className="font-mono text-xs tracking-wider text-muted-foreground">
                      ID: <span className="text-foreground">{resolvedSessionId}</span>
                    </p>
                  )}
                </div>
              </div>
            </div>

            {sessionError ? (
              <div className="border-t border-border/60 px-6 py-4">
                <Alert className="flex items-start gap-3" variant="warning">
                  <TimerReset className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="space-y-1">
                    <AlertTitle>Session resolving</AlertTitle>
                    <AlertDescription>{sessionError}</AlertDescription>
                  </div>
                </Alert>
              </div>
            ) : null}

            <div className="p-6">
              {resolvedSessionId
                ? children({ sessionId: resolvedSessionId, runStatus, sessionSummary })
                : null}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
