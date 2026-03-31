'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertCircle, FileJson, FileText, Globe, Loader2 } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs } from '@/components/ui/tabs';
import { getApiErrorMessage, getSessionReport } from '@/lib/api';
import type {
  ResearchOutputFormat,
  ResearchRunStatus,
  SessionReportResponse,
} from '@/types/telemetry';

interface SessionReportProps {
  sessionId: string;
  runStatus: ResearchRunStatus | null;
  hasReport?: boolean;
}

const REPORT_FORMATS: Array<{
  value: ResearchOutputFormat;
  label: string;
  icon: typeof FileText;
}> = [
  { value: 'markdown', label: 'Markdown', icon: FileText },
  { value: 'json', label: 'JSON', icon: FileJson },
  { value: 'html', label: 'HTML', icon: Globe },
];

type ReportCache = Partial<Record<ResearchOutputFormat, SessionReportResponse>>;

function formatLabel(format: ResearchOutputFormat): string {
  return REPORT_FORMATS.find((item) => item.value === format)?.label ?? format.toUpperCase();
}

function renderReportContent(
  report: SessionReportResponse,
  selectedFormat: ResearchOutputFormat
): React.ReactNode {
  if (selectedFormat === 'json') {
    try {
      const parsed = JSON.parse(report.content);
      return (
        <pre className="overflow-auto rounded-2xl bg-background p-5 text-sm text-foreground">
          {JSON.stringify(parsed, null, 2)}
        </pre>
      );
    } catch {
      return (
        <pre className="overflow-auto rounded-2xl bg-background p-5 text-sm text-foreground">
          {report.content}
        </pre>
      );
    }
  }

  if (selectedFormat === 'html') {
    return (
      <div
        className="prose prose-invert max-w-none prose-headings:text-foreground prose-a:text-primary prose-strong:text-foreground"
        dangerouslySetInnerHTML={{ __html: report.content }}
      />
    );
  }

  return (
    <ReactMarkdown
      className="prose prose-invert max-w-none prose-headings:text-foreground prose-a:text-primary prose-strong:text-foreground prose-pre:rounded-2xl"
      remarkPlugins={[remarkGfm]}
    >
      {report.content}
    </ReactMarkdown>
  );
}

function WaitingCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Loader2;
  title: string;
  body: string;
}) {
  return (
    <Card className="border-dashed border-slate-300/90 shadow-sm">
      <CardContent className="flex min-h-[360px] flex-col items-center justify-center gap-4">
        <Icon className={Icon === Loader2 ? 'h-8 w-8 animate-spin text-slate-500' : 'h-8 w-8 text-slate-500'} />
        <div className="space-y-1 text-center">
          <p className="text-lg font-medium text-slate-900">{title}</p>
          <p className="text-sm text-muted-foreground">{body}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function ReportStateAlert({
  variant,
  icon: Icon,
  title,
  body,
}: {
  variant: 'warning' | 'destructive';
  icon: typeof AlertCircle;
  title: string;
  body: string;
}) {
  return (
    <Card className="shadow-sm">
      <CardContent className="p-6">
        <Alert className="flex min-h-[300px] items-center justify-center" variant={variant}>
          <div className="flex max-w-lg flex-col items-center gap-4 text-center">
            <Icon className="h-8 w-8" />
            <div className="space-y-2">
              <AlertTitle className="text-base">{title}</AlertTitle>
              <AlertDescription>{body}</AlertDescription>
            </div>
          </div>
        </Alert>
      </CardContent>
    </Card>
  );
}

export function SessionReport({ sessionId, runStatus, hasReport }: SessionReportProps) {
  const [selectedFormat, setSelectedFormat] = useState<ResearchOutputFormat>('markdown');
  const [reportsByFormat, setReportsByFormat] = useState<ReportCache>({});
  const [loadingFormat, setLoadingFormat] = useState<ResearchOutputFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedReport = reportsByFormat[selectedFormat] ?? null;

  useEffect(() => {
    setSelectedFormat('markdown');
    setReportsByFormat({});
    setLoadingFormat(null);
    setError(null);
  }, [sessionId]);

  useEffect(() => {
    if (
      runStatus === 'queued' ||
      runStatus === 'running' ||
      runStatus === 'failed' ||
      runStatus === 'cancelled' ||
      hasReport === false ||
      selectedReport
    ) {
      return;
    }

    let mounted = true;
    setLoadingFormat(selectedFormat);
    setError(null);

    getSessionReport(sessionId, selectedFormat)
      .then((response) => {
        if (!mounted) {
          return;
        }
        setReportsByFormat((current) => ({
          ...current,
          [selectedFormat]: response,
        }));
      })
      .catch((requestError) => {
        if (!mounted) {
          return;
        }
        setError(getApiErrorMessage(requestError, 'Failed to load report.'));
      })
      .finally(() => {
        if (mounted) {
          setLoadingFormat((current) => (current === selectedFormat ? null : current));
        }
      });

    return () => {
      mounted = false;
    };
  }, [hasReport, runStatus, selectedFormat, selectedReport, sessionId]);

  if (runStatus === 'queued' || runStatus === 'running') {
    return (
      <WaitingCard
        icon={Loader2}
        title={runStatus === 'queued' ? 'Report queue is warming up' : 'Research is still running'}
        body="The page stays lightweight while the report is being finalized. It will appear here as soon as the run completes."
      />
    );
  }

  if (runStatus === 'failed') {
    return (
      <ReportStateAlert
        body="No report is available because the run did not complete successfully."
        icon={AlertCircle}
        title="Research run failed"
        variant="destructive"
      />
    );
  }

  if (runStatus === 'cancelled') {
    return (
      <ReportStateAlert
        body="The session stopped before a final report artifact was produced."
        icon={AlertCircle}
        title="Run was cancelled"
        variant="warning"
      />
    );
  }

  if (hasReport === false) {
    return (
      <Card className="border-dashed border-slate-300/90 shadow-sm">
        <CardContent className="flex min-h-[360px] flex-col items-center justify-center gap-4">
          <Alert className="flex min-h-[300px] items-center justify-center" variant="default">
            <div className="flex max-w-lg flex-col items-center gap-4 text-center">
              <FileText className="h-8 w-8 text-slate-400" />
              <div className="space-y-2">
                <AlertTitle className="text-base">No report artifact available</AlertTitle>
                <AlertDescription>
                  This session does not currently expose a rendered report.
                </AlertDescription>
              </div>
            </div>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-slate-200/80 shadow-sm">
      <CardHeader className="gap-4 border-b bg-[linear-gradient(135deg,rgba(15,23,42,0.04),rgba(56,189,248,0.12))]">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-sky-700" />
                Report Workspace
              </CardTitle>
              <Badge variant="secondary">{formatLabel(selectedFormat)}</Badge>
              {loadingFormat === selectedFormat ? <Badge variant="outline">Loading</Badge> : null}
            </div>
            <p className="text-sm text-muted-foreground">
              Report-first view for session{' '}
              <span className="font-mono text-xs text-foreground">{sessionId}</span>. Formats are
              fetched and cached independently so switching tabs stays cheap after the first load.
            </p>
          </div>

          <div className="flex flex-col gap-2 xl:items-end">
            <Tabs
              tabs={REPORT_FORMATS.map((format) => ({
                value: format.value,
                label: format.label,
                icon: format.icon,
              }))}
              value={selectedFormat}
              onValueChange={(value) => setSelectedFormat(value as ResearchOutputFormat)}
            />
            <p className="text-xs text-muted-foreground">
              Markdown is optimized for the initial render. JSON and HTML are loaded on demand.
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="min-h-[360px] p-6">
        {loadingFormat === selectedFormat && !selectedReport ? (
          <Alert className="flex min-h-[300px] items-center justify-center border-dashed" variant="default">
            <div className="flex flex-col items-center gap-4 text-center">
              <Loader2 className="h-7 w-7 animate-spin text-slate-500" />
              <AlertDescription>
                Loading {formatLabel(selectedFormat).toLowerCase()} report…
              </AlertDescription>
            </div>
          </Alert>
        ) : null}

        {!selectedReport && error ? (
          <Alert className="flex items-start gap-3" variant="destructive">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <AlertTitle>Report error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </div>
          </Alert>
        ) : null}

        {!selectedReport && !error && loadingFormat !== selectedFormat ? (
          <Alert className="flex min-h-[300px] items-center justify-center border-dashed" variant="default">
            <div className="flex max-w-lg flex-col items-center gap-3 text-center">
              <FileText className="h-8 w-8 text-slate-400" />
              <div className="space-y-1">
                <AlertTitle>No report available</AlertTitle>
                <AlertDescription>
                  The report may still be finalizing. Try refreshing once the session reaches a
                  completed state.
                </AlertDescription>
              </div>
            </div>
          </Alert>
        ) : null}

        {selectedReport ? renderReportContent(selectedReport, selectedFormat) : null}
      </CardContent>
    </Card>
  );
}
