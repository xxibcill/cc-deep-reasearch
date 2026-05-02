'use client';

import { KnowledgeShell } from '@/components/knowledge/knowledge-shell';

export default function KnowledgePage() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b px-6 py-4">
        <h1 className="text-lg font-semibold">Knowledge Graph</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Inspect the local knowledge vault, wiki pages, and graph structure.
        </p>
      </div>

      <div className="flex-1 overflow-hidden">
        <KnowledgeShell />
      </div>
    </div>
  );
}
