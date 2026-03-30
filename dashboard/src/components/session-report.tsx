'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertCircle, FileJson, FileText, Globe, Loader2 } from 'lucide-react';

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
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <Card className="border-dashed border-slate-300/90 shadow-sm">
      <CardContent className="flex min-h-[360px] flex-col items-center justify-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-slate-500" />
        <div className="space-y-1 text-center">
          <p className="text-lg font-medium text-slate-900">{title}</p>
          <p className="text-sm text-muted-foreground">{body}</p>
        </div>
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
        title={runStatus === 'queued' ? 'Report queue is warming up' : 'Research is still running'}
        body="The page stays lightweight while the report is being finalized. It will appear here as soon as the run completes."
      />
    );
  }

  if (runStatus === 'failed') {
    return (
      <Card className="border-destructive bg-destructive/5 shadow-sm">
        <CardContent className="flex min-h-[360px] flex-col items-center justify-center gap-4">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <div className="space-y-1 text-center">
            <p className="text-lg font-medium text-destructive">Research run failed</p>
            <p className="text-sm text-muted-foreground">
              No report is available because the run did not complete successfully.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (runStatus === 'cancelled') {
    return (
      <Card className="border-amber-200 bg-amber-50/80 shadow-sm">
        <CardContent className="flex min-h-[360px] flex-col items-center justify-center gap-4">
          <AlertCircle className="h-8 w-8 text-amber-600" />
          <div className="space-y-1 text-center">
            <p className="text-lg font-medium text-amber-900">Run was cancelled</p>
            <p className="text-sm text-amber-800">
              The session stopped before a final report artifact was produced.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (hasReport === false) {
    return (
      <Card className="border-dashed border-slate-300/90 shadow-sm">
        <CardContent className="flex min-h-[360px] flex-col items-center justify-center gap-4">
          <FileText className="h-8 w-8 text-slate-400" />
          <div className="space-y-1 text-center">
            <p className="text-lg font-medium text-slate-900">No report artifact available</p>
            <p className="text-sm text-muted-foreground">
              This session does not currently expose a rendered report.
            </p>
          </div>
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
          <div className="flex min-h-[300px] flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-slate-300">
            <Loader2 className="h-7 w-7 animate-spin text-slate-500" />
            <p className="text-sm text-muted-foreground">
              Loading {formatLabel(selectedFormat).toLowerCase()} report…
            </p>
          </div>
        ) : null}

        {!selectedReport && error ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-5">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <p className="font-medium">Report Error</p>
            </div>
            <p className="mt-3 text-sm text-destructive">{error}</p>
          </div>
        ) : null}

        {!selectedReport && !error && loadingFormat !== selectedFormat ? (
          <div className="flex min-h-[300px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-slate-300">
            <FileText className="h-8 w-8 text-slate-400" />
            <div className="space-y-1 text-center">
              <p className="font-medium text-slate-900">No report available</p>
              <p className="text-sm text-muted-foreground">
                The report may still be finalizing. Try refreshing once the session reaches a
                completed state.
              </p>
            </div>
          </div>
        ) : null}

        {selectedReport ? renderReportContent(selectedReport, selectedFormat) : null}
      </CardContent>
    </Card>
  );
}
