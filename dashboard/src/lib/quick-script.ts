export interface QuickScriptFieldDef {
  key: QuickScriptFieldKey
  label: string
  placeholder: string
  required?: boolean
  rows?: number
}

export type QuickScriptFieldKey =
  | 'raw_idea'
  | 'viewer_outcome'
  | 'target_audience'
  | 'platform'
  | 'desired_length'
  | 'tone'
  | 'angle'
  | 'must_include'
  | 'must_avoid'
  | 'cta_goal'
  | 'source_material'
  | 'constraints'

export const QUICK_SCRIPT_FIELDS: QuickScriptFieldDef[] = [
  { key: 'raw_idea', label: 'Raw idea', placeholder: 'What the video is about in plain words', required: true, rows: 2 },
  { key: 'viewer_outcome', label: 'What this video should help the viewer do', placeholder: 'Specific outcome' },
  { key: 'target_audience', label: 'Target audience', placeholder: 'Who this is for' },
  { key: 'platform', label: 'Platform', placeholder: 'TikTok / Reels / Shorts / X / LinkedIn / Other' },
  { key: 'desired_length', label: 'Desired length', placeholder: '20 sec / 30 sec / 45 sec / other' },
  { key: 'tone', label: 'Tone', placeholder: 'Sharp / calm / premium / funny / intense / direct / other' },
  { key: 'angle', label: 'What kind of angle you want most', placeholder: 'Contrarian / mistake / framework / insight / story / myth vs truth / no preference' },
  { key: 'must_include', label: 'Must include', placeholder: 'Any facts, claims, examples, phrases, CTA, product, offer, story, proof', rows: 2 },
  { key: 'must_avoid', label: 'Must avoid', placeholder: 'Words, tone, claims, topics, style you do not want' },
  { key: 'cta_goal', label: 'CTA goal', placeholder: 'Follow / comment / DM / click / save / share / buy / no CTA' },
  { key: 'source_material', label: 'Optional source material', placeholder: 'Paste notes, transcript, bullets, proof points, data, story details', rows: 3 },
  { key: 'constraints', label: 'Optional constraints', placeholder: 'Brand rules, compliance limits, banned claims, pronunciation notes, etc.', rows: 2 },
]

export type QuickScriptFields = Record<QuickScriptFieldKey, string>

const FIELD_KEY_BY_LABEL = Object.fromEntries(
  QUICK_SCRIPT_FIELDS.map((field) => [field.label, field.key]),
) as Record<string, QuickScriptFieldKey>

export function createEmptyQuickScriptFields(): QuickScriptFields {
  return Object.fromEntries(
    QUICK_SCRIPT_FIELDS.map((field) => [field.key, '']),
  ) as QuickScriptFields
}

export function mergeQuickScriptFields(
  values?: Partial<QuickScriptFields> | null,
): QuickScriptFields {
  return {
    ...createEmptyQuickScriptFields(),
    ...(values ?? {}),
  }
}

export function buildQuickScriptPrompt(fields: QuickScriptFields): string {
  const lines: string[] = []

  for (const field of QUICK_SCRIPT_FIELDS) {
    const value = fields[field.key].trim()
    if (value) {
      lines.push(`${field.label}:\n${value}`)
    }
  }

  return lines.join('\n\n')
}

export function buildQuickScriptMarkdown(fields: QuickScriptFields): string {
  const sections = QUICK_SCRIPT_FIELDS.flatMap((field) => {
    const value = fields[field.key].trim()
    if (!value) {
      return []
    }

    return [`## ${field.label}`, '', value, '']
  })

  return ['# Quick Script Input', '', ...sections].join('\n').trim()
}

export function parseQuickScriptPrompt(prompt: string): QuickScriptFields {
  const parsed = createEmptyQuickScriptFields()
  const lines = prompt.split('\n')

  let currentKey: QuickScriptFieldKey | null = null
  let matchedKnownLabel = false

  for (const line of lines) {
    const maybeLabel = line.endsWith(':') ? line.slice(0, -1) : null
    const nextKey = maybeLabel ? FIELD_KEY_BY_LABEL[maybeLabel] : undefined

    if (nextKey) {
      currentKey = nextKey
      matchedKnownLabel = true
      continue
    }

    if (!currentKey) {
      continue
    }

    parsed[currentKey] = parsed[currentKey]
      ? `${parsed[currentKey]}\n${line}`
      : line
  }

  for (const key of Object.keys(parsed) as QuickScriptFieldKey[]) {
    parsed[key] = parsed[key].trim()
  }

  if (!matchedKnownLabel && prompt.trim()) {
    parsed.raw_idea = prompt.trim()
  }

  return parsed
}

export function parseQuickScriptMarkdown(markdown: string): QuickScriptFields {
  const parsed = createEmptyQuickScriptFields()
  const lines = markdown.split('\n')

  let currentKey: QuickScriptFieldKey | null = null
  let matchedKnownSection = false

  for (const line of lines) {
    const trimmed = line.trim()
    const headingLabel = trimmed.replace(/^#{1,6}\s+/, '').replace(/:$/, '')
    const nextKey = FIELD_KEY_BY_LABEL[headingLabel]

    if (nextKey) {
      currentKey = nextKey
      matchedKnownSection = true
      continue
    }

    if (!currentKey) {
      continue
    }

    parsed[currentKey] = parsed[currentKey]
      ? `${parsed[currentKey]}\n${line}`
      : line
  }

  for (const key of Object.keys(parsed) as QuickScriptFieldKey[]) {
    parsed[key] = parsed[key].trim()
  }

  if (!matchedKnownSection) {
    return parseQuickScriptPrompt(markdown)
  }

  return parsed
}
