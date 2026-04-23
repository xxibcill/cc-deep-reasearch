import { useState, useCallback, useRef, useEffect } from 'react';
import { backlogChatRespond, backlogChatApply } from '@/lib/content-gen/backlog-ai';
import type { BacklogChatMessage, BacklogChatOperation, BacklogChatRespondMode, BacklogItem } from '@/types/content-gen';

export interface TranscriptEntry {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const STORAGE_KEY = 'content-gen-chat-session';

interface UseBacklogChatOptions {
  backlog: BacklogItem[];
  selectedIdeaId: string | null;
  defaultMode?: BacklogChatRespondMode;
}

export interface UseBacklogChatReturn {
  transcript: TranscriptEntry[];
  input: string;
  loading: boolean;
  error: string | null;
  pendingOps: BacklogChatOperation[];
  editMode: boolean;
  setInput: (value: string) => void;
  sendMessage: (content: string) => Promise<void>;
  applyPendingOps: () => Promise<{ applied: number; errors: string[] }>;
  clearTranscript: () => void;
  setEditMode: (value: boolean) => void;
}

function loadPersistedSession(): { transcript: TranscriptEntry[]; draftInput: string } | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveSession(session: { transcript: TranscriptEntry[]; draftInput: string }) {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // ignore
  }
}

function clearSession() {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function useBacklogChat({
  backlog,
  selectedIdeaId,
  defaultMode = 'conversation',
}: UseBacklogChatOptions): UseBacklogChatReturn {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>(() => {
    const saved = loadPersistedSession();
    return saved?.transcript ?? [];
  });
  const [input, setInput] = useState(() => {
    const saved = loadPersistedSession();
    return saved?.draftInput ?? '';
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingOps, setPendingOps] = useState<BacklogChatOperation[]>([]);
  const [editMode, setEditMode] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    saveSession({ transcript, draftInput: input });
  }, [transcript, input]);

  const sendMessage = useCallback(async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;

    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    const userEntry: TranscriptEntry = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
    };

    setTranscript((prev) => [...prev, userEntry]);
    setInput('');
    setError(null);
    setPendingOps([]);
    setLoading(true);

    const mode: BacklogChatRespondMode = trimmed.startsWith('/edit') || trimmed.startsWith('/propose')
      ? 'edit'
      : defaultMode;

    try {
      const messages: BacklogChatMessage[] = transcript
        .map((entry): BacklogChatMessage => ({ role: entry.role, content: entry.content }))
        .concat([{ role: 'user', content: trimmed }]);

      const response = await backlogChatRespond({
        messages,
        backlog_items: backlog,
        selected_idea_id: selectedIdeaId,
        mode,
      });

      const assistantEntry: TranscriptEntry = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.reply_markdown,
      };

      setTranscript((prev) => [...prev, assistantEntry]);

      if (response.apply_ready && response.operations.length > 0) {
        setPendingOps(response.operations);
      }

      if (response.warnings.length > 0) {
        setError(response.warnings.join('; '));
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Failed to get response.');
    } finally {
      setLoading(false);
    }
  }, [backlog, selectedIdeaId, defaultMode, transcript]);

  const applyPendingOps = useCallback(async (): Promise<{ applied: number; errors: string[] }> => {
    if (pendingOps.length === 0) return { applied: 0, errors: [] };

    setLoading(true);
    setError(null);
    try {
      const response = await backlogChatApply({ operations: pendingOps });
      setPendingOps([]);
      clearSession();
      return { applied: response.applied, errors: response.errors };
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to apply changes.';
      return { applied: 0, errors: [errorMsg] };
    } finally {
      setLoading(false);
    }
  }, [pendingOps]);

  const clearTranscript = useCallback(() => {
    setTranscript([]);
    setPendingOps([]);
    setError(null);
    setInput('');
    clearSession();
  }, []);

  return {
    transcript,
    input,
    loading,
    error,
    pendingOps,
    editMode,
    setInput,
    sendMessage,
    applyPendingOps,
    clearTranscript,
    setEditMode,
  };
}