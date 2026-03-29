# Design System Extraction Plan

## Executive Summary

This document outlines the systematic extraction of reusable components, patterns, and design tokens from the CC Deep Research dashboard into a cohesive design system. The goal is to improve consistency, reduce code duplication, and make the UI more maintainable.

## Current State Analysis

### Existing Design System Infrastructure

**Location:** `dashboard/src/components/ui/`

**Current Components:**
- `button.tsx` - Button variants (default, outline, ghost, destructive) with sizes
- `card.tsx` - Card container with header, title, description, content
- `badge.tsx` - Status badges with variants (default, secondary, success, warning, destructive, outline)
- `scroll-area.tsx` - Scrollable container
- `alert-dialog.tsx` - Modal dialogs
- `dialog.tsx` - Dialog component
- `select.tsx` - Select dropdown
- `tabs.tsx` - Tab navigation (default, prominent variants)

**Design Tokens:** CSS custom properties in `globals.css`
- Colors: background, foreground, card, primary, secondary, muted, accent, destructive, border, input, ring
- Radius: 0.75rem (12px)
- Dark mode support via `.dark` class

### Problems Identified

1. **Hard-coded Colors:** Extensive use of hard-coded Tailwind colors (`bg-slate-100`, `bg-green-100`, `bg-amber-100`, `bg-red-50`, etc.) instead of semantic tokens
2. **Inconsistent Spacing:** Mixed spacing patterns (`gap-2`, `gap-1.5`, `gap-3`, `space-y-4`)
3. **Repeated Status Badge Patterns:** Multiple implementations of status badges (Live, Archived, etc.) with hard-coded colors
4. **Form Element Patterns:** Repeated form input styling without reusable components
5. **Icon + Text Patterns:** Common layouts with icons and text not abstracted
6. **Alert/Notice Patterns:** Multiple implementations of alert boxes with different styles
7. **Loading States:** Repeated loading spinner implementations
8. **Empty States:** Multiple empty state variations

## Extraction Plan

### Phase 1: Design Tokens (Priority: HIGH)

Create semantic design tokens to replace hard-coded values throughout the codebase.

#### 1.1 Color Tokens

**Current Issues:**
- 67 occurrences of hard-coded colors like `bg-slate-100`, `bg-blue-50`, `bg-red-200`, `bg-green-100`, `bg-amber-100`

**New Tokens to Add to `globals.css`:**

```css
:root {
  /* Status Colors - Light Mode */
  --status-success-bg: 142 76% 96%;
  --status-success-text: 142 76% 28%;
  --status-success-border: 142 76% 88%;

  --status-warning-bg: 43 96% 89%;
  --status-warning-text: 43 96% 20%;
  --status-warning-border: 43 96% 80%;

  --status-error-bg: 0 72% 92%;
  --status-error-text: 0 72% 38%;
  --status-error-border: 0 72% 85%;

  --status-info-bg: 197 76% 94%;
  --status-info-text: 197 76% 38%;
  --status-info-border: 197 76% 88%;

  --status-neutral-bg: 215 25% 93%;
  --status-neutral-text: 215 25% 37%;
  --status-neutral-border: 215 25% 85%;

  /* Dark mode equivalents */
  --status-success-bg-dark: 142 76% 18%;
  --status-success-text-dark: 142 76% 92%;
  /* ... etc for other status colors */
}

.dark {
  --status-success-bg: var(--status-success-bg-dark);
  --status-success-text: var(--status-success-text-dark);
  /* ... etc */
}
```

**Usage in Tailwind:**
```typescript
// Replace:
className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900 dark:text-green-100"

// With:
className="rounded-full bg-status-success px-2 py-0.5 text-xs font-medium text-status-success-foreground"
```

#### 1.2 Spacing Tokens

**Current Issues:**
- Inconsistent gap usage: `gap-1`, `gap-1.5`, `gap-2`, `gap-2.5`, `gap-3`, `gap-4`

**Recommendation:**
Use Tailwind's default spacing scale consistently:
- `gap-2` (0.5rem) - tight spacing (icon + text)
- `gap-3` (0.75rem) - normal spacing (related items)
- `gap-4` (1rem) - loose spacing (sections)

