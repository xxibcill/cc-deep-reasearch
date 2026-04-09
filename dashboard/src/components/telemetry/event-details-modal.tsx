import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { TelemetryEvent } from '@/types/telemetry';

export function EventDetailsModal({
  event,
  onClose,
}: {
  event: TelemetryEvent;
  onClose: () => void;
}) {
  return (
    <Dialog open={Boolean(event)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>Event Details</DialogTitle>
          <DialogDescription>
            Inspect the raw telemetry payload for{' '}
            <span className="font-mono text-xs text-foreground">{event.eventId}</span>.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <pre className="overflow-auto rounded-xl bg-muted p-4 text-sm">
            {JSON.stringify(event, null, 2)}
          </pre>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
