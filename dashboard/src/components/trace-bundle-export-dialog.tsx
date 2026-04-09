'use client';

import { useState } from 'react';
import { Download, FileArchive, Info, Loader2 } from 'lucide-react';

import { Button, buttonVariants } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogBody,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogContent,
} from '@/components/ui/dialog';
import { getSessionBundle, getApiErrorMessage } from '@/lib/api';
import { useNotifications } from '@/components/ui/notification-center';

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
  const { notify } = useNotifications();
  const [includePayload, setIncludePayload] = useState(false);
  const [includeReport, setIncludeReport] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const { bundle } = await getSessionBundle(sessionId, {
        includePayload,
        includeReport,
      });

      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `trace-bundle-${sessionId.slice(0, 8)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      notify({
        variant: 'success',
        title: 'Bundle exported',
        description: 'The trace bundle has been downloaded.',
      });
      onOpenChange(false);
    } catch (error) {
      notify({
        variant: 'destructive',
        title: 'Export failed',
        description: getApiErrorMessage(error, 'Failed to export trace bundle.'),
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleClose = () => {
    if (!isExporting) {
      setIncludePayload(false);
      setIncludeReport(false);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileArchive className="h-5 w-5" />
            Export Trace Bundle
          </DialogTitle>
          <DialogDescription>
            Download a portable trace bundle for offline inspection, debugging, or sharing.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <div className="rounded-xl border border-border bg-muted/30 p-4">
            <div className="flex items-start gap-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="text-sm text-muted-foreground">
                <p className="font-medium text-foreground">What&apos;s included</p>
                <p className="mt-1">
                  The bundle contains session metadata, telemetry events, and derived outputs
                  (decisions, failures, state changes).
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <label className="flex items-start gap-3 cursor-pointer">
              <Checkbox
                checked={includePayload}
                onCheckedChange={(checked) => setIncludePayload(Boolean(checked))}
                className="mt-1"
              />
              <div className="space-y-1">
                <span className="text-sm font-medium">Include session payload</span>
                <p className="text-xs text-muted-foreground">
                  Adds the full research data including sources, collected content, and intermediate
                  results. Larger file size but useful for complete debugging.
                </p>
              </div>
            </label>

            <label className="flex items-start gap-3 cursor-pointer">
              <Checkbox
                checked={includeReport}
                onCheckedChange={(checked) => setIncludeReport(Boolean(checked))}
                disabled={!hasReport}
                className="mt-1"
              />
              <div className="space-y-1">
                <span className="text-sm font-medium">Include research report</span>
                <p className="text-xs text-muted-foreground">
                  Adds the final research report content. Only available if a report was generated.
                </p>
              </div>
            </label>
          </div>
        </DialogBody>

        <DialogFooter>
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
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
