import { create } from 'zustand';
import type { StrategyMemory } from '@/types/content-gen';
import {
  getStrategy as getStrategyApi,
  updateStrategy as updateStrategyApi,
} from '@/lib/content-gen/strategy';
import { getApiErrorMessage } from '@/lib/api';

interface StrategyState {
  strategy: StrategyMemory | null;
  strategyLoading: boolean;
  error: string | null;
  loadStrategy: () => Promise<void>;
  updateStrategy: (patch: Record<string, unknown>) => Promise<void>;
  clearError: () => void;
}

const initialState = {
  strategy: null as StrategyMemory | null,
  strategyLoading: false,
  error: null as string | null,
};

export const useStrategyStore = create<StrategyState>((set) => ({
  ...initialState,

  loadStrategy: async () => {
    set({ strategyLoading: true, error: null });
    try {
      const strategy = await getStrategyApi();
      set({ strategy, strategyLoading: false });
    } catch (err) {
      set({
        strategyLoading: false,
        error: getApiErrorMessage(err, 'Failed to load strategy.'),
      });
    }
  },

  updateStrategy: async (patch) => {
    set({ error: null });
    try {
      const updated = await updateStrategyApi(patch);
      set({ strategy: updated });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to update strategy.') });
    }
  },

  clearError: () => set({ error: null }),
}));

// Backwards compatibility alias
export const useStrategy = useStrategyStore;