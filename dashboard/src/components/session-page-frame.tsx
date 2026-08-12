'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { FileArchive, FileText, Radar, ScrollText, TimerReset } from 'lucide-react';

import { RunStatusSummary } from '@/components/run-status-summary';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { useNotifications } from '@/components/ui/notification-center';
import { useSessionRoute } from '@/hooks/useSessionRoute';
import { runStatusBadgeVariant, runStatusLabel } from '@/lib/session-route';
import { cn } from '@/lib/utils';
import type { ResearchRunStatus, Session } from '@/types/telemetry';
import { TraceBundleExportDialog } from '@/components/trace-bundle-export-dialog';

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
  workspaceId,
}: {
  workspaceId: string;
}) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Session workspace views"
      className="grid w-full grid-cols-3 items-center gap-1 rounded-[0.85rem] border border-border/60 bg-muted/40 p-1 md:flex md:w-auto"
    >
      {(Object.entries(viewMeta) as Array<[SessionView, (typeof viewMeta)[SessionView]]>).map(
        ([key, item]) => {
          const Icon = item.icon;
          const isActive = pathname === item.href(workspaceId);

          return (
            <Link
              key={key}
              href={item.href(workspaceId)}
              className={cn(
                buttonVariants({
                  variant: 'ghost',
                  size: 'sm',
                }),
                'min-h-11 min-w-0 gap-1 px-2 py-1.5 text-sm font-medium transition-all md:gap-2 md:px-3',
                isActive
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
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
    controlRunId,
    runStatus,
    sessionSummary,
    sessionError,
    setResolvedSessionId,
    setRunStatus,
    handleRunStatusLoaded,
  } = useSessionRoute(routeId);
  const previousRunStatusRef = useRef<ResearchRunStatus | null>(null);
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);

  const isActiveRun = runStatus === 'queued' || runStatus === 'running';
  const runIdForControls = isRunRoute ? routeId : controlRunId;
  const showRunStatus =
    Boolean(runIdForControls) &&
    ((isRunRoute && !resolvedSessionId) || isActiveRun);
  const lifecycleStatusLabel = runStatusLabel(runStatus);
  const workspaceRouteId = isRunRoute ? routeId : resolvedSessionId;

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
        title: 'Run stopped',
        description: 'The run stopped before completion. Historical telemetry remains available for review.',
        actions: [{ label: 'Open monitor', href: `/session/${resolvedSessionId}/monitor` }],
      });
    }
  }, [isRunRoute, notify, resolvedSessionId, runStatus]);

  return (
    <div className="mx-auto max-w-content space-y-5 px-page-x py-page-y">
      {showRunStatus && runIdForControls ? (
        <RunStatusSummary
          runId={runIdForControls}
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
                href: workspaceRouteId ? `/session/${workspaceRouteId}` : undefined,
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
                        <CardTitle
                          as="h1"
                          className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight"
                        >
                          <Icon className="h-5 w-5 text-primary" />
                          {title}
                        </CardTitle>
                      );
                    })()}
                    <Badge variant={runStatusBadgeVariant(runStatus)} className="px-2.5 py-0.5">
                      {lifecycleStatusLabel}
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
                  {view === 'monitor' && sessionSummary ? (
                    <dl className="grid max-w-3xl gap-3 rounded-xl border border-border/60 bg-background/70 p-3 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
                      <div className="min-w-0">
                        <dt className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                          Session
                        </dt>
                        <dd className="mt-1 truncate text-sm font-medium text-foreground">
                          {sessionSummary.label}
                        </dd>
                      </div>
                      {sessionSummary.query ? (
                        <div className="min-w-0">
                          <dt className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                            Research query
                          </dt>
                          <dd className="mt-1 line-clamp-2 text-sm leading-5 text-foreground">
                            {sessionSummary.query}
                          </dd>
                        </div>
                      ) : null}
                    </dl>
                  ) : null}
                </div>

                <div className="flex flex-col items-start gap-3 xl:items-end">
                  {workspaceRouteId && (
                    <div className="w-full xl:w-auto">
                      <WorkspaceNav workspaceId={workspaceRouteId} />
                    </div>
                  )}
                  {resolvedSessionId && (
                    <button
                      type="button"
                      onClick={() => setIsExportDialogOpen(true)}
                      className={buttonVariants({
                        variant: 'outline',
                        size: 'sm',
                      })}
                    >
                      <FileArchive className="mr-2 h-4 w-4" />
                      Export Bundle
                    </button>
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

      {resolvedSessionId && (
        <TraceBundleExportDialog
          sessionId={resolvedSessionId}
          hasReport={sessionSummary?.hasReport ?? false}
          open={isExportDialogOpen}
          onOpenChange={setIsExportDialogOpen}
        />
      )}
    </div>
  );
}
