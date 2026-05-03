import { create } from 'zustand';
import type {
  PipelineRunSummary,
  PipelineContext,
  StageProgress,
  StrategyMemory,
  PublishItem,
  SavedScriptRun,
  BacklogItem,
  ManagedOpportunityBrief,
  BriefRevision,
} from '@/types/content-gen';
import { listPipelines, startPipeline, getPipeline, stopPipeline as stopPipelineApi, approveQC } from '@/lib/content-gen/pipeline';
import { listScripts, runScripting } from '@/lib/content-gen/scripts';
import { getStrategy as getStrategyApi, updateStrategy as updateStrategyApi } from '@/lib/content-gen/strategy';
import { listPublishQueue, removeFromQueue as removeFromQueueApi } from '@/lib/content-gen/publish';
import {
  listBacklog,
  updateBacklogItem as updateBacklogItemApi,
  selectBacklogItem as selectBacklogItemApi,
  archiveBacklogItem as archiveBacklogItemApi,
  deleteBacklogItem as deleteBacklogItemApi,
  createBacklogItem as createBacklogItemApi,
  startBacklogItem as startBacklogItemApi,
} from '@/lib/content-gen/backlog';
import {
  listBriefs,
  getBrief,
  createBrief as createBriefApi,
  updateBrief as updateBriefApi,
  approveBrief as approveBriefApi,
  archiveBrief as archiveBriefApi,
  supersedeBrief as supersedeBriefApi,
  revertBriefToDraft as revertBriefToDraftApi,
  cloneBrief as cloneBriefApi,
  branchBrief as branchBriefApi,
  listSiblingBriefs as listSiblingBriefsApi,
  compareBriefs as compareBriefsApi,
  listBriefRevisions,
  getBriefRevision,
  saveBriefRevision,
  applyRevision,
} from '@/lib/content-gen/brief';
import { getApiErrorMessage } from '@/lib/api';

// ---------------------------------------------------------------------------
// Unified store - delegates to feature stores internally
// This preserves the existing API while splitting internals
// ---------------------------------------------------------------------------

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

  // Backlog
  backlog: BacklogItem[];
  backlogPath: string | null;
  backlogLoading: boolean;

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

  loadPublishQueue: () => Promise<void>;
  removeFromQueue: (ideaId: string, platform: string) => Promise<void>;

  loadBacklog: () => Promise<void>;
  mergeBacklogItems: (items: BacklogItem[]) => void;
  createBacklogItem: (data: Record<string, unknown>) => Promise<void>;
  updateBacklogItem: (ideaId: string, patch: Record<string, unknown>) => Promise<void>;
  selectBacklogItem: (ideaId: string) => Promise<void>;
  archiveBacklogItem: (ideaId: string) => Promise<void>;
  deleteBacklogItem: (ideaId: string) => Promise<void>;
  startBacklogItem: (ideaId: string) => Promise<string | null>;

  // Briefs
  briefs: ManagedOpportunityBrief[];
  briefsLoading: boolean;
  activeBriefId: string | null;
  activeBriefRevisions: BriefRevision[];
  siblingBriefs: ManagedOpportunityBrief[];
  loadBriefs: (lifecycleState?: string) => Promise<void>;
  loadBrief: (briefId: string) => Promise<ManagedOpportunityBrief | null>;
  createBrief: (brief: Record<string, unknown>) => Promise<void>;
  updateBrief: (briefId: string, patch: Record<string, unknown>) => Promise<void>;
  approveBrief: (briefId: string, expectedUpdatedAt?: string) => Promise<void>;
  archiveBrief: (briefId: string, expectedUpdatedAt?: string) => Promise<void>;
  supersedeBrief: (briefId: string, expectedUpdatedAt?: string) => Promise<void>;
  revertBriefToDraft: (briefId: string, expectedUpdatedAt?: string) => Promise<void>;
  cloneBrief: (briefId: string, newTitle?: string) => Promise<string | null>;
  branchBrief: (briefId: string, newTitle?: string, branchReason?: string) => Promise<string | null>;
  loadSiblingBriefs: (briefId: string) => Promise<void>;
  loadBriefRevisions: (briefId: string) => Promise<void>;
  saveBriefRevision: (
    briefId: string,
    brief: Record<string, unknown>,
    revisionNotes?: string,
    sourcePipelineId?: string,
  ) => Promise<void>;
  applyRevision: (briefId: string, revisionId: string, expectedUpdatedAt?: string) => Promise<void>;

  loadAll: () => Promise<void>;

  clearError: () => void;
  reset: () => void;
}

