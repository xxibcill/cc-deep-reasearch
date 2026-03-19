'use client';

import { useEffect, useState } from 'react';
import { FileText, Loader2, AlertCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs } from '@/components/ui/tabs';
import { getSessionReport } from '@/lib/api';
import type {
  ResearchOutputFormat,
  ResearchRunStatus,
  SessionReportResponse,
} from '@/types/telemetry';

interface SessionReportProps {
  sessionId: string;
  runStatus: ResearchRunStatus | null;
}

function formatReportContent(content: string, format: ResearchOutputFormat): React.ReactNode {
  if (format === 'json') {
    try {
      const parsed = JSON.parse(content);
      return (
        <pre className="overflow-auto rounded-lg bg-slate-950 p-4 text-sm text-slate-100">
          {JSON.stringify(parsed, null, 2)}
        </pre>
      );
    } catch {
      return <pre className="whitespace-pre-wrap">{content}</pre>;
    }
  }

  if (format === 'html') {
    return (
      <div
        className="prose prose-sm dark:prose-invert max-w-none"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }

  // Markdown - for now just render as preformatted text
  // TODO: Add a proper markdown renderer
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
      {content}
    </div>
  );
}

export function SessionReport({ sessionId, runStatus }: SessionReportProps) {
  const [report, setReport] = useState<SessionReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<ResearchOutputFormat>('markdown');

  useEffect(() => {
    if (
      runStatus === 'queued' ||
      runStatus === 'running' ||
      runStatus === 'failed' ||
      runStatus === 'cancelled'
    ) {
      return;
    }

    let mounted = true;

    const fetchReport = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await getSessionReport(sessionId, selectedFormat);
        if (!mounted) return;
        setReport(response);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to load report');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void fetchReport();

    return () => {
      mounted = false;
    };
  }, [sessionId, runStatus, selectedFormat]);

  // Show waiting state for queued/running runs
  if (runStatus === 'queued' || runStatus === 'running') {
    return (
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
          <p className="text-lg font-medium text-muted-foreground">
            {runStatus === 'queued' ? 'Research run is queued...' : 'Research in progress...'}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Report will be available once the research completes.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Show error state for failed runs
  if (runStatus === 'failed') {
    return (
      <Card className="border-destructive bg-destructive/5">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="h-8 w-8 text-destructive mb-4" />
          <p className="text-lg font-medium text-destructive">Research run failed</p>
          <p className="text-sm text-muted-foreground mt-2">
            No report is available for failed runs.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (runStatus === 'cancelled') {
    return (
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="mb-4 h-8 w-8 text-amber-600" />
          <p className="text-lg font-medium text-amber-800">Research run was cancelled</p>
          <p className="mt-2 text-sm text-amber-700">
            No new report was produced after the run was stopped.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Loading state
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Report
          </CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            Report Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  // No report available
  if (!report) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <FileText className="h-8 w-8 text-muted-foreground mb-4" />
          <p className="text-lg font-medium text-muted-foreground">No report available</p>
          <p className="text-sm text-muted-foreground mt-2">
            The report may still be generating. Try refreshing the page.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Report
        </CardTitle>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{report.format}</Badge>
          <Tabs
            tabs={[
              { value: 'markdown', label: 'MD' },
              { value: 'json', label: 'JSON' },
              { value: 'html', label: 'HTML' },
            ]}
            value={selectedFormat}
            onValueChange={(value) => setSelectedFormat(value as ResearchOutputFormat)}
          />
        </div>
      </CardHeader>
      <CardContent>
        {formatReportContent(report.content, report.format)}
      </CardContent>
    </Card>
  );
}
