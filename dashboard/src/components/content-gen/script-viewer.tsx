'use client'

import { useState } from 'react'
import { Copy, FileText, Check } from 'lucide-react'

interface ScriptViewerProps {
  content: string
  label?: string
  showWordCount?: boolean
}

export function ScriptViewer({
  content,
  label = 'Script',
  showWordCount = true,
}: ScriptViewerProps) {
  const [copied, setCopied] = useState(false)
  const wordCount = content ? content.split(/\s+/).filter(Boolean).length : 0

  const handleCopy = async () => {
    if (!content) return
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium font-display">{label}</span>
          {showWordCount && (
            <span className="text-xs text-muted-foreground font-mono tabular-nums">
              {wordCount}w
            </span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-surface-raised"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-success" />
              <span className="text-success">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              Copy
            </>
          )}
        </button>
      </div>
      <div className="bg-background border border-border p-4 rounded-sm max-h-[500px] overflow-y-auto">
        <pre className="whitespace-pre-wrap text-sm leading-[1.7] font-mono text-foreground/85">
          {content || <span className="text-muted-foreground italic">No content</span>}
        </pre>
      </div>
    </div>
  )
}
