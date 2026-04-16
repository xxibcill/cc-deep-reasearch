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

  const sections: BeatSection[] = []
  let lastIndex = 0
  let match
  const foundBeats: string[] = []

  while ((match = pattern.exec(script)) !== null) {
    if (foundBeats.length > 0) {
      // Update content of previous section
      const prevBeat = foundBeats[foundBeats.length - 1]
      const prevSection = sections.find((s) => s.beat === prevBeat)
      if (prevSection) {
        prevSection.content = script.slice(lastIndex, match.index).trim()
      }
    }
    foundBeats.push(match[1])
    sections.push({ beat: match[1], content: '' })
    lastIndex = pattern.lastIndex
  }

  // Handle last section content
  if (sections.length > 0) {
    const lastSection = sections[sections.length - 1]
    lastSection.content = script.slice(lastIndex).trim()
  }

  // If no beats were found, return full script as single section
  if (sections.length === 0) {
    return [{ beat: 'Full Script', content: script }]
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
