import { create } from 'zustand';
import type {
  PipelineRunSummary,
  PipelineContext,
  StageProgress,
  StrategyMemory,
  PublishItem,
  SavedScriptRun,
} from '@/types/content-gen';
import {
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

  runScripting: (idea: string) => Promise<void>;
  loadScripts: () => Promise<void>;

  loadStrategy: () => Promise<void>;
  updateStrategy: (patch: Record<string, unknown>) => Promise<void>;

  loadPublishQueue: () => Promise<void>;
  removeFromQueue: (ideaId: string, platform: string) => Promise<void>;

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

  runScripting: async (idea) => {
    set({ error: null });
    try {
      await runScriptingApi(idea);
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

  reset: () => set(initialState),
}));

export default useContentGen;
