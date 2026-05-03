'use client';

import { useState } from 'react';
import type { LintFinding } from '@/lib/knowledge-client';

interface LintQueueProps {
  findings: LintFinding[];
  onRefresh: () => void;
}

const SEVERITY_ICONS: Record<string, string> = {
  error: '✗',
  warning: '⚠',
  info: 'ℹ',
};

const SEVERITY_COLORS: Record<string, string> = {
  error: 'text-red-500',
  warning: 'text-amber-500',
  info: 'text-blue-500',
};

export function LintQueue({ findings, onRefresh }: LintQueueProps) {
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());

  const visible = findings.filter((_, i) => !dismissed.has(i));
  const errorCount = visible.filter((f) => f.severity === 'error').length;
  const warningCount = visible.filter((f) => f.severity === 'warning').length;

  if (findings.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-surface-raised/50 p-3 text-xs text-muted-foreground">
        <span className="text-green-500">✓</span>
        <span>No lint findings. Vault is healthy.</span>
        <button
          onClick={onRefresh}
          className="ml-auto text-xs text-muted-foreground hover:text-foreground"
        >
          Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {errorCount > 0 && (
            <span className={SEVERITY_COLORS.error}>
              {errorCount} error{errorCount !== 1 ? 's' : ''}
            </span>
          )}
          {warningCount > 0 && (
            <span className={SEVERITY_COLORS.warning}>
              {warningCount} warning{warningCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <button
          onClick={onRefresh}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Refresh
        </button>
      </div>

      <ul className="space-y-1 max-h-48 overflow-y-auto">
        {visible.map((finding, i) => (
          <li
            key={i}
            className="flex items-start gap-2 rounded-md border border-border/30 bg-background/50 p-2 text-xs"
          >
            <span className={`mt-0.5 ${SEVERITY_COLORS[finding.severity]}`}>
              {SEVERITY_ICONS[finding.severity]}
            </span>
            <div className="flex-1 min-w-0">
              <p className="break-words text-foreground">{finding.message}</p>
              {finding.page_path && (
                <p className="mt-0.5 truncate text-muted-foreground">
                  {finding.page_path}
                </p>
              )}
            </div>
            <button
              onClick={() => setDismissed((prev) => new Set([...prev, i]))}
              className="shrink-0 text-muted-foreground hover:text-foreground"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
