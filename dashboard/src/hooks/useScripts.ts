import { create } from 'zustand';
import type { SavedScriptRun } from '@/types/content-gen';
import {
  runScripting as runScriptingApi,
  listScripts,
} from '@/lib/content-gen/scripts';
import { getApiErrorMessage } from '@/lib/api';

interface ScriptsState {
  scripts: SavedScriptRun[];
  scriptsLoading: boolean;
  error: string | null;
  runScripting: (idea: string) => Promise<void>;
  loadScripts: () => Promise<void>;
  clearError: () => void;
}

const initialState = {
  scripts: [] as SavedScriptRun[],
  scriptsLoading: false,
  error: null as string | null,
};

export const useScriptsStore = create<ScriptsState>((set) => ({
  ...initialState,

  runScripting: async (idea) => {
    set({ error: null });
    try {
      await runScriptingApi({ idea });
      const scripts = await listScripts();
      set({ scripts });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to run scripting.') });
    }
  },

  loadScripts: async () => {
    set({ scriptsLoading: true, error: null });
    try {
      const scripts = await listScripts();
      set({ scripts, scriptsLoading: false });
    } catch (err) {
      set({
        scriptsLoading: false,
        error: getApiErrorMessage(err, 'Failed to load scripts.'),
      });
    }
  },

  clearError: () => set({ error: null }),
}));

// Backwards compatibility alias
export const useScripts = useScriptsStore;