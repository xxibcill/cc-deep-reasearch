'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  ArrowRight,
  Archive,
  CheckCircle2,
  Database,
  FileArchive,
  FileText,
  GitBranch,
  Info,
  Package,
  XCircle,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { getSessionArtifacts, getApiErrorMessage } from '@/lib/api';
import { useNotifications } from '@/components/ui/notification-center';
import type {
  ResearchRunStatus,
  Session,
  SessionArtifactsResponse,
} from '@/types/telemetry';

interface ArtifactExplorerProps {
  sessionId: string;
  runStatus: ResearchRunStatus | null;
  sessionSummary: Session | null;
  onOpenBundleExport?: () => void;
}

type ArtifactKey = 'session_payload' | 'reports' | 'trace_bundle' | 'checkpoints';

interface ArtifactItem {
  key: ArtifactKey;
  label: string;
  icon: typeof FileText;
  description: string;
  provenance: 'direct' | 'derived';
  present: boolean;
  formats?: string[];
  count?: number;
  resumeAvailable?: boolean;
  missingReason?: string;
  href?: string;
}

function ProvenanceBadge({ provenance }: { provenance: 'direct' | 'derived' }) {
  return (
    <Badge variant={provenance === 'direct' ? 'default' : 'secondary'} className="text-xs">
      {provenance === 'direct' ? 'Generated' : 'Derived'}
    </Badge>
  );
}

function ArtifactCard({
  artifact,
  onExport,
}: {
  artifact: ArtifactItem;
  onExport?: () => void;
}) {
  const Icon = artifact.icon;
  const isMissing = !artifact.present;

  return (
    <div
      className={`relative flex flex-col gap-3 rounded-xl border p-4 transition-colors ${
        isMissing
          ? 'border-dashed border-border/50 bg-muted/20'
          : 'border-border bg-surface-raised hover:bg-surface-raised/70'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
              isMissing ? 'bg-muted' : 'bg-primary/10'
            }`}
          >
            <Icon
              className={`h-5 w-5 ${isMissing ? 'text-muted-foreground' : 'text-primary'}`}
            />
          </div>
          <div>
            <p className="font-medium text-foreground">{artifact.label}</p>
            <ProvenanceBadge provenance={artifact.provenance} />
          </div>
        </div>
        {artifact.present ? (
          <CheckCircle2 className="h-5 w-5 text-success" />
        ) : (
          <XCircle className="h-5 w-5 text-muted-foreground" />
        )}
      </div>

      <p className="text-sm text-muted-foreground">{artifact.description}</p>

      {artifact.present && artifact.formats && artifact.formats.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {artifact.formats.map((format) => (
            <Badge key={format} variant="outline" className="text-xs">
              {format}
            </Badge>
          ))}
        </div>
      )}

      {artifact.present && artifact.count !== undefined && (
        <div className="text-xs text-muted-foreground">
          {artifact.count} checkpoint{artifact.count !== 1 ? 's' : ''} available
          {artifact.resumeAvailable && (
            <span className="ml-2 text-success">• Resume-ready</span>
          )}
        </div>
      )}

      {isMissing && artifact.missingReason && (
        <p className="text-xs text-muted-foreground">{artifact.missingReason}</p>
      )}

      {artifact.present && artifact.href && (
        <div className="mt-1">
          <Link
            href={artifact.href}
            className={buttonVariants({ variant: 'ghost', size: 'sm', className: 'w-full' })}
          >
            Open
            <ArrowRight className="ml-2 h-3 w-3" />
          </Link>
        </div>
      )}

      {artifact.key === 'trace_bundle' && onExport && artifact.present && (
        <div className="mt-1">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={(e) => {
              e.preventDefault();
              onExport();
            }}
          >
            <FileArchive className="mr-2 h-3.5 w-3.5" />
            Export
          </Button>
        </div>
      )}
    </div>
  );
}

function ArtifactSummary({ artifacts }: { artifacts: ArtifactItem[] }) {
  const present = artifacts.filter((a) => a.present).length;
  const total = artifacts.length;

  if (present === total) {
    return (
      <Badge variant="success" className="gap-1.5">
        <CheckCircle2 className="h-3 w-3" />
        All artifacts available
      </Badge>
    );
  }

  if (present === 0) {
    return (
      <Badge variant="destructive" className="gap-1.5">
        <XCircle className="h-3 w-3" />
        No artifacts available
      </Badge>
    );
  }

  return (
    <Badge variant="secondary" className="gap-1.5">
      <Info className="h-3 w-3" />
      {present}/{total} artifacts available
    </Badge>
  );
}

