'use client';

import { useEffect, useState } from 'react';
import { X } from 'lucide-react';

import { useLocalStorage } from '@/hooks/useLocalStorage';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface HelpCalloutProps {
  id: string;
  title: string;
  content: string;
  className?: string;
}

export function HelpCallout({ id, title, content, className }: HelpCalloutProps) {
  const [dismissed, setDismissed] = useLocalStorage(`help-dismissed-${id}`, false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 100);
    return () => clearTimeout(timer);
  }, []);

  if (dismissed) {
    return null;
  }

  return (
    <div
      className={cn(
        'relative rounded-2xl border border-primary/20 bg-primary/5 p-4 transition-all duration-300',
        isVisible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0',
        className
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">{title}</p>
          <p className="text-sm leading-relaxed text-muted-foreground">{content}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 shrink-0 p-0 text-muted-foreground hover:text-foreground"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss help"
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

interface OnboardingCardProps {
  id: string;
  title: string;
  description: string;
  steps: { label: string; description: string }[];
  className?: string;
}

export function OnboardingCard({ id, title, description, steps, className }: OnboardingCardProps) {
  const [dismissed, setDismissed] = useLocalStorage(`onboarding-dismissed-${id}`, false);

  if (dismissed) {
    return null;
  }

  return (
    <div
      className={cn(
        'rounded-[1.5rem] border border-border/70 bg-card/95 p-6 shadow-sm',
        className
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="eyebrow text-primary">Getting started</p>
          <h2 className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => setDismissed(true)}
        >
          <X className="mr-1 h-4 w-4" />
          Dismiss
        </Button>
      </div>
      <ol className="mt-4 space-y-3">
        {steps.map((step, index) => (
          <li key={index} className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              {index + 1}
            </span>
            <div className="space-y-0.5">
              <p className="text-sm font-medium text-foreground">{step.label}</p>
              <p className="text-xs text-muted-foreground">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
