import * as React from 'react'

import { cn } from '@/lib/utils'

export const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, onChange, onInput, ...props }, forwardedRef) => {
  const selectRef = React.useRef<HTMLSelectElement | null>(null)

  React.useImperativeHandle(forwardedRef, () => selectRef.current as HTMLSelectElement, [])

  React.useEffect(() => {
    const element = selectRef.current
    if (!element) {
      return
    }

    const emitNativeFallback = () => {
      if (onChange) {
        onChange({
          target: element,
          currentTarget: element,
        } as React.ChangeEvent<HTMLSelectElement>)
      }

      if (onInput) {
        onInput({
          target: element,
          currentTarget: element,
        } as unknown as React.InputEvent<HTMLSelectElement>)
      }
    }

    element.addEventListener('change', emitNativeFallback)
    element.addEventListener('input', emitNativeFallback)
    return () => {
      element.removeEventListener('change', emitNativeFallback)
      element.removeEventListener('input', emitNativeFallback)
    }
  }, [onChange, onInput])

  return (
    <select
      ref={selectRef}
      className={cn(
        'flex h-11 w-full rounded-[0.95rem] border border-input/90 bg-surface/72 px-3.5 py-2 text-sm text-foreground transition-all',
        'focus-visible:border-primary/55 focus-visible:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-0',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      onChange={onChange}
      onInput={onInput}
      {...props}
    >
      {children}
    </select>
  )
})

NativeSelect.displayName = 'NativeSelect'
