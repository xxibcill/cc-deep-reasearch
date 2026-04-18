'use client'

import type { KeyboardEvent } from 'react'
import { useState } from 'react'
import { X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'

export function TagInput({
  value = [],
  onChange,
  placeholder = 'Add item…',
  disabled = false,
  className,
}: {
  value?: string[]
  onChange?: (tags: string[]) => void
  placeholder?: string
  disabled?: boolean
  className?: string
}) {
  const [inputValue, setInputValue] = useState('')

  const addTag = (raw: string) => {
    const tag = raw.trim()
    if (!tag || value.includes(tag)) return
    onChange?.([...value, tag])
    setInputValue('')
  }

  const removeTag = (tag: string) => {
    onChange?.(value.filter((t) => t !== tag))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(inputValue)
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      removeTag(value[value.length - 1])
    }
  }

  return (
    <div
      className={`flex min-h-[52px] flex-wrap gap-2 rounded-[0.95rem] border border-input/90 bg-surface/72 px-3 py-2.5 transition-all focus-within:border-primary/55 focus-within:bg-surface-raised focus-within:ring-2 focus-within:ring-ring/30 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-text'} ${className ?? ''}`}
      onClick={() => {
        if (!disabled) {
          document.getElementById('tag-input-field')?.focus()
        }
      }}
    >
      {value.map((tag) => (
        <Badge key={tag} variant="default" className="gap-1.5 pl-2.5 pr-1.5">
          {tag}
          {!disabled && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                removeTag(tag)
              }}
              className="ml-0.5 rounded-sm opacity-60 hover:opacity-100"
              aria-label={`Remove ${tag}`}
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </Badge>
      ))}
      {!disabled && (
        <Input
          id="tag-input-field"
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (inputValue.trim()) addTag(inputValue)
          }}
          placeholder={value.length === 0 ? placeholder : ''}
          className="min-w-[120px] flex-1 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
        />
      )}
    </div>
  )
}
