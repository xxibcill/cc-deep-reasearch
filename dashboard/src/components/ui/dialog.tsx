import { cn } from '@/lib/utils';
import { X } from 'lucide-react';
import { createContext, useContext, useState, type ReactNode } from 'react';

interface DialogContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DialogContext = createContext<DialogContextValue | null>(null);

function useDialogContext() {
  const context = useContext(DialogContext);
  if (!context) {
    throw new Error('Dialog components must be used within a Dialog');
  }
  return context;
}

export function Dialog({
  open,
  onOpenChange,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}) {
  return (
    <DialogContext.Provider value={{ open, onOpenChange }}>
      {children}
    </DialogContext.Provider>
  );
}

export function DialogContent({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const { open, onOpenChange } = useDialogContext();

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-500/75 p-4">
      <div className="absolute inset-0" onClick={() => onOpenChange(false)} />
      <div
        className={cn(
          'relative z-10 max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-2xl border bg-neutral-100 shadow-2xl dark:bg-neutral-900',
          className
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function DialogHeader({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn('flex items-center justify-between border-b px-5 py-4', className)}>
      {children}
    </div>
  );
}

export function DialogTitle({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <h2 className={cn('text-lg font-semibold', className)}>{children}</h2>;
}

export function DialogDescription({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <p className={cn('text-sm text-muted-foreground', className)}>{children}</p>;
}

export function DialogBody({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn('max-h-[calc(85vh-4.5rem)] overflow-auto p-5', className)}>{children}</div>;
}

export function DialogClose({
  className,
  onClick,
}: {
  className?: string;
  onClick?: () => void;
}) {
  const { onOpenChange } = useDialogContext();
  return (
    <button
      aria-label="Close dialog"
      className={cn(
        'rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground',
        className
      )}
      onClick={() => {
        onOpenChange(false);
        onClick?.();
      }}
    >
      <X className="h-4 w-4" />
    </button>
  );
}