#### 1.3 Typography Tokens

**Current Patterns:**
- Labels: `text-sm font-medium`
- Descriptions: `text-xs text-muted-foreground`
- Section headers: `text-xs font-medium uppercase tracking-wide text-muted-foreground`

**Tailwind Classes to Define as Utilities:**
```css
@layer components {
  .label-text {
    @apply text-sm font-medium;
  }

  .description-text {
    @apply text-xs text-muted-foreground;
  }

  .section-header {
    @apply text-xs font-medium uppercase tracking-wide text-muted-foreground;
  }
}
```

### Phase 2: Component Extraction (Priority: HIGH)

#### 2.1 Status Badge Component

**Current Usage:** Scattered implementations in `session-list.tsx`, `config-editor.tsx`, `agent-timeline.tsx`, `decision-graph.tsx`

**Extract to:** `dashboard/src/components/ui/status-badge.tsx`

**Variants to Support:**
- `live` - green, for active sessions
- `archived` - amber, for archived items
- `success` - green, for successful states
- `warning` - amber, for warnings
- `error` - red, for errors
- `info` - blue, for informational
- `neutral` - gray, for generic status

**Props Interface:**
```typescript
interface StatusBadgeProps {
  variant: 'live' | 'archived' | 'success' | 'warning' | 'error' | 'info' | 'neutral';
  children: React.ReactNode;
  size?: 'sm' | 'md';
}
```

**Implementation:**
```tsx
export function StatusBadge({ variant, children, size = 'sm' }: StatusBadgeProps) {
  const variants = {
    live: 'bg-status-success text-status-success-foreground',
    archived: 'bg-status-warning text-status-warning-foreground',
    // ... etc
  };

  return (
    <span className={cn(
      'inline-flex items-center rounded-full font-medium',
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
      variants[variant]
    )}>
      {children}
    </span>
  );
}
```

