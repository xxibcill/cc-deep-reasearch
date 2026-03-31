import * as React from 'react'

import { cn } from '@/lib/utils'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'

export function FormField({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('space-y-2', className)} {...props} />
}

export function FormSection({
  className,
  title,
  description,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  title?: string
  description?: string
}) {
  return (
    <fieldset className={cn('space-y-3', className)}>
      {title && (
        <legend className="text-sm font-semibold text-foreground">{title}</legend>
      )}
      {description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}
      <div {...props} />
    </fieldset>
  )
}

export function FieldHint({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn('text-xs text-muted-foreground', className)}
      {...props}
    />
  )
}

export function FieldMeta({
  className,
  left,
  right,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  left?: React.ReactNode
  right?: React.ReactNode
}) {
  return (
    <div
      className={cn('flex items-center justify-between text-xs', className)}
      {...props}
    >
      {left && <span className="text-muted-foreground">{left}</span>}
      {right && <span className="text-muted-foreground">{right}</span>}
    </div>
  )
}

export function FormLabel({
  className,
  required,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof Label> & { required?: boolean }) {
  return (
    <Label className={cn('block', className)} {...props}>
      {children}
      {required ? <span className="ml-1 text-warning">*</span> : null}
    </Label>
  )
}

export function FormDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn('text-sm leading-relaxed text-muted-foreground', className)}
      {...props}
    />
  )
}

export function FormMessage({
  className,
  tone = 'default',
  ...props
}: React.HTMLAttributes<HTMLParagraphElement> & {
  tone?: 'default' | 'error' | 'success'
}) {
  const toneClassName =
    tone === 'error'
      ? 'text-error'
      : tone === 'success'
        ? 'text-success'
        : 'text-muted-foreground'

  return <p className={cn('text-sm leading-relaxed', toneClassName, className)} {...props} />
}

export interface CheckboxRowProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string
  description?: string
}

export function CheckboxRow({
  label,
  description,
  className,
  id,
  ...props
}: CheckboxRowProps) {
  const checkboxId = id || `checkbox-${Math.random().toString(36).slice(2, 9)}`
  return (
    <div className={cn('flex items-start gap-3', className)}>
      <Checkbox id={checkboxId} className="mt-0.5" {...props} />
      <label
        htmlFor={checkboxId}
        className="flex flex-col gap-0.5 cursor-pointer text-sm"
      >
        <span className="text-foreground font-medium">{label}</span>
        {description && (
          <span className="text-muted-foreground text-xs">{description}</span>
        )}
      </label>
    </div>
  )
}

export interface CompactInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode
}

export function CompactInput({ className, icon, ...props }: CompactInputProps) {
  return (
    <div className="relative">
      {icon && (
        <div className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground">
          {icon}
        </div>
      )}
      <input
        className={cn(
          'h-8 w-full rounded border border-input bg-background px-2.5 py-1 text-sm text-foreground',
          'placeholder:text-muted-foreground/60',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-0',
          'disabled:cursor-not-allowed disabled:opacity-50',
          icon && 'pl-8',
          className
        )}
        {...props}
      />
    </div>
  )
}

export interface CompactSelectOption {
  value: string
  label: string
}

export interface CompactSelectProps {
  value: string
  onChange: (value: string) => void
  options: CompactSelectOption[]
  placeholder?: string
  className?: string
}

export function CompactSelect({
  value,
  onChange,
  options,
  placeholder = 'Select',
  className,
}: CompactSelectProps) {
  return (
    <select
      className={cn(
        'h-8 rounded border border-input bg-background px-2.5 py-1 text-sm text-foreground',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-0',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'cursor-pointer',
        className
      )}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export interface FormLayoutProps {
  children: React.ReactNode
  className?: string
}

export function FormLayout({ children, className }: FormLayoutProps) {
  return (
    <div className={cn('grid gap-6', className)}>
      {children}
    </div>
  )
}

export interface FormRowProps {
  label: string
  error?: string
  description?: string
  children: React.ReactNode
  className?: string
}

export function FormRow({
  label,
  error,
  description,
  children,
  className,
}: FormRowProps) {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <label className="text-sm font-medium text-foreground">{label}</label>
      {children}
      {description && !error && (
        <span className="text-xs text-muted-foreground">{description}</span>
      )}
      {error && (
        <span className="text-xs text-error">{error}</span>
      )}
    </div>
  )
}

export interface SettingFieldShellProps {
  label: string
  description: string
  error?: string
  overridden: boolean
  effectiveValue?: string
  persistedValue?: string
  overrideSource?: string[]
  children: React.ReactNode
  className?: string
}

export function SettingFieldShell({
  label,
  description,
  error,
  overridden,
  effectiveValue,
  persistedValue,
  overrideSource,
  children,
  className,
}: SettingFieldShellProps) {
  return (
    <div className={cn('space-y-2 rounded-xl border border-border bg-muted/30 p-3', className)}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium">{label}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
        </div>
        {overridden ? (
          <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-amber-900 dark:bg-amber-900 dark:text-amber-100">
            Env override
          </span>
        ) : null}
      </div>
      {children}
      {overridden ? (
        <p className="text-xs text-amber-900">
          Saved: <span className="font-medium">{persistedValue}</span>. Runtime:{' '}
          <span className="font-medium">{effectiveValue}</span>. Source:{' '}
          {(overrideSource ?? []).join(', ')}
        </p>
      ) : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  )
}
