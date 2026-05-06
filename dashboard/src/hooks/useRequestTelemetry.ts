'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getRecentRequestTelemetry,
  sanitizeForExport,
  type RequestTelemetryEntry,
} from '@/lib/request-telemetry';

const TELEMETRY_POLL_INTERVAL_MS = 2000;

export interface RequestTelemetryState {
  recentFailures: RequestTelemetryEntry[];
  exportableFailures: RequestTelemetryEntry[];
}

export function useRequestTelemetry(): RequestTelemetryState {
  const [recentFailures, setRecentFailures] = useState<RequestTelemetryEntry[]>([]);
  const exportableRef = useRef<RequestTelemetryEntry[]>([]);

  useEffect(() => {
    const poll = () => {
      const entries = getRecentRequestTelemetry();
      const failures = entries.filter((e) => e.errorCategory !== null);
      setRecentFailures(failures);
      exportableRef.current = sanitizeForExport(failures);
    };

    poll();
    const intervalId = window.setInterval(poll, TELEMETRY_POLL_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, []);

  return {
    recentFailures,
    exportableFailures: exportableRef.current,
  };
}
