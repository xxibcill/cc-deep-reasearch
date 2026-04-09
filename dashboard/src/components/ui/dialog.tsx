'use client';

import * as React from 'react';
import { X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

interface DialogContextValue {
  onOpenChange: (open: boolean) => void;
  titleId: string;
  descriptionId: string;
}

const DialogContext = React.createContext<DialogContextValue | null>(null);

function useDialogContext() {
  const context = React.useContext(DialogContext);
  if (!context) {
    throw new Error('Dialog components must be used within a Dialog.');
  }
  return context;
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: DialogProps) {
  const previousFocusRef = React.useRef<HTMLElement | null>(null);
  const titleId = React.useId();
  const descriptionId = React.useId();
  const legacyContent = title !== undefined || description !== undefined || className !== undefined;

  React.useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      requestAnimationFrame(() => {
        const content = document.querySelector<HTMLElement>('[data-dialog-content="true"]');
        content?.focus();
      });
    } else {
      previousFocusRef.current?.focus();
    }
  }, [open]);

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) {
        onOpenChange(false);
      }
    };

    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [open, onOpenChange]);

  if (!open) {
    return null;
  }

  return (
    <DialogContext.Provider value={{ onOpenChange, titleId, descriptionId }}>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
        <div className="absolute inset-0" onClick={() => onOpenChange(false)} aria-hidden="true" />
        {legacyContent ? (
          <DialogContent className={className}>
            {(title || description) && (
              <DialogHeader>
                {title ? <DialogTitle>{title}</DialogTitle> : null}
                {description ? <DialogDescription>{description}</DialogDescription> : null}
              </DialogHeader>
            )}
            <DialogBody>{children}</DialogBody>
          </DialogContent>
        ) : (
          children
        )}
      </div>
    </DialogContext.Provider>
  );
}

export const DialogContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { onOpenChange, titleId, descriptionId } = useDialogContext();

  return (
    <div
      ref={ref}
      data-dialog-content="true"
      className={cn(
        'panel-shell relative z-10 flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-[1.25rem] shadow-2xl',
        className
      )}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      tabIndex={-1}
      {...props}
    >
      <Button
        aria-label="Close dialog"
        className="absolute right-4 top-4 z-10 h-8 px-2 text-muted-foreground"
        onClick={() => onOpenChange(false)}
        type="button"
        variant="ghost"
      >
        <X className="h-4 w-4" />
      </Button>
      {children}
    </div>
  );
});
DialogContent.displayName = 'DialogContent';

export const DialogHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('space-y-2 border-b border-border/70 px-5 py-4 pr-14 text-left', className)}
    {...props}
  />
));
DialogHeader.displayName = 'DialogHeader';

export const DialogTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => {
  const { titleId } = useDialogContext();

  return (
    <h2
      ref={ref}
      className={cn('font-display text-[1.8rem] font-semibold uppercase tracking-[0.02em]', className)}
      id={titleId}
      {...props}
    />
  );
});
DialogTitle.displayName = 'DialogTitle';

export const DialogDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => {
  const { descriptionId } = useDialogContext();

  return (
    <p
      ref={ref}
      className={cn('text-sm text-muted-foreground', className)}
      id={descriptionId}
      {...props}
    />
  );
});
DialogDescription.displayName = 'DialogDescription';

export const DialogBody = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('max-h-[calc(85vh-4.5rem)] overflow-auto px-5 py-5', className)}
    {...props}
  />
));
DialogBody.displayName = 'DialogBody';

export const DialogFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('flex flex-col-reverse gap-2 border-t px-5 py-4 sm:flex-row sm:justify-end', className)}
    {...props}
  />
));
DialogFooter.displayName = 'DialogFooter';
