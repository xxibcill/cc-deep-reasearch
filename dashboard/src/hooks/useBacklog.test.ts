import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useBacklogStore } from './useBacklog';
import type { BacklogItem } from '@/types/content-gen';

// Mock the API module
vi.mock('@/lib/content-gen/backlog', () => ({
  listBacklog: vi.fn(),
  updateBacklogItem: vi.fn(),
  selectBacklogItem: vi.fn(),
  archiveBacklogItem: vi.fn(),
  deleteBacklogItem: vi.fn(),
  createBacklogItem: vi.fn(),
  startBacklogItem: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  getApiErrorMessage: vi.fn((_, fallback) => fallback),
}));

import {
  listBacklog,
  updateBacklogItem,
  selectBacklogItem,
  archiveBacklogItem,
  deleteBacklogItem,
  createBacklogItem,
  startBacklogItem,
} from '@/lib/content-gen/backlog';

const mockBacklogItem = (overrides: Partial<BacklogItem> = {}): BacklogItem => ({
  idea_id: 'test-001',
  title: 'Test Idea',
  idea: 'Test idea content',
  one_line_summary: 'Test summary',
  category: 'trend-responsive',
  status: 'backlog',
  risk_level: 'medium',
  priority_score: 7.0,
  latest_score: 75,
  latest_recommendation: 'produce_now',
  audience: 'Test audience',
  problem: 'Test problem',
  emotional_driver: 'Curiosity',
  urgency_level: 'medium',
  why_now: 'Timely topic',
  hook: 'Test hook',
  content_type: 'Short video',
  key_message: 'Key message',
  call_to_action: 'Subscribe',
  evidence: 'Evidence text',
  source_theme: 'AI',
  created_at: '2026-04-01T10:00:00Z',
  updated_at: '2026-04-01T10:00:00Z',
  ...overrides,
} as BacklogItem);

describe('useBacklogStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const { result } = renderHook(() => useBacklogStore());
    act(() => {
      result.current.reset();
    });
  });

  describe('mergeBacklogItems', () => {
    it('does nothing for empty items array', () => {
      const { result } = renderHook(() => useBacklogStore());

      act(() => {
        result.current.mergeBacklogItems([]);
      });

      expect(result.current.backlog).toEqual([]);
    });

    it('adds new items to empty backlog', () => {
      const { result } = renderHook(() => useBacklogStore());

      const newItems = [
        mockBacklogItem({ idea_id: 'new-001' }),
        mockBacklogItem({ idea_id: 'new-002' }),
      ];

      act(() => {
        result.current.mergeBacklogItems(newItems);
      });

      expect(result.current.backlog).toHaveLength(2);
      expect(result.current.backlog[0].idea_id).toBe('new-001');
      expect(result.current.backlog[1].idea_id).toBe('new-002');
    });

    it('replaces existing items with same idea_id', () => {
      const { result } = renderHook(() => useBacklogStore());

      const existingItem = mockBacklogItem({
        idea_id: 'existing-001',
        title: 'Original Title',
        priority_score: 5.0,
      });

      act(() => {
        result.current.mergeBacklogItems([existingItem]);
      });

      const updatedItem = mockBacklogItem({
        idea_id: 'existing-001',
        title: 'Updated Title',
        priority_score: 8.5,
      });

      act(() => {
        result.current.mergeBacklogItems([updatedItem]);
      });

      expect(result.current.backlog).toHaveLength(1);
      expect(result.current.backlog[0].title).toBe('Updated Title');
      expect(result.current.backlog[0].priority_score).toBe(8.5);
    });

    it('adds new items while preserving existing ones', () => {
      const { result } = renderHook(() => useBacklogStore());

      act(() => {
        result.current.mergeBacklogItems([mockBacklogItem({ idea_id: 'existing-001' })]);
      });

      act(() => {
        result.current.mergeBacklogItems([mockBacklogItem({ idea_id: 'new-001' })]);
      });

      expect(result.current.backlog).toHaveLength(2);
      expect(result.current.backlog.map((i) => i.idea_id)).toContain('existing-001');
      expect(result.current.backlog.map((i) => i.idea_id)).toContain('new-001');
    });

    it('demotes previously selected item when new selection arrives', () => {
      const { result } = renderHook(() => useBacklogStore());

      const previouslySelected = mockBacklogItem({
        idea_id: 'old-selected',
        status: 'selected',
        selection_reasoning: 'Was selected',
      });

      act(() => {
        result.current.mergeBacklogItems([previouslySelected]);
      });

      expect(result.current.backlog[0].status).toBe('selected');

      const newlySelected = mockBacklogItem({
        idea_id: 'new-selected',
        status: 'selected',
        selection_reasoning: 'New selection',
      });

      act(() => {
        result.current.mergeBacklogItems([newlySelected]);
      });

      const oldItem = result.current.backlog.find((i) => i.idea_id === 'old-selected');
      const newItem = result.current.backlog.find((i) => i.idea_id === 'new-selected');

      expect(oldItem?.status).toBe('backlog');
      expect(oldItem?.selection_reasoning).toBe('');
      expect(newItem?.status).toBe('selected');
    });

    it('keeps selected item status when new selection does not contain selected item', () => {
      const { result } = renderHook(() => useBacklogStore());

      const selectedItem = mockBacklogItem({
        idea_id: 'selected-001',
        status: 'selected',
        selection_reasoning: 'Selected',
      });

      act(() => {
        result.current.mergeBacklogItems([selectedItem]);
      });

      // Merge with non-selected items
      act(() => {
        result.current.mergeBacklogItems([
          mockBacklogItem({ idea_id: 'other-001', status: 'backlog' }),
        ]);
      });

      const item = result.current.backlog.find((i) => i.idea_id === 'selected-001');
      expect(item?.status).toBe('selected');
    });
  });

  describe('API error handling', () => {
    it('sets error message on API failure', async () => {
      vi.mocked(listBacklog).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useBacklogStore());

      await act(async () => {
        await result.current.loadBacklog();
      });

      await waitFor(() => {
        expect(result.current.error).toBeTruthy();
      });
    });

    it('clears error when clearError is called', async () => {
      vi.mocked(listBacklog).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useBacklogStore());

      await act(async () => {
        await result.current.loadBacklog();
      });

      await waitFor(() => {
        expect(result.current.error).toBeTruthy();
      });

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });
});