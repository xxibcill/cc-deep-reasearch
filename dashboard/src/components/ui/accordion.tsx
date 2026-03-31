'use client';

import * as React from 'react';

import { cn } from '@/lib/utils';

interface AccordionContextValue {
  value: string;
  setValue: (value: string) => void;
}

const AccordionContext = React.createContext<AccordionContextValue | null>(null);

function useAccordionContext() {
  const context = React.useContext(AccordionContext);
  if (!context) {
    throw new Error('Accordion components must be used within an Accordion');
  }
  return context;
}

interface AccordionProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
  onValueChange: (value: string) => void;
}

const Accordion = React.forwardRef<HTMLDivElement, AccordionProps>(
  ({ className, value, onValueChange, children, ...props }, ref) => {
    return (
      <AccordionContext.Provider value={{ value, setValue: onValueChange }}>
        <div className={cn('space-y-2', className)} ref={ref} {...props}>
          {children}
        </div>
      </AccordionContext.Provider>
    );
  }
);
Accordion.displayName = 'Accordion';

interface AccordionItemProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

const AccordionItem = React.forwardRef<HTMLDivElement, AccordionItemProps>(
  ({ className, value, ...props }, ref) => {
    const { value: selectedValue } = useAccordionContext();
    const isOpen = selectedValue === value;

    return (
      <div
        className={cn('rounded-md border border-border', isOpen && 'bg-surface', className)}
        ref={ref}
        {...props}
      />
    );
  }
);
AccordionItem.displayName = 'AccordionItem';

interface AccordionTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

const AccordionTrigger = React.forwardRef<HTMLButtonElement, AccordionTriggerProps & { value: string }>(
  ({ className, children, value, ...props }, ref) => {
    const { value: selectedValue, setValue } = useAccordionContext();
    const isOpen = selectedValue === value;

    return (
      <button
        ref={ref}
        className={cn(
          'flex flex-1 items-center justify-between px-4 py-3 text-sm font-medium transition-all hover:text-foreground [&[data-state=open]>svg]:rotate-180',
          !isOpen && 'text-muted-foreground',
          className
        )}
        onClick={() => setValue(isOpen ? '' : value)}
        data-state={isOpen ? 'open' : 'closed'}
        {...props}
      >
        {children}
        <ChevronIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
      </button>
    );
  }
);
AccordionTrigger.displayName = 'AccordionTrigger';

const ChevronIcon = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="m6 9 6 6 6-6" />
  </svg>
);

interface AccordionContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

const AccordionContent = React.forwardRef<HTMLDivElement, AccordionContentProps & { value: string }>(
  ({ className, children, value, ...props }, ref) => {
    const { value: selectedValue } = useAccordionContext();
    const isOpen = selectedValue === value;

    return (
      <div
        ref={ref}
        className={cn(
          'overflow-hidden text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down',
          isOpen ? 'pb-4' : 'max-h-0 pb-0',
          className
        )}
        data-state={isOpen ? 'open' : 'closed'}
        {...props}
      >
        <div className="px-4">{children}</div>
      </div>
    );
  }
);
AccordionContent.displayName = 'AccordionContent';

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent };