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

export type KnowledgeNodeKind = (typeof ALL_KINDS)[number];

interface KnowledgeFiltersProps {
  selectedKinds: KnowledgeNodeKind[];
  onToggleKind: (kind: KnowledgeNodeKind) => void;
  onClearKinds: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function KnowledgeFilters({
  selectedKinds,
  onToggleKind,
  onClearKinds,
  searchQuery,
  onSearchChange,
}: KnowledgeFiltersProps) {
  const filterSummary =
    selectedKinds.length === 0
      ? 'All node types'
      : `${selectedKinds.length} type${selectedKinds.length === 1 ? '' : 's'} selected`;

  const renderFilterButtons = () => (
    <>
      {ALL_KINDS.map((kind) => {
        const isSelected = selectedKinds.length === 0 || selectedKinds.includes(kind);
        return (
          <button
            key={kind}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onToggleKind(kind)}
            className={`min-h-11 rounded-full px-3 text-xs font-medium transition-colors lg:min-h-7 lg:px-2.5 ${
              isSelected
                ? 'bg-warning text-background'
                : 'bg-surface-raised text-foreground/70 hover:bg-border/70 hover:text-foreground'
            }`}
          >
            {kind.replace(/_/g, ' ')}
          </button>
        );
      })}

      {selectedKinds.length > 0 && (
        <button
          type="button"
          onClick={onClearKinds}
          className="min-h-11 rounded-md px-2 text-xs font-medium text-foreground/70 hover:text-foreground lg:min-h-7"
        >
          Clear filters
        </button>
      )}
    </>
  );

  return (
    <div className="flex flex-col gap-3">
      <label htmlFor="knowledge-node-search" className="sr-only">
        Search knowledge graph nodes
      </label>
      <input
        id="knowledge-node-search"
        type="text"
        placeholder="Search nodes…"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        className="h-11 w-full rounded-md border border-border bg-background px-3 text-base placeholder:text-muted-foreground lg:h-8 lg:text-xs"
      />

      <details className="group rounded-lg border border-border/70 bg-surface/50 px-3 lg:hidden">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-sm text-foreground/80 marker:content-none [&::-webkit-details-marker]:hidden">
          <span className="font-medium">Node types</span>
          <span className="flex items-center gap-2 text-xs text-foreground/60">
            {filterSummary}
            <span aria-hidden="true" className="transition-transform group-open:rotate-180">
              ▾
            </span>
          </span>
        </summary>

        <div className="hidden flex-wrap gap-2 border-t border-border/60 py-3 group-open:flex lg:flex lg:border-0 lg:py-0">
          {renderFilterButtons()}
        </div>
      </details>

      <div className="hidden flex-wrap gap-2 lg:flex">{renderFilterButtons()}</div>
    </div>
  );
}
