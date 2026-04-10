'use client';

import { useState } from 'react';

interface SavedViewControlsProps<T> {
  storageKey: string;
  title: string;
  description: string;
  itemLabel: string;
  testIdPrefix: string;
  selectLabel: string;
  inputLabel: string;
  emptyState: string;
  currentValue: T;
  sanitizeStoredValue: (value: unknown) => T | null;
  sanitizeForSave: (value: T) => T;
  sanitizeForApply: (value: T) => T;
  isEqual: (a: T, b: T) => boolean;
  onApply: (value: T) => void;
}

export function SavedViewControls<T>({
  title,
  description,
  itemLabel,
  selectLabel,
  inputLabel,
  emptyState,
  currentValue,
  onApply,
}: SavedViewControlsProps<T>) {
  const [selectedValue, setSelectedValue] = useState<T | null>(null);

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {emptyState && <p className="text-xs text-muted-foreground">{emptyState}</p>}
    </div>
  );
}
