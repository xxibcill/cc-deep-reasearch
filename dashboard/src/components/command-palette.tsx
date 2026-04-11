'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { 
  Search, 
  Home, 
  Settings, 
  Film, 
  GitCompare, 
  Terminal,
  X,
  BarChart3,
  Trophy,
  ScrollText,
  Radar,
  FileText
} from 'lucide-react';
import { cn } from '@/lib/utils';
import useDashboardStore from '@/hooks/useDashboard';

const PALETTE_OPEN_EVENT = 'ccdr.command-palette.open';
const SEQUENCE_TIMEOUT_MS = 900;

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ElementType;
  shortcut?: string;
  action: () => void;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return (
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.isContentEditable ||
    Boolean(target.closest('[contenteditable="true"]'))
  );
}

export function CommandPalette() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const sequenceRef = useRef('');
  const sequenceTimerRef = useRef<number | null>(null);

  const sessions = useDashboardStore((state) => state.sessions);
  const activeSessionMatch = pathname.match(/^\/session\/([^/]+)(?:\/(monitor|report))?$/);
  const activeSessionId = activeSessionMatch?.[1] ?? null;

  const clearSequence = useCallback(() => {
    sequenceRef.current = '';
    if (sequenceTimerRef.current !== null) {
      window.clearTimeout(sequenceTimerRef.current);
      sequenceTimerRef.current = null;
    }
  }, []);

  const restartSequenceTimer = useCallback(() => {
    if (sequenceTimerRef.current !== null) {
      window.clearTimeout(sequenceTimerRef.current);
    }
    sequenceTimerRef.current = window.setTimeout(() => {
      sequenceRef.current = '';
      sequenceTimerRef.current = null;
    }, SEQUENCE_TIMEOUT_MS);
  }, []);

  const focusSessionSearch = useCallback(() => {
    const searchInput = document.querySelector('[data-session-search]') as HTMLInputElement | null;
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
      return;
    }

    router.push('/');
    window.setTimeout(() => {
      const homeSearch = document.querySelector('[data-session-search]') as HTMLInputElement | null;
      homeSearch?.focus();
      homeSearch?.select();
    }, 100);
  }, [router]);

  const commands: CommandItem[] = [
    {
      id: 'home',
      label: 'Go to Home',
      description: 'View sessions and start new research',
      icon: Home,
      shortcut: 'G H',
      action: () => {
        router.push('/');
        setOpen(false);
        clearSequence();
      },
    },
    {
      id: 'analytics',
      label: 'Go to Analytics',
      description: 'Review aggregate operational trends',
      icon: BarChart3,
      shortcut: 'G A',
      action: () => {
        router.push('/analytics');
        setOpen(false);
        clearSequence();
      },
    },
    {
      id: 'benchmark',
      label: 'Go to Benchmark',
      description: 'View evaluation results',
      icon: Trophy,
      shortcut: 'G B',
      action: () => {
        router.push('/benchmark');
        setOpen(false);
        clearSequence();
      },
    },
    {
      id: 'content-studio',
      label: 'Go to Content Studio',
      description: 'Manage production workflows',
      icon: Film,
      shortcut: 'G C',
      action: () => {
        router.push('/content-gen');
        setOpen(false);
        clearSequence();
      },
    },
    {
      id: 'settings',
      label: 'Go to Settings',
      description: 'Configure runtime controls',
      icon: Settings,
      shortcut: 'G S',
      action: () => {
        router.push('/settings');
        setOpen(false);
        clearSequence();
      },
    },
    {
      id: 'compare',
      label: 'Jump to Compare',
      description: 'Compare two sessions side by side',
      icon: GitCompare,
      shortcut: 'G V',
      action: () => {
        router.push('/compare');
        setOpen(false);
        clearSequence();
      },
    },
    {
      id: 'search-sessions',
      label: 'Search Sessions',
      description: 'Filter sessions by name or status',
      icon: Search,
      shortcut: '/',
      action: () => {
        setOpen(false);
        focusSessionSearch();
        clearSequence();
      },
    },
    ...(activeSessionId
      ? [
          {
            id: 'session-overview',
            label: 'Switch to Overview',
            description: 'Open the session summary workspace',
            icon: ScrollText,
            shortcut: 'G O',
            action: () => {
              router.push(`/session/${activeSessionId}`);
              setOpen(false);
              clearSequence();
            },
          },
          {
            id: 'session-monitor',
            label: 'Switch to Monitor',
            description: 'Open the live telemetry workspace',
            icon: Radar,
            shortcut: 'G M',
            action: () => {
              router.push(`/session/${activeSessionId}/monitor`);
              setOpen(false);
              clearSequence();
            },
          },
          {
            id: 'session-report',
            label: 'Switch to Report',
            description: 'Open the report workspace for this session',
            icon: FileText,
            shortcut: 'G R',
            action: () => {
              router.push(`/session/${activeSessionId}/report`);
              setOpen(false);
              clearSequence();
            },
          },
        ]
      : []),
    ...sessions.slice(0, 8).map((session) => ({
      id: `session-${session.sessionId}`,
      label: session.label || `Session ${session.sessionId.slice(0, 8)}`,
      description: `${session.status}${session.createdAt ? ` • ${new Date(session.createdAt).toLocaleDateString()}` : ''}`,
      icon: Terminal,
      action: () => {
        router.push(`/session/${session.sessionId}`);
        setOpen(false);
        clearSequence();
      },
    })),
  ];

  const filteredCommands = query
    ? commands.filter(
        (cmd) =>
          cmd.label.toLowerCase().includes(query.toLowerCase()) ||
          cmd.description?.toLowerCase().includes(query.toLowerCase())
      )
    : commands;

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target;
      const editingOutsidePalette = isEditableTarget(target) && target !== inputRef.current;

      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        clearSequence();
        setOpen((prev) => !prev);
        return;
      }

      if (!open && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey) {
        if (e.key === '/' && !isEditableTarget(target)) {
          e.preventDefault();
          focusSessionSearch();
          clearSequence();
          return;
        }

        if (!editingOutsidePalette) {
          const key = e.key.toLowerCase();
          const currentSequence = sequenceRef.current;

          if (key === 'g') {
            sequenceRef.current = 'g';
            restartSequenceTimer();
            return;
          }

          if (currentSequence === 'g') {
            const commandByShortcutKey: Record<string, () => void> = {
              h: () => router.push('/'),
              a: () => router.push('/analytics'),
              b: () => router.push('/benchmark'),
              c: () => router.push('/content-gen'),
              s: () => router.push('/settings'),
              v: () => router.push('/compare'),
            };

            if (activeSessionId) {
              commandByShortcutKey.o = () => router.push(`/session/${activeSessionId}`);
              commandByShortcutKey.m = () => router.push(`/session/${activeSessionId}/monitor`);
              commandByShortcutKey.r = () => router.push(`/session/${activeSessionId}/report`);
            }

            const action = commandByShortcutKey[key];
            if (action) {
              e.preventDefault();
              action();
              clearSequence();
              return;
            }

            clearSequence();
          }
        }
      }

      if (!open) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
        clearSequence();
        return;
      }

      if (editingOutsidePalette) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, filteredCommands.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter' && filteredCommands[selectedIndex]) {
        e.preventDefault();
        filteredCommands[selectedIndex].action();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    activeSessionId,
    clearSequence,
    filteredCommands,
    focusSessionSearch,
    open,
    restartSequenceTimer,
    router,
    selectedIndex,
  ]);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    const handleOpenEvent = () => {
      setOpen(true);
    };

    window.addEventListener(PALETTE_OPEN_EVENT, handleOpenEvent);
    return () => {
      window.removeEventListener(PALETTE_OPEN_EVENT, handleOpenEvent);
    };
  }, []);

  useEffect(() => () => clearSequence(), [clearSequence]);

  useEffect(() => {
    if (listRef.current) {
      const selected = listRef.current.querySelector('[data-selected="true"]');
      selected?.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  const handleSelect = useCallback((command: CommandItem) => {
    command.action();
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      <div 
        className="fixed inset-0 bg-background/80 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />
      <div className="relative w-full max-w-lg overflow-hidden rounded-[1.2rem] border border-border/70 bg-popover shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center border-b border-border/70 px-4">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search commands..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent px-3 py-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
          <button
            onClick={() => setOpen(false)}
            className="flex h-6 w-6 items-center justify-center rounded border border-border/50 text-muted-foreground hover:bg-surface-raised/75"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
        
        <div ref={listRef} className="max-h-[60vh] overflow-y-auto p-2">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              No commands found
            </div>
          ) : (
            <div className="space-y-1">
              {filteredCommands.map((command, index) => (
                <button
                  key={command.id}
                  data-selected={index === selectedIndex}
                  onClick={() => handleSelect(command)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-[0.8rem] px-3 py-2.5 text-left transition-colors',
                    index === selectedIndex
                      ? 'bg-accent text-accent-foreground'
                      : 'text-foreground hover:bg-surface-raised/75'
                  )}
                >
                  <div className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                    index === selectedIndex ? 'bg-accent/50' : 'bg-surface-raised/75'
                  )}>
                    <command.icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{command.label}</p>
                    {command.description && (
                      <p className="text-xs text-muted-foreground truncate">{command.description}</p>
                    )}
                  </div>
                  {command.shortcut && (
                    <kbd className="hidden shrink-0 items-center gap-1 rounded border border-border/50 bg-background px-1.5 py-0.5 text-[0.65rem] font-medium text-muted-foreground sm:flex">
                      {command.shortcut.split(' ').map((key, i) => (
                        <span key={i} className={i > 0 ? 'opacity-50' : ''}>{key}</span>
                      ))}
                    </kbd>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2 border-t border-border/70 px-4 py-2.5 text-[0.7rem] text-muted-foreground">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border/50 bg-background px-1.5 py-0.5">↑↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border/50 bg-background px-1.5 py-0.5">↵</kbd>
              select
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-border/50 bg-background px-1.5 py-0.5">esc</kbd>
              close
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3 opacity-80">
            <span>Cmd/Ctrl+K open</span>
            <span>G then H/A/B/C/S/V navigate</span>
            {activeSessionId ? <span>G then O/M/R switch tabs</span> : null}
            <span>/ focus session search</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function KeyboardHint() {
  const [showHint, setShowHint] = useState(true);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        setShowHint(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (!showHint) return null;

  return (
    <button
      onClick={() => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT))}
      className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-full border border-border/70 bg-popover/95 px-3 py-2 text-xs text-muted-foreground shadow-lg backdrop-blur-sm transition-opacity hover:bg-surface-raised/75 hover:text-foreground"
    >
      <span className="flex items-center gap-1">
        <kbd className="rounded border border-border/50 bg-background px-1.5 py-0.5 font-medium">⌘</kbd>
        <kbd className="rounded border border-border/50 bg-background px-1.5 py-0.5 font-medium">K</kbd>
      </span>
      <span className="text-[0.7rem]">Palette · GH home · / search</span>
    </button>
  );
}
