import { create } from 'zustand';
import type {
  ManagedOpportunityBrief,
  BriefRevision,
} from '@/types/content-gen';
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
  listBriefRevisions,
  getBriefRevision,
  saveBriefRevision,
  applyRevision,
} from '@/lib/content-gen/brief';
import { getApiErrorMessage } from '@/lib/api';

interface BriefsState {
  briefs: ManagedOpportunityBrief[];
  briefsLoading: boolean;
  activeBriefId: string | null;
  activeBriefRevisions: BriefRevision[];
  siblingBriefs: ManagedOpportunityBrief[];
  error: string | null;
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
  clearError: () => void;
}

const initialState = {
  briefs: [] as ManagedOpportunityBrief[],
  briefsLoading: false,
  activeBriefId: null as string | null,
  activeBriefRevisions: [] as BriefRevision[],
  siblingBriefs: [] as ManagedOpportunityBrief[],
  error: null as string | null,
};

export const useBriefsStore = create<BriefsState>((set) => ({
  ...initialState,

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

  clearError: () => set({ error: null }),
}));

// Backwards compatibility alias
export const useBriefs = useBriefsStore;