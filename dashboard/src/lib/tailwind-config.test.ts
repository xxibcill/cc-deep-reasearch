import { createRequire } from 'node:module'
import path from 'node:path'

import postcss from 'postcss'
import tailwindcss, { type Config } from 'tailwindcss'
import { describe, expect, it } from 'vitest'

const require = createRequire(import.meta.url)
const loadConfig = require('tailwindcss/loadConfig') as (path: string) => Config

const semanticClasses = [
  'bg-card',
  'text-card-foreground',
  'bg-popover',
  'text-popover-foreground',
  'bg-primary',
  'text-primary-foreground',
  'bg-secondary',
  'text-secondary-foreground',
  'bg-muted',
  'text-muted-foreground',
  'bg-accent',
  'text-accent-foreground',
  'bg-destructive',
  'text-destructive-foreground',
  'bg-destructive-muted/20',
  'border-info/30',
  'bg-info-muted/15',
  'text-info',
] as const

const customOpacityClasses = [
  'border-primary/26',
  'bg-primary/12',
  'bg-surface/62',
  'text-foreground/86',
] as const

function selectorFor(className: string) {
  return `.${className.replace('/', '\\/')}`
}

async function compileUtilities(classes: readonly string[]) {
  const config = loadConfig(path.resolve(process.cwd(), 'tailwind.config.ts'))
  const result = await postcss([
    tailwindcss({
      ...config,
      content: [{ raw: `<div class="${classes.join(' ')}"></div>` }],
    }),
  ]).process('@tailwind utilities;', { from: undefined })

  return result.css
}

describe('Tailwind semantic token configuration', () => {
  it('compiles the semantic color roles used by shared UI components', async () => {
    const css = await compileUtilities(semanticClasses)

    for (const className of semanticClasses) {
      expect(css).toContain(selectorFor(className))
    }
  })

  it('compiles the custom opacity steps used by the dashboard', async () => {
    const css = await compileUtilities(customOpacityClasses)

    for (const className of customOpacityClasses) {
      expect(css).toContain(selectorFor(className))
    }
  })
})
