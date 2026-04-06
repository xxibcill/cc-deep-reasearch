import { useEffect, useState } from 'react';
import { Bookmark, Save, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import {
  SavedView,
  deleteSavedView,
  findMatchingSavedViewName,
  findSavedView,
  loadSavedViews,
  normalizeSavedViewName,
  persistSavedViews,
  upsertSavedView,
} from '@/lib/saved-views';

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
  sanitizeStoredValue: (value: unknown) => T;
  sanitizeForSave: (value: T) => T;
  sanitizeForApply: (value: T) => T;
  isEqual: (left: T, right: T) => boolean;
  onApply: (value: T) => void;
}

export function SavedViewControls<T>({
  storageKey,
  title,
  description,
  itemLabel,
  testIdPrefix,
  selectLabel,
  inputLabel,
  emptyState,
  currentValue,
  sanitizeStoredValue,
  sanitizeForSave,
  sanitizeForApply,
  isEqual,
  onApply,
}: SavedViewControlsProps<T>) {
  const [views, setViews] = useState<SavedView<T>[]>([]);
  const [selectedName, setSelectedName] = useState('');
  const [draftName, setDraftName] = useState('');
  const [composerOpen, setComposerOpen] = useState(false);

  useEffect(() => {
    setViews(loadSavedViews(storageKey, sanitizeStoredValue));
  }, [sanitizeStoredValue, storageKey]);

  const normalizedCurrentValue = sanitizeForSave(currentValue);
  const activeViewName = findMatchingSavedViewName(
    views,
    normalizedCurrentValue,
    (left, right) => isEqual(sanitizeForApply(left), sanitizeForApply(right))
  );
  const selectedView = findSavedView(views, selectedName);
  const nameAlreadyExists = draftName.trim().length > 0
    && views.some((view) => normalizeSavedViewName(view.name) === normalizeSavedViewName(draftName));

  useEffect(() => {
    if (selectedName && selectedView) {
      return;
    }
    setSelectedName(activeViewName ?? '');
  }, [activeViewName, selectedName, selectedView]);

  const openComposer = () => {
    setDraftName(activeViewName ?? selectedName);
    setComposerOpen(true);
  };

  const handleSave = () => {
    const nextViews = upsertSavedView(views, draftName, normalizedCurrentValue);
    if (nextViews === views) {
      return;
    }
    persistSavedViews(storageKey, nextViews);
    setViews(nextViews);
    setSelectedName(draftName.trim().replace(/\s+/g, ' '));
    setComposerOpen(false);
    setDraftName('');
  };

  const handleApply = () => {
    if (!selectedView) {
      return;
    }
    onApply(sanitizeForApply(selectedView.value));
  };

  const handleDelete = () => {
    if (!selectedView) {
      return;
    }
    const nextViews = deleteSavedView(views, selectedView.name);
    persistSavedViews(storageKey, nextViews);
    setViews(nextViews);
    setSelectedName('');
  };

  return (
    <div
      className="rounded-[1rem] border border-border/70 bg-surface/55 p-3"
      data-testid={`${testIdPrefix}-controls`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            <Bookmark className="h-3.5 w-3.5" />
            {title}
          </div>
          <p className="text-xs leading-5 text-muted-foreground">{description}</p>
        </div>
        {activeViewName ? (
          <Badge variant="outline" className="bg-surface-raised/80">
            Current: {activeViewName}
          </Badge>
        ) : null}
      </div>

      <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-end">
        <Select
          label={selectLabel}
          value={selectedName}
          options={views.map((view) => view.name)}
          onChange={setSelectedName}
          emptyLabel="Choose view"
          testId={`${testIdPrefix}-select`}
          className="h-9 bg-surface-raised/72"
          labelClassName="min-w-0 flex-1 gap-1 text-[11px] tracking-[0.18em] text-muted-foreground"
        />
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleApply}
            disabled={!selectedView}
            data-testid={`${testIdPrefix}-apply`}
          >
            Apply
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={handleDelete}
            disabled={!selectedView}
            data-testid={`${testIdPrefix}-delete`}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={openComposer}
            data-testid={`${testIdPrefix}-save-current`}
          >
            <Save className="h-3.5 w-3.5" />
            Save Current
          </Button>
        </div>
      </div>

      {composerOpen ? (
        <div className="mt-3 grid gap-3 rounded-[0.95rem] border border-border/60 bg-surface-raised/50 p-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <label className="min-w-0">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {inputLabel}
            </span>
            <Input
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              placeholder="e.g. Active failures"
              className="h-9 bg-surface/80"
              aria-label={inputLabel}
              data-testid={`${testIdPrefix}-name`}
            />
          </label>
          <div className="flex flex-wrap items-end gap-2">
            <Button
              type="button"
              size="sm"
              onClick={handleSave}
              disabled={draftName.trim().length === 0}
              data-testid={`${testIdPrefix}-save`}
            >
              {nameAlreadyExists ? 'Overwrite' : 'Save'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setComposerOpen(false);
                setDraftName('');
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {!composerOpen && views.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">{emptyState}</p>
      ) : null}
    </div>
  );
}
