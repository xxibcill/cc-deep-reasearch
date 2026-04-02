import { SlidersHorizontal } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CollapsiblePanel } from '@/components/ui/collapsible-panel';
import { Select } from '@/components/ui/select';
import type { EventFilter } from '@/types/telemetry';

export const EMPTY_FILTERS: Partial<EventFilter> = {
  agent: [],
  phase: [],
  tool: [],
  provider: [],
  status: [],
  eventTypes: [],
};

export function getActiveFilters(filters: EventFilter): Array<{ label: string; value: string }> {
  return [
    { label: 'Agent', value: filters.agent[0] ?? '' },
    { label: 'Phase', value: filters.phase[0] ?? '' },
    { label: 'Tool', value: filters.tool[0] ?? '' },
    { label: 'Provider', value: filters.provider[0] ?? '' },
    { label: 'Status', value: filters.status[0] ?? '' },
    { label: 'Event Type', value: filters.eventTypes[0] ?? '' },
  ].filter((entry): entry is { label: string; value: string } => Boolean(entry.value));
}

export interface FilterPanelProps {
  filters: EventFilter;
  derived: {
    agents: string[];
    phases: string[];
    tools: string[];
    providers: string[];
    statuses: string[];
    eventTypes: string[];
  };
  filtersOpen: boolean;
  onFiltersOpenChange: (open: boolean) => void;
  onFiltersChange: (filters: Partial<EventFilter>) => void;
}

export function FilterPanel({
  filters,
  derived,
  filtersOpen,
  onFiltersOpenChange,
  onFiltersChange,
}: FilterPanelProps) {
  const activeFilters = getActiveFilters(filters);

  return (
    <CollapsiblePanel
      actions={
        activeFilters.length > 0 ? (
          <Button
            className="text-slate-600"
            onClick={(event) => {
              event.stopPropagation();
              onFiltersChange(EMPTY_FILTERS);
              onFiltersOpenChange(false);
            }}
            size="sm"
            type="button"
            variant="ghost"
          >
            Clear
          </Button>
        ) : undefined
      }
      className="border-dashed border-slate-200/80 bg-slate-50/70 shadow-none"
      defaultOpen={activeFilters.length > 0}
      meta={
        activeFilters.length > 0 ? (
          <Badge variant="outline" className="bg-white/80">
            {activeFilters.length} active
          </Badge>
        ) : undefined
      }
      onOpenChange={onFiltersOpenChange}
      open={filtersOpen}
      summary={
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Refine Results
          </div>
          <div className="text-sm font-semibold text-foreground">Filters</div>
          <p className="text-xs text-muted-foreground">
            {activeFilters.length === 0
              ? 'Showing all telemetry data. Expand filters only when you need to narrow the view.'
              : `${activeFilters.length} active filter${activeFilters.length === 1 ? '' : 's'} narrowing the workspace.`}
          </p>
        </div>
      }
    >
      {activeFilters.length > 0 ? (
        <div className="mb-4 flex flex-wrap gap-2">
          {activeFilters.map((filter) => (
            <Badge key={filter.label} variant="outline" className="bg-white/80 text-[11px]">
              {filter.label}: {filter.value}
            </Badge>
          ))}
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <Select
          label="Agent"
          value={filters.agent[0] ?? ''}
          options={derived.agents}
          onChange={(value) => onFiltersChange({ agent: value ? [value] : [] })}
          className="h-9 bg-white/90"
          labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
        />
        <Select
          label="Phase"
          value={filters.phase[0] ?? ''}
          options={derived.phases}
          onChange={(value) => onFiltersChange({ phase: value ? [value] : [] })}
          className="h-9 bg-white/90"
          labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
        />
        <Select
          label="Tool"
          value={filters.tool[0] ?? ''}
          options={derived.tools}
          onChange={(value) => onFiltersChange({ tool: value ? [value] : [] })}
          className="h-9 bg-white/90"
          labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
        />
        <Select
          label="Provider"
          value={filters.provider[0] ?? ''}
          options={derived.providers}
          onChange={(value) => onFiltersChange({ provider: value ? [value] : [] })}
          className="h-9 bg-white/90"
          labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
        />
        <Select
          label="Status"
          value={filters.status[0] ?? ''}
          options={derived.statuses}
          onChange={(value) => onFiltersChange({ status: value ? [value] : [] })}
          className="h-9 bg-white/90"
          labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
        />
        <Select
          label="Event Type"
          value={filters.eventTypes[0] ?? ''}
          options={derived.eventTypes}
          onChange={(value) => onFiltersChange({ eventTypes: value ? [value] : [] })}
          className="h-9 bg-white/90"
          labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
        />
      </div>
    </CollapsiblePanel>
  );
}