const initialState = {
  pipelines: [] as PipelineRunSummary[],
  pipelinesLoading: false,
  activePipelineId: null as string | null,
  pipelineContext: null as PipelineContext | null,
  pipelineStageProgress: {} as Record<number, StageProgress>,
  strategy: null as StrategyMemory | null,
  strategyLoading: false,
  publishQueue: [] as PublishItem[],
  publishQueueLoading: false,
  scripts: [] as SavedScriptRun[],
  scriptsLoading: false,
  backlog: [] as BacklogItem[],
  backlogPath: null as string | null,
  backlogLoading: false,
  briefs: [] as ManagedOpportunityBrief[],
  briefsLoading: false,
  activeBriefId: null as string | null,
  activeBriefRevisions: [] as BriefRevision[],
  siblingBriefs: [] as ManagedOpportunityBrief[],
  error: null as string | null,
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
      await runScripting({ idea });
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
      if (pipelineId) {
        set({ activePipelineId: pipelineId });
        const pipelines = await listPipelines();
        set({ pipelines });
      }
      return pipelineId;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to start backlog item.') });
      return null;
    }
  },

  clearError: () => set({ error: null }),

  // Briefs
  loadBriefs: async (lifecycleState?: string) => {
    set({ briefsLoading: true, error: null });
    try {
      const result = await listBriefs(lifecycleState);
      set({ briefs: result.items, briefsLoading: false });
    } catch (err) {
      set({ briefsLoading: false, error: getApiErrorMessage(err, 'Failed to load briefs.') });
    }
  },

  loadBrief: async (briefId: string) => {
    set({ error: null });
    try {
      const brief = await getBrief(briefId);
      set({ activeBriefId: briefId });
      return brief;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to load brief.') });
      return null;
    }
  },

  createBrief: async (brief: Record<string, unknown>) => {
    set({ error: null });
    try {
      const created = await createBriefApi({ brief });
      set((state) => ({ briefs: [...state.briefs, created] }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to create brief.') });
    }
  },

  updateBrief: async (briefId: string, patch: Record<string, unknown>) => {
    set({ error: null });
    try {
      const updated = await updateBriefApi(briefId, { patch });
      set((state) => ({
        briefs: state.briefs.map((b) => (b.brief_id === briefId ? updated : b)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to update brief.') });
    }
  },

  approveBrief: async (briefId: string, expectedUpdatedAt?: string) => {
    set({ error: null });
    try {
      const updated = await approveBriefApi(briefId, expectedUpdatedAt);
      set((state) => ({
        briefs: state.briefs.map((b) => (b.brief_id === briefId ? updated : b)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to approve brief.') });
    }
  },

  archiveBrief: async (briefId: string, expectedUpdatedAt?: string) => {
    set({ error: null });
    try {
      const updated = await archiveBriefApi(briefId, expectedUpdatedAt);
      set((state) => ({
        briefs: state.briefs.map((b) => (b.brief_id === briefId ? updated : b)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to archive brief.') });
    }
  },

  supersedeBrief: async (briefId: string, expectedUpdatedAt?: string) => {
    set({ error: null });
    try {
      const updated = await supersedeBriefApi(briefId, expectedUpdatedAt);
      set((state) => ({
        briefs: state.briefs.map((b) => (b.brief_id === briefId ? updated : b)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to supersede brief.') });
    }
  },

  revertBriefToDraft: async (briefId: string, expectedUpdatedAt?: string) => {
    set({ error: null });
    try {
      const updated = await revertBriefToDraftApi(briefId, expectedUpdatedAt);
      set((state) => ({
        briefs: state.briefs.map((b) => (b.brief_id === briefId ? updated : b)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to revert brief to draft.') });
    }
  },

  cloneBrief: async (briefId: string, newTitle?: string) => {
    set({ error: null });
    try {
      const cloned = await cloneBriefApi(briefId, newTitle);
      set((state) => ({ briefs: [...state.briefs, cloned] }));
      return cloned.brief_id;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to clone brief.') });
      return null;
    }
  },

  branchBrief: async (briefId: string, newTitle?: string, branchReason?: string) => {
    set({ error: null });
    try {
      const branched = await branchBriefApi(briefId, {
        new_title: newTitle,
        branch_reason: branchReason,
      });
      set((state) => ({ briefs: [...state.briefs, branched] }));
      return branched.brief_id;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to branch brief.') });
      return null;
    }
  },

  loadSiblingBriefs: async (briefId: string) => {
    set({ error: null });
    try {
      const result = await listSiblingBriefsApi(briefId);
      set({ siblingBriefs: result.items });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to load sibling briefs.') });
    }
  },

  loadBriefRevisions: async (briefId: string) => {
    set({ error: null });
    try {
      const result = await listBriefRevisions(briefId);
      set({ activeBriefRevisions: result.items });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to load brief revisions.') });
    }
  },

  saveBriefRevision: async (
    briefId: string,
    brief: Record<string, unknown>,
    revisionNotes?: string,
    sourcePipelineId?: string,
  ) => {
    set({ error: null });
    try {
      await saveBriefRevision(briefId, {
        brief,
        revision_notes: revisionNotes,
        source_pipeline_id: sourcePipelineId,
      });
      const result = await listBriefRevisions(briefId);
      set({ activeBriefRevisions: result.items });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to save brief revision.') });
    }
  },

  applyRevision: async (
    briefId: string,
    revisionId: string,
    expectedUpdatedAt?: string,
  ) => {
    set({ error: null });
    try {
      const updated = await applyRevision(briefId, { revision_id: revisionId, expected_updated_at: expectedUpdatedAt });
      set((state) => ({
        briefs: state.briefs.map((b) => (b.brief_id === briefId ? updated : b)),
      }));
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to apply revision.') });
    }
  },

  /**
   * Loads all content gen data in parallel. Errors are caught individually by each
   * load function and set on the store's error state — this function intentionally
   * does not throw so the UI remains usable even if some data fails to load.
   */
  loadAll: async () => {
    await Promise.allSettled([
      get().loadPipelines(),
      get().loadScripts(),
      get().loadPublishQueue(),
      get().loadStrategy(),
      get().loadBacklog(),
      get().loadBriefs(),
    ]);
  },

  reset: () => set(initialState),
}));

export default useContentGen;