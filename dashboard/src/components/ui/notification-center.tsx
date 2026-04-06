'use client';

import Link from 'next/link';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Info,
  X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type NotificationVariant = 'success' | 'info' | 'warning' | 'destructive';

interface NotificationAction {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface NotificationInput {
  title: string;
  description?: string;
  variant?: NotificationVariant;
  durationMs?: number;
  persistent?: boolean;
  actions?: NotificationAction[];
}

interface NotificationRecord extends NotificationInput {
  id: string;
  variant: NotificationVariant;
  persistent: boolean;
}

interface NotificationContextValue {
  notify: (notification: NotificationInput) => string;
  dismiss: (id: string) => void;
  dismissAll: () => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

const DEFAULT_DURATION_MS = 4500;

function notificationIcon(variant: NotificationVariant) {
  switch (variant) {
    case 'success':
      return <CheckCircle2 className="h-4.5 w-4.5 text-success" />;
    case 'warning':
      return <Clock3 className="h-4.5 w-4.5 text-warning" />;
    case 'destructive':
      return <AlertCircle className="h-4.5 w-4.5 text-error" />;
    default:
      return <Info className="h-4.5 w-4.5 text-primary" />;
  }
}

function notificationTone(variant: NotificationVariant): string {
  switch (variant) {
    case 'success':
      return 'border-success/30 bg-[linear-gradient(180deg,rgba(20,83,45,0.16),rgba(10,18,16,0.96))]';
    case 'warning':
      return 'border-warning/30 bg-[linear-gradient(180deg,rgba(133,77,14,0.18),rgba(18,16,12,0.96))]';
    case 'destructive':
      return 'border-error/30 bg-[linear-gradient(180deg,rgba(127,29,29,0.18),rgba(22,13,13,0.97))]';
    default:
      return 'border-primary/25 bg-[linear-gradient(180deg,rgba(37,99,235,0.16),rgba(12,17,27,0.97))]';
  }
}

function NotificationCard({
  notification,
  onDismiss,
}: {
  notification: NotificationRecord;
  onDismiss: (id: string) => void;
}) {
  return (
    <article
      className={cn(
        'pointer-events-auto w-full rounded-[1rem] border px-4 py-3 shadow-[0_18px_50px_rgba(0,0,0,0.24)] backdrop-blur-sm',
        notificationTone(notification.variant)
      )}
      role="status"
      aria-live={notification.variant === 'destructive' || notification.variant === 'warning' ? 'assertive' : 'polite'}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 shrink-0">{notificationIcon(notification.variant)}</div>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm font-semibold text-foreground">{notification.title}</p>
          {notification.description ? (
            <p className="text-sm leading-6 text-muted-foreground">{notification.description}</p>
          ) : null}
          {notification.actions?.length ? (
            <div className="flex flex-wrap gap-2 pt-1">
              {notification.actions.map((action) =>
                action.href ? (
                  <Link key={`${notification.id}-${action.label}`} href={action.href} className="inline-flex">
                    <Button size="sm" variant="outline">
                      {action.label}
                    </Button>
                  </Link>
                ) : (
                  <Button
                    key={`${notification.id}-${action.label}`}
                    size="sm"
                    variant="outline"
                    onClick={action.onClick}
                  >
                    {action.label}
                  </Button>
                )
              )}
            </div>
          ) : null}
        </div>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => onDismiss(notification.id)}
          aria-label="Dismiss notification"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </article>
  );
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const timeoutMap = useRef<Map<string, number>>(new Map());

  const dismiss = useCallback((id: string) => {
    const timeoutId = timeoutMap.current.get(id);
    if (timeoutId) {
      window.clearTimeout(timeoutId);
      timeoutMap.current.delete(id);
    }

    setNotifications((current) => current.filter((notification) => notification.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    for (const timeoutId of timeoutMap.current.values()) {
      window.clearTimeout(timeoutId);
    }
    timeoutMap.current.clear();
    setNotifications([]);
  }, []);

  const notify = useCallback(
    ({
      variant = 'info',
      durationMs = DEFAULT_DURATION_MS,
      persistent = variant === 'destructive' || variant === 'warning',
      ...notification
    }: NotificationInput) => {
      const id = `note-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setNotifications((current) => [
        {
          id,
          variant,
          persistent,
          durationMs,
          ...notification,
        },
        ...current,
      ]);

      if (!persistent) {
        const timeoutId = window.setTimeout(() => {
          dismiss(id);
        }, durationMs);
        timeoutMap.current.set(id, timeoutId);
      }

      return id;
    },
    [dismiss]
  );

  useEffect(() => {
    const activeTimeouts = timeoutMap.current
    return () => {
      for (const timeoutId of activeTimeouts.values()) {
        window.clearTimeout(timeoutId);
      }
      activeTimeouts.clear();
    };
  }, []);

  const value = useMemo(
    () => ({
      notify,
      dismiss,
      dismissAll,
    }),
    [dismiss, dismissAll, notify]
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-[5.5rem] z-[70] flex w-full max-w-sm flex-col gap-3 sm:right-6">
        {notifications.map((notification) => (
          <NotificationCard
            key={notification.id}
            notification={notification}
            onDismiss={dismiss}
          />
        ))}
      </div>
    </NotificationContext.Provider>
  );
}

export function useNotifications(): NotificationContextValue {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}
