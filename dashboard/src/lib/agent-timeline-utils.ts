import type { AgentExecution } from '@/types/telemetry';

export const MAX_VISIBLE_MARKERS_PER_LANE = 18;

export function sampleMarkers(markers: AgentExecution['markers']): {
  markers: AgentExecution['markers'];
  hiddenCount: number;
} {
  if (markers.length <= MAX_VISIBLE_MARKERS_PER_LANE) {
    return {
      markers,
      hiddenCount: 0,
    };
  }

  // Always include first and last markers (key checkpoints)
  const firstTimestamp = markers[0]?.timestamp ?? 0;
  const lastTimestamp = markers[markers.length - 1]?.timestamp ?? 0;
  const timeRange = lastTimestamp - firstTimestamp;

  const selectedMarkers: typeof markers = [markers[0]];

  if (timeRange > 0) {
    // Use timestamp-based sampling for stable visuals across re-renders
    const targetInteriorCount = MAX_VISIBLE_MARKERS_PER_LANE - 2;
    for (let step = 1; step <= targetInteriorCount; step += 1) {
      const targetTimestamp = firstTimestamp + (step / (targetInteriorCount + 1)) * timeRange;
      // Find the marker closest to the target timestamp
      let closestIndex = 0;
      let closestDiff = Math.abs((markers[0]?.timestamp ?? 0) - targetTimestamp);
      for (let i = 1; i < markers.length; i++) {
        const diff = Math.abs((markers[i]?.timestamp ?? 0) - targetTimestamp);
        if (diff < closestDiff) {
          closestDiff = diff;
          closestIndex = i;
        }
      }
      // Avoid duplicates
      if (closestIndex !== 0 && closestIndex !== markers.length - 1) {
        selectedMarkers.push(markers[closestIndex]);
      }
    }
  }

  selectedMarkers.push(markers[markers.length - 1]);

  return {
    markers: selectedMarkers,
    hiddenCount: markers.length - selectedMarkers.length,
  };
}
