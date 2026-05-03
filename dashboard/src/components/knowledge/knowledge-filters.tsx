'use client';

const ALL_KINDS = [
  'session',
  'source',
  'query',
  'concept',
  'entity',
  'claim',
  'finding',
  'gap',
  'question',
  'wiki_page',
] as const;

interface KnowledgeFiltersProps {
  selectedKinds: string[];
  onToggleKind: (kind: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function KnowledgeFilters({
  selectedKinds,
  onToggleKind,
  searchQuery,
  onSearchChange,
}: KnowledgeFiltersProps) {
  return (
    <div className="flex flex-col gap-3">
      <input
        type="text"
        placeholder="Search nodes…"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        className="h-8 w-full rounded-md border border-border bg-background px-3 text-xs placeholder:text-muted-foreground"
      />

      <div className="flex flex-wrap gap-1.5">
        {ALL_KINDS.map((kind) => {
          const isSelected = selectedKinds.length === 0 || selectedKinds.includes(kind);
          return (
            <button
              key={kind}
              onClick={() => onToggleKind(kind)}
              className={`rounded-full px-2.5 py-0.5 text-xs transition-colors ${
                isSelected
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-surface-raised text-muted-foreground hover:bg-border/50'
              }`}
            >
              {kind.replace(/_/g, ' ')}
            </button>
          );
        })}
      </div>

      {selectedKinds.length > 0 && (
        <button
          onClick={() => onToggleKind('')}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
