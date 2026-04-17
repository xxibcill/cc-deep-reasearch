'use client'

import { ScriptViewer } from '@/components/content-gen/script-viewer'
import { countWords } from '@/lib/text-utils'

interface BeatSection {
  beat: string
  content: string
}

interface ScriptBeatViewProps {
  script: string
  beatList: string[]
}

function splitScriptByBeats(script: string, beatList: string[]): BeatSection[] {
  if (!script || !beatList || beatList.length === 0) {
    return [{ beat: 'Full Script', content: script || '' }]
  }

  // Escape special regex chars in beat names
  const escaped = beatList.map((b) => b.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`##\\s*(${escaped.join('|')})\\s*$`, 'gim')

  // Find all header positions first
  const headers: { beat: string; start: number; end: number }[] = []
  let match
  while ((match = pattern.exec(script)) !== null) {
    headers.push({
      beat: match[1],
      start: match.index,
      end: match.index + match[0].length,
    })
  }

  // If no beats were found, return full script as single section
  if (headers.length === 0) {
    return [{ beat: 'Full Script', content: script }]
  }

  // Extract content between headers
  const sections: BeatSection[] = []
  for (let i = 0; i < headers.length; i++) {
    const header = headers[i]
    const nextHeader = headers[i + 1]

    // Find content start: skip past the newline after this header
    let contentStart = header.end
    while (contentStart < script.length && (script[contentStart] === '\n' || script[contentStart] === '\r')) {
      contentStart++
    }

    // Find content end: before the next header (skipping blank lines)
    let contentEnd = nextHeader ? nextHeader.start : script.length
    while (contentEnd > contentStart && script[contentEnd - 1] === '\n') {
      contentEnd--
    }

    const content = script.slice(contentStart, contentEnd).trim()
    sections.push({ beat: header.beat, content })
  }

  return sections
}

export function ScriptBeatView({ script, beatList }: ScriptBeatViewProps) {
  const sections = splitScriptByBeats(script, beatList)

  const totalWordCount = countWords(script)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold font-display">Generated Script</h2>
        <span className="text-sm font-mono text-muted-foreground tabular-nums">
          {totalWordCount.toLocaleString()} words total
        </span>
      </div>

      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.beat} className="space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-foreground">{section.beat}</h3>
              <span className="text-xs font-mono text-muted-foreground tabular-nums">
                {countWords(section.content)}w
              </span>
            </div>
            <ScriptViewer content={section.content} label="" showWordCount={false} />
          </div>
        ))}
      </div>
    </div>
  )
}
