import { create } from 'zustand';
import type { BacklogItem, BacklogListResponse } from '@/types/content-gen';
import {
  listBacklog,
  updateBacklogItem as updateBacklogItemApi,
  selectBacklogItem as selectBacklogItemApi,
  archiveBacklogItem as archiveBacklogItemApi,
  deleteBacklogItem as deleteBacklogItemApi,
  createBacklogItem as createBacklogItemApi,
  startBacklogItem as startBacklogItemApi,
} from '@/lib/content-gen/backlog';
import { getApiErrorMessage } from '@/lib/api';

interface BacklogState {
  backlog: BacklogItem[];
  backlogPath: string | null;
  backlogLoading: boolean;
  error: string | null;
  loadBacklog: () => Promise<void>;
  mergeBacklogItems: (items: BacklogItem[]) => void;
  createBacklogItem: (data: Record<string, unknown>) => Promise<void>;
  updateBacklogItem: (ideaId: string, patch: Record<string, unknown>) => Promise<void>;
  selectBacklogItem: (ideaId: string) => Promise<void>;
  archiveBacklogItem: (ideaId: string) => Promise<void>;
  deleteBacklogItem: (ideaId: string) => Promise<void>;
  startBacklogItem: (ideaId: string) => Promise<string | null>;
  clearError: () => void;
  reset: () => void;
}

const initialState = {
  backlog: [] as BacklogItem[],
  backlogPath: null as string | null,
  backlogLoading: false,
  error: null as string | null,
};

export const useBacklogStore = create<BacklogState>((set, get) => ({
  ...initialState,

  loadBacklog: async () => {
    set({ backlogLoading: true, error: null });
    try {
      const result = await listBacklog();
      set({ backlog: result.items, backlogPath: result.path, backlogLoading: false });
    } catch (err) {
      set({
        backlogLoading: false,
        error: getApiErrorMessage(err, 'Failed to load backlog.'),
      });
    }
  },

  mergeBacklogItems: (items) => {
    if (!items.length) {
      return;
    }

    set((state) => {
      const existingById = new Map(state.backlog.map((item) => [item.idea_id, item]));
      const incomingById = new Map(items.map((item) => [item.idea_id, item]));
      const containsSelectedItem = items.some((item) => item.status === 'selected');
      const nextBacklog = state.backlog.map((item) => {
        const incoming = incomingById.get(item.idea_id);
        if (incoming) {
          return incoming;
        }
        if (containsSelectedItem && item.status === 'selected') {
          return { ...item, status: 'backlog', selection_reasoning: '' };
        }
        return item;
      });

      for (const item of items) {
        if (!existingById.has(item.idea_id)) {
          nextBacklog.push(item);
        }
      }

      return { backlog: nextBacklog };
    });
  },

  createBacklogItem: async (data) => {
    set({ error: null });
    try {
      const created = await createBacklogItemApi(data);
      set((state) => ({
        backlog: [...state.backlog, created],
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to create backlog item.') });
    }
  },

  updateBacklogItem: async (ideaId, patch) => {
    set({ error: null });
    try {
      const updated = await updateBacklogItemApi(ideaId, patch);
      set((state) => ({
        backlog: state.backlog.map((item) => (item.idea_id === ideaId ? updated : item)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to update backlog item.') });
    }
  },

  selectBacklogItem: async (ideaId) => {
    const previousBacklog = get().backlog;
    set({ error: null });
    try {
      const selected = await selectBacklogItemApi(ideaId);
      set((state) => ({
        backlog: state.backlog.map((item) =>
          item.idea_id === ideaId
            ? selected
            : item.status === 'selected'
              ? { ...item, status: 'backlog' as const, selection_reasoning: '' }
              : item
        ),
      }));
    } catch (err) {
      set({ backlog: previousBacklog, error: getApiErrorMessage(err, 'Failed to select backlog item.') });
    }
  },

  archiveBacklogItem: async (ideaId) => {
    set({ error: null });
    try {
      const archived = await archiveBacklogItemApi(ideaId);
      set((state) => ({
        backlog: state.backlog.map((item) => (item.idea_id === ideaId ? archived : item)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to archive backlog item.') });
    }
  },

  deleteBacklogItem: async (ideaId) => {
    set({ error: null });
    try {
      await deleteBacklogItemApi(ideaId);
      set((state) => ({
        backlog: state.backlog.filter((item) => item.idea_id !== ideaId),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to delete backlog item.') });
    }
  },

  startBacklogItem: async (ideaId) => {
    set({ error: null });
    try {
      const result = await startBacklogItemApi(ideaId);
      const pipelineId = result.pipeline_id ?? null;
      return pipelineId;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to start backlog item.') });
      return null;
    }
  },

  clearError: () => set({ error: null }),

  reset: () => set(initialState),
}));

// Backwards compatibility alias
export const useBacklog = useBacklogStore;