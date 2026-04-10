'use client';

import { useState } from 'react';
import { Download, FileArchive, Info, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { getSessionBundle, getApiErrorMessage } from '@/lib/api';

interface TraceBundleExportDialogProps {
  sessionId: string;
  hasReport: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TraceBundleExportDialog({
  sessionId,
  hasReport,
  open,
  onOpenChange,
}: TraceBundleExportDialogProps) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const { bundle } = await getSessionBundle(sessionId);

      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `trace-bundle-${sessionId.slice(0, 8)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      onOpenChange(false);
    } catch (error) {
      console.error('Failed to export trace bundle:', error);
    } finally {
      setIsExporting(false);
    }
  };

  const handleClose = () => {
    if (!isExporting) {
      onOpenChange(false);
    }
  };

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-500/75 p-4">
      <div className="absolute inset-0" onClick={handleClose} />
      <div className="relative z-10 max-h-[85vh] w-full max-w-md overflow-hidden rounded-2xl border bg-neutral-100 shadow-2xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <FileArchive className="h-5 w-5" />
            Export Trace Bundle
          </h2>
          <button
            aria-label="Close dialog"
            className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            onClick={handleClose}
          >
            Close
          </button>
        </div>
        <div className="max-h-[calc(85vh-4.5rem)] overflow-auto p-5">
          <div className="rounded-xl border border-border bg-muted/30 p-4">
            <div className="flex items-start gap-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="text-sm text-muted-foreground">
                <p className="font-medium text-foreground">{"What's"} included</p>
                <p className="mt-1">
                  The bundle contains session metadata, telemetry events, and derived outputs
                  (decisions, failures, state changes).
                </p>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t px-5 py-4">
          <Button variant="outline" onClick={handleClose} disabled={isExporting}>
            Cancel
          </Button>
          <Button onClick={handleExport} disabled={isExporting}>
            {isExporting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Export Bundle
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