**Migration Targets:**
- [session-list.tsx:219-225](dashboard/src/components/session-list.tsx#L219-L225) - Live/Archive badges
- [session-list.tsx:234-242](dashboard/src/components/session-list.tsx#L234-L242) - Depth/Payload/Report badges
- [config-editor.tsx:582](dashboard/src/components/config-editor.tsx#L582) - Field badges
- [config-secrets-panel.tsx:224](dashboard/src/components/config-secrets-panel.tsx#L224) - Secret badges

#### 2.2 Form Input Components

**Current Usage:** Repeated form styling in `start-research-form.tsx`, `config-editor.tsx`, `config-secrets-panel.tsx`

**Extract to:**
- `dashboard/src/components/ui/input.tsx` - Text input
- `dashboard/src/components/ui/textarea.tsx` - Textarea
- `dashboard/src/components/ui/label.tsx` - Form label
- `dashboard/src/components/ui/form-field.tsx` - Compound field with label + input

**Current Patterns to Standardize:**

**Input Pattern (from start-research-form.tsx:123, 159):**
```tsx
className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
```

**Label Pattern (from start-research-form.tsx:115, 130, 149):**
```tsx
<label htmlFor="query" className="block text-sm font-medium mb-2">
```

**Extracted Components:**

```tsx
// input.tsx
export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-ring',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        className
      )}
      {...props}
    />
  );
}

// label.tsx
export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn('block text-sm font-medium mb-2', className)}
      {...props}
    />
  );
}

// form-field.tsx
interface FormFieldProps {
  label: string;
  description?: string;
  error?: string;
  children: React.ReactNode;
}

export function FormField({ label, description, error, children }: FormFieldProps) {
  return (
    <div>
      <Label>{label}</Label>
      {description && (
        <p className="text-xs text-muted-foreground mt-1 mb-2">{description}</p>
      )}
      {children}
      {error && (
        <p className="text-sm text-status-error mt-1">{error}</p>
      )}
    </div>
  );
}
```

**Migration Targets:**
- [start-research-form.tsx:114-126](dashboard/src/components/start-research-form.tsx#L114-L126) - Query textarea
- [start-research-form.tsx:128-146](dashboard/src/components/start-research-form.tsx#L128-L146) - Depth select
- [start-research-form.tsx:148-163](dashboard/src/components/start-research-form.tsx#L148-L163) - Min sources input
- [config-editor.tsx](dashboard/src/components/config-editor.tsx) - All form fields
- [config-secrets-panel.tsx](dashboard/src/components/config-secrets-panel.tsx) - Secret fields

#### 2.3 Alert/Notice Component

**Current Usage:** Multiple implementations with different styles
- [session-list.tsx:386-401](dashboard/src/components/session-list.tsx#L386-L401) - Error state
- [session-list.tsx:624-632](dashboard/src/components/session-list.tsx#L624-L632) - Force delete warning
- [start-research-form.tsx:230-233](dashboard/src/components/start-research-form.tsx#L230-L233) - Error alert

**Extract to:** `dashboard/src/components/ui/alert.tsx`

**Variants:**
- `error` - red background
- `warning` - amber background
- `info` - blue background
- `success` - green background

**Props Interface:**
```typescript
interface AlertProps {
  variant?: 'error' | 'warning' | 'info' | 'success';
  title?: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
}
```

**Implementation:**
```tsx
export function Alert({ variant = 'info', title, children, icon }: AlertProps) {
  const variants = {
    error: 'bg-status-error-bg/50 border-status-error-border text-status-error-text',
    warning: 'bg-status-warning-bg/50 border-status-warning-border text-status-warning-text',
    info: 'bg-status-info-bg/50 border-status-info-border text-status-info-text',
    success: 'bg-status-success-bg/50 border-status-success-border text-status-success-text',
  };

  const defaultIcons = {
    error: <AlertCircle className="h-5 w-5" />,
    warning: <AlertTriangle className="h-5 w-5" />,
    info: <Info className="h-5 w-5" />,
    success: <CheckCircle className="h-5 w-5" />,
  };

  return (
    <div className={cn('rounded-md border p-4', variants[variant])}>
      <div className="flex items-start gap-3">
        {icon || defaultIcons[variant]}
        <div className="space-y-1">
          {title && <p className="font-medium">{title}</p>}
          <div className="text-sm">{children}</div>
        </div>
      </div>
    </div>
  );
}
```

**Migration Targets:**
- [session-list.tsx:386-401](dashboard/src/components/session-list.tsx#L386-L401) - ErrorState component
- [start-research-form.tsx:230-233](dashboard/src/components/start-research-form.tsx#L230-L233) - Error message
- [start-research-form.tsx:619-632](dashboard/src/components/start-research-form.tsx#L619-L632) - Force delete warning
- [config-editor.tsx](dashboard/src/components/config-editor.tsx) - Validation errors

#### 2.4 Icon+Text Layout Component

**Current Usage:** Very common pattern for icon + label/value pairs
- [session-list.tsx:246-262](dashboard/src/components/session-list.tsx#L246-L262) - Status/Sources/Time fields

**Extract to:** `dashboard/src/components/ui/icon-text.tsx`

**Implementation:**
```tsx
interface IconTextProps {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  labelWidth?: string;
}

export function IconText({ icon, label, value, labelWidth = 'auto' }: IconTextProps) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <div className="text-muted-foreground shrink-0">{icon}</div>
      <span className="text-muted-foreground" style={{ minWidth: labelWidth }}>
        {label}:
      </span>
      <span className="font-medium truncate">{value}</span>
    </div>
  );
}
```

**Migration Targets:**
- [session-list.tsx:246-262](dashboard/src/components/session-list.tsx#L246-L262) - Status/Sources/Time
- Similar patterns in other components

#### 2.5 Loading Spinner Component

**Current Usage:**
- [session-list.tsx:377-381](dashboard/src/components/session-list.tsx#L377-L381) - LoadingState

**Extract to:** `dashboard/src/components/ui/loading.tsx`

**Implementation:**
```tsx
interface LoadingProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
}

export function Loading({ size = 'md', text }: LoadingProps) {
  const sizes = {
    sm: 'h-6 w-6 border-2',
    md: 'h-12 w-12 border-b-2',
    lg: 'h-16 w-16 border-4',
  };

  return (
    <div className="flex min-h-48 items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className={cn('animate-spin rounded-full border-blue-600', sizes[size])} />
        {text && <p className="text-sm text-muted-foreground">{text}</p>}
      </div>
    </div>
  );
}
```

#### 2.6 Empty State Component

**Current Usage:**
- [session-list.tsx:405-429](dashboard/src/components/session-list.tsx#L405-L429) - EmptyState
- [derived-outputs-panel.tsx:53-54](dashboard/src/components/derived-outputs-panel.tsx#L53-L54)

**Extract to:** `dashboard/src/components/ui/empty-state.tsx`

**Implementation:**
```tsx
interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  const defaultIcon = <Network className="h-16 w-16 text-muted-foreground" />;

  return (
    <div className="py-12 text-center">
      <div className="mx-auto mb-4 flex justify-center text-muted-foreground">
        {icon || defaultIcon}
      </div>
      <p className="mb-2 text-xl text-muted-foreground">{title}</p>
      {description && (
        <p className="text-muted-foreground">{description}</p>
      )}
      {action && (
        <Button className="mt-4" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
```

### Phase 3: Pattern Documentation (Priority: MEDIUM)

#### 3.1 Component Storybook

Create a documentation site showing all components with:
- Live examples
- Props API documentation
- Usage guidelines
- Accessibility notes

**Recommended Tool:** [Storybook](https://storybook.js.org/) or [Docz](https://www.docz.site/)

#### 3.2 Design Guidelines Document

Create `DESIGN_GUIDELINES.md` with:
- Color usage guidelines (when to use each status color)
- Spacing guidelines (gap hierarchy)
- Typography hierarchy
- Component composition patterns
- Accessibility standards

## Migration Strategy

### Rollout Plan

**Week 1: Design Tokens**
1. Add new color tokens to `globals.css`
2. Update Tailwind config to recognize new tokens
3. Migrate 2-3 components as proof of concept

**Week 2: Core Components**
1. Create `StatusBadge` component
2. Create form input components (`Input`, `Textarea`, `Label`, `FormField`)
3. Migrate `start-research-form.tsx` and `config-editor.tsx`

**Week 3: UI Components**
1. Create `Alert` component
2. Create `Loading` and `EmptyState` components
3. Migrate remaining components

**Week 4: Polish & Documentation**
1. Complete migration
2. Create component documentation
3. Update accessibility
4. Clean up unused styles

### Testing Strategy

For each extracted component:
1. **Visual Regression:** Take screenshots before/after migration
2. **Functional Testing:** Verify all interactions still work
3. **Accessibility Testing:** Check keyboard navigation, screen readers
4. **Dark Mode Testing:** Verify both light and dark modes

### Rollback Plan

- Keep old component implementations in `components/legacy/` during migration
- Use feature flags if needed for gradual rollout
- Git commits per component for easy reversion

## Success Metrics

**Quantitative:**
- Reduce hard-coded color usage by 80%
- Reduce code duplication in forms by 60%
- Reduce total CSS classes by 30%

**Qualitative:**
- Consistent styling across all components
- Faster feature development (reuse vs. rebuild)
- Easier maintenance (single source of truth)
- Better accessibility out of the box

## Open Questions

1. **Animation Style:** Should we define standard animation patterns (fade-in, slide-up)?
2. **Responsive Breakpoints:** Current responsive classes are ad-hoc. Should we standardize?
3. **Component Variants:** Some components have many variants (e.g., tabs). Should we add more or consolidate?
4. **Design System Location:** Should we move to a separate package or keep in-repo?

## Next Steps

1. **Get Approval:** Review this plan with the team
2. **Set Up Infrastructure:** Add Storybook or similar
3. **Start with Phase 1:** Begin design token implementation
4. **Iterate:** Create components incrementally with feedback

---

**Document Version:** 1.0
**Last Updated:** 2025-03-28
**Author:** Extracted from CC Deep Research dashboard codebase analysis
