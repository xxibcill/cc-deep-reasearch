import { create } from 'zustand';
import type {
  BacklogItem,
  PipelineRunSummary,
  PipelineContext,
  StageProgress,
  StrategyMemory,
  PublishItem,
  SavedScriptRun,
} from '@/types/content-gen';
import {
  listBacklog,
  updateBacklogItem as updateBacklogItemApi,
  selectBacklogItem as selectBacklogItemApi,
  archiveBacklogItem as archiveBacklogItemApi,
  deleteBacklogItem as deleteBacklogItemApi,
  listPipelines,
  startPipeline,
  getPipeline,
  stopPipeline as stopPipelineApi,
  approveQC,
  runScripting as runScriptingApi,
  listScripts,
  getStrategy as getStrategyApi,
  updateStrategy as updateStrategyApi,
  listPublishQueue,
  removeFromQueue as removeFromQueueApi,
} from '@/lib/content-gen-api';
import { getApiErrorMessage } from '@/lib/api';

interface ContentGenState {
  // Pipeline runs
  pipelines: PipelineRunSummary[];
  pipelinesLoading: boolean;
  activePipelineId: string | null;
  pipelineContext: PipelineContext | null;
  pipelineStageProgress: Record<number, StageProgress>;

  // Strategy
  strategy: StrategyMemory | null;
  strategyLoading: boolean;

  // Backlog
  backlog: BacklogItem[];
  backlogPath: string | null;
  backlogLoading: boolean;

  // Publish queue
  publishQueue: PublishItem[];
  publishQueueLoading: boolean;

  // Scripts history
  scripts: SavedScriptRun[];
  scriptsLoading: boolean;

  // Error state
  error: string | null;

  // Actions
  loadPipelines: () => Promise<void>;
  startPipeline: (theme: string, fromStage?: number, toStage?: number) => Promise<string | null>;
  selectPipeline: (id: string) => Promise<void>;
  stopPipeline: (id: string) => Promise<void>;
  approveQC: (pipelineId: string) => Promise<void>;
  updateStageProgress: (stageIndex: number, event: Record<string, unknown>) => void;
  updatePipelineContext: (context: PipelineContext) => void;

  runScripting: (idea: string) => Promise<void>;
  loadScripts: () => Promise<void>;

  loadStrategy: () => Promise<void>;
  updateStrategy: (patch: Record<string, unknown>) => Promise<void>;

  loadBacklog: () => Promise<void>;
  updateBacklogItem: (ideaId: string, patch: Record<string, unknown>) => Promise<void>;
  selectBacklogItem: (ideaId: string) => Promise<void>;
  archiveBacklogItem: (ideaId: string) => Promise<void>;
  deleteBacklogItem: (ideaId: string) => Promise<void>;

  loadPublishQueue: () => Promise<void>;
  removeFromQueue: (ideaId: string, platform: string) => Promise<void>;

  loadAll: () => Promise<void>;

  clearError: () => void;
  reset: () => void;
}

const initialState = {
  pipelines: [],
  pipelinesLoading: false,
  activePipelineId: null,
  pipelineContext: null,
  pipelineStageProgress: {},
  strategy: null,
  strategyLoading: false,
  backlog: [],
  backlogPath: null,
  backlogLoading: false,
  publishQueue: [],
  publishQueueLoading: false,
  scripts: [],
  scriptsLoading: false,
  error: null,
};

const useContentGen = create<ContentGenState>((set, get) => ({
  ...initialState,

  loadPipelines: async () => {
    set({ pipelinesLoading: true, error: null });
    try {
      const pipelines = await listPipelines();
      set({ pipelines, pipelinesLoading: false });
    } catch (err) {
      set({
        pipelinesLoading: false,
        error: getApiErrorMessage(err, 'Failed to load pipelines.'),
      });
    }
  },

  startPipeline: async (theme, fromStage, toStage) => {
    set({ error: null });
    try {
      const result = await startPipeline({
        theme,
        from_stage: fromStage,
        to_stage: toStage ?? null,
      });
      const pipelineId = result.pipeline_id ?? null;
      if (pipelineId) {
        set({ activePipelineId: pipelineId });
        const pipelines = await listPipelines();
        set({ pipelines });
      }
      return pipelineId;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to start pipeline.') });
      return null;
    }
  },

  selectPipeline: async (id) => {
    set({ activePipelineId: id, pipelineContext: null, pipelineStageProgress: {}, error: null });
    try {
      const context = await getPipeline(id);
      set({ pipelineContext: context });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to load pipeline context.') });
    }
  },

  stopPipeline: async (id) => {
    set({ error: null });
    try {
      await stopPipelineApi(id);
      const pipelines = await listPipelines();
      set({ pipelines });
      if (get().activePipelineId === id) {
        set({ pipelineContext: null });
      }
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to stop pipeline.') });
    }
  },

  approveQC: async (pipelineId) => {
    set({ error: null });
    try {
      await approveQC(pipelineId);
      const context = await getPipeline(pipelineId);
      set({ pipelineContext: context });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to approve QC.') });
    }
  },

  updateStageProgress: (stageIndex, event) => {
    set((state) => ({
      pipelineStageProgress: {
        ...state.pipelineStageProgress,
        [stageIndex]: {
          ...state.pipelineStageProgress[stageIndex],
          ...event,
        } as StageProgress,
      },
    }));
  },

  updatePipelineContext: (context) => {
    set({ pipelineContext: context });
  },

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

  loadBacklog: async () => {
    set({ backlogLoading: true, error: null });
    try {
      const backlog = await listBacklog();
      set({
        backlog: backlog.items,
        backlogPath: backlog.path || null,
        backlogLoading: false,
      });
    } catch (err) {
      set({
        backlogLoading: false,
        error: getApiErrorMessage(err, 'Failed to load backlog.'),
      });
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
    set({ error: null });
    try {
      const selected = await selectBacklogItemApi(ideaId);
      set((state) => ({
        backlog: state.backlog.map((item) =>
          item.idea_id === ideaId
            ? selected
            : item.status === 'selected'
              ? { ...item, status: 'backlog', selection_reasoning: '' }
              : item
        ),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to select backlog item.') });
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
      set({ error: getApiErrorMessage(err, 'Failed to remove backlog item.') });
    }
  },

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

  loadAll: async () => {
    await Promise.allSettled([
      get().loadPipelines(),
      get().loadScripts(),
      get().loadBacklog(),
      get().loadPublishQueue(),
      get().loadStrategy(),
    ]);
  },

  reset: () => set(initialState),
}));

export default useContentGen;
