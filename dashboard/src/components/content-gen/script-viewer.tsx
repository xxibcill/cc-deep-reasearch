'use client'

import { Copy, FileText } from 'lucide-react'

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
  const wordCount = content ? content.split(/\s+/).filter(Boolean).length : 0

  const handleCopy = async () => {
    if (!content) return
    await navigator.clipboard.writeText(content)
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium">
          <FileText className="h-4 w-4" />
          {label}
          {showWordCount && (
            <span className="text-muted-foreground font-normal">
              ({wordCount} words)
            </span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="Copy to clipboard"
        >
          <Copy className="h-3.5 w-3.5" />
          Copy
        </button>
      </div>
      <pre className="whitespace-pre-wrap text-sm leading-relaxed bg-muted/30 p-4 rounded-md border max-h-[500px] overflow-y-auto">
        {content || <span className="text-muted-foreground italic">No content</span>}
      </pre>
    </div>
  )
}
