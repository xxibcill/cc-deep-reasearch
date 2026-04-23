import { create } from 'zustand';
import type { PublishItem } from '@/types/content-gen';
import {
  listPublishQueue,
  removeFromQueue as removeFromQueueApi,
} from '@/lib/content-gen/publish';
import { getApiErrorMessage } from '@/lib/api';

interface PublishState {
  publishQueue: PublishItem[];
  publishQueueLoading: boolean;
  error: string | null;
  loadPublishQueue: () => Promise<void>;
  removeFromQueue: (ideaId: string, platform: string) => Promise<void>;
  clearError: () => void;
}

const initialState = {
  publishQueue: [] as PublishItem[],
  publishQueueLoading: false,
  error: null as string | null,
};

export const usePublishStore = create<PublishState>((set) => ({
  ...initialState,

  loadPublishQueue: async () => {
    set({ publishQueueLoading: true, error: null });
    try {
      const publishQueue = await listPublishQueue();
      set({ publishQueue, publishQueueLoading: false });
    } catch (err) {
      set({
        publishQueueLoading: false,
        error: getApiErrorMessage(err, 'Failed to load publish queue.'),
      });
    }
  },

  removeFromQueue: async (ideaId, platform) => {
    set({ error: null });
    try {
      await removeFromQueueApi(ideaId, platform);
      set((state) => ({
        publishQueue: state.publishQueue.filter(
          (item) => !(item.idea_id === ideaId && item.platform === platform)
        ),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to remove item from publish queue.') });
    }
  },

  clearError: () => set({ error: null }),
}));

// Backwards compatibility alias
export const usePublish = usePublishStore;