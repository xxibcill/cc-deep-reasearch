'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { startResearchRun } from '@/lib/api';
import type { ResearchRunRequest } from '@/types/telemetry';

type ResearchDepth = 'quick' | 'standard' | 'deep';

interface FormData {
  query: string;
  depth: ResearchDepth;
  minSources: string;
}

export function StartResearchForm() {
  const router = useRouter();
  const [formData, setFormData] = useState<FormData>({
    query: '',
    depth: 'deep',
    minSources: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.query.trim()) {
      setError('Please enter a research query');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const request: ResearchRunRequest = {
        query: formData.query.trim(),
        depth: formData.depth,
        min_sources: formData.minSources ? parseInt(formData.minSources, 10) : null,
        realtime_enabled: true,
      };

      const response = await startResearchRun(request);

      // Redirect to the session view
      router.push(`/session/${response.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start research run');
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="query" className="block text-sm font-medium mb-2">
          Research Query
        </label>
        <textarea
          id="query"
          value={formData.query}
          onChange={(e) => setFormData((prev) => ({ ...prev, query: e.target.value }))}
          placeholder="What would you like to research?"
          className="w-full min-h-[100px] px-3 py-2 border rounded-md resize-y focus:outline-none focus:ring-2 focus:ring-primary"
          disabled={isSubmitting}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="depth" className="block text-sm font-medium mb-2">
            Research Depth
          </label>
          <select
            id="depth"
            value={formData.depth}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, depth: e.target.value as ResearchDepth }))
            }
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={isSubmitting}
          >
            <option value="quick">Quick (3-5 sources)</option>
            <option value="standard">Standard (10-15 sources)</option>
            <option value="deep">Deep (20+ sources)</option>
          </select>
        </div>

        <div>
          <label htmlFor="minSources" className="block text-sm font-medium mb-2">
            Minimum Sources (optional)
          </label>
          <input
            id="minSources"
            type="number"
            min="1"
            max="100"
            value={formData.minSources}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, minSources: e.target.value }))
            }
            placeholder="Auto"
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={isSubmitting}
          />
        </div>
      </div>

      {error && (
        <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={isSubmitting || !formData.query.trim()}
        className="w-full py-2 px-4 bg-primary text-white rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? 'Starting Research...' : 'Start Research'}
      </button>
    </form>
  );
}