export function ArtifactExplorer({
  sessionId,
  runStatus,
  sessionSummary,
  onOpenBundleExport,
}: ArtifactExplorerProps) {
  const { notify } = useNotifications();
  const [artifacts, setArtifacts] = useState<SessionArtifactsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isTerminal =
    runStatus === 'completed' || runStatus === 'failed' || runStatus === 'cancelled';
  const isActive = runStatus === 'running' || runStatus === 'queued';

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    getSessionArtifacts(sessionId)
      .then((data) => {
        if (!mounted) return;
        setArtifacts(data);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(getApiErrorMessage(err, 'Failed to load artifacts'));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [sessionId]);

  if (loading) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex min-h-[120px] items-center justify-center py-8">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-foreground" />
            <span>Loading artifacts...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex min-h-[120px] items-center justify-center py-8">
          <div className="text-center text-sm text-muted-foreground">
            <XCircle className="mx-auto mb-2 h-5 w-5 text-destructive" />
            <p>{error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!artifacts) {
    return null;
  }

  const artifactItems: ArtifactItem[] = [
    {
      key: 'session_payload',
      label: 'Session Payload',
      icon: Database,
      description: 'Full research data including sources and collected content',
      provenance: 'direct',
      present: artifacts.available.session_payload?.present ?? false,
      href: undefined,
    },
    {
      key: 'reports',
      label: 'Research Reports',
      icon: FileText,
      description: 'Generated research output in multiple formats',
      provenance: 'derived',
      present: artifacts.available.reports?.present ?? false,
      formats: artifacts.available.reports?.formats,
      missingReason: artifacts.missing?.reports?.reason,
      href: `/session/${sessionId}/report`,
    },
    {
      key: 'trace_bundle',
      label: 'Trace Bundle',
      icon: FileArchive,
      description: 'Portable trace with events and derived outputs',
      provenance: 'derived',
      present: artifacts.available.trace_bundle?.present ?? false,
    },
    {
      key: 'checkpoints',
      label: 'Checkpoints',
      icon: GitBranch,
      description: 'Session snapshots for potential resume',
      provenance: 'derived',
      present: artifacts.available.checkpoints?.present ?? false,
      count: artifacts.available.checkpoints?.count,
      resumeAvailable: artifacts.available.checkpoints?.resume_available,
      missingReason: artifacts.missing?.checkpoints?.reason,
    },
  ];

  const handleExportBundle = () => {
    if (onOpenBundleExport) {
      onOpenBundleExport();
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Package className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">Artifact Explorer</CardTitle>
          </div>
          <ArtifactSummary artifacts={artifactItems} />
        </div>
        <CardDescription className="mt-1">
          View all available artifacts and their provenance for this session
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isActive && (
          <div className="mb-4 rounded-lg border border-warning/25 bg-warning-muted/20 p-3">
            <div className="flex items-center gap-2 text-sm text-warning">
              <Info className="h-4 w-4" />
              <span>
                Research is still {runStatus}. More artifacts may become available once complete.
              </span>
            </div>
          </div>
        )}

        {isTerminal && !artifactItems.some((a) => a.present) && (
          <div className="mb-4 rounded-lg border border-destructive/25 bg-destructive-muted/20 p-3">
            <div className="flex items-center gap-2 text-sm text-destructive">
              <XCircle className="h-4 w-4" />
              <span>
                Run {runStatus}. No artifacts available for inspection.
              </span>
            </div>
          </div>
        )}

        <ScrollArea className="pr-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {artifactItems.map((artifact) => (
              <ArtifactCard
                key={artifact.key}
                artifact={
                  artifact.key === 'trace_bundle'
                    ? { ...artifact, present: true }
                    : artifact
                }
                onExport={
                  artifact.key === 'trace_bundle' && artifact.present
                    ? handleExportBundle
                    : undefined
                }
              />
            ))}
          </div>
        </ScrollArea>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4 text-xs text-muted-foreground">
          <Info className="h-3.5 w-3.5" />
          <span className="font-medium">Provenance guide:</span>
          <span>Direct = generated during run</span>
          <span className="text-border">•</span>
          <span>Derived = computed from raw data</span>
        </div>
      </CardContent>
    </Card>
  );
}