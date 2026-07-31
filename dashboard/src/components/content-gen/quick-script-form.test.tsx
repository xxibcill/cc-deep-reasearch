import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { QuickScriptForm } from '@/components/content-gen/quick-script-form'
import { runScripting } from '@/lib/content-gen-api'
import type { RunScriptingResponse } from '@/types/content-gen'

vi.mock('@/lib/content-gen-api', () => ({
  runScripting: vi.fn(),
}))

const runScriptingMock = vi.mocked(runScripting)

describe('QuickScriptForm Codex routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    runScriptingMock.mockResolvedValue({
      raw_idea: 'Explain model routing',
      script: 'Generated script',
      word_count: 2,
      context: { step_traces: [] },
      execution_mode: 'single_pass',
    } as unknown as RunScriptingResponse)
  })

  it('offers Codex and submits it as the LLM route', async () => {
    render(<QuickScriptForm />)

    expect(screen.getByRole('option', { name: 'Codex (ChatGPT)' })).toBeTruthy()

    fireEvent.change(screen.getByLabelText('LLM route'), {
      target: { value: 'codex' },
    })
    fireEvent.change(screen.getByLabelText(/Raw idea/), {
      target: { value: 'Explain model routing' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Generate Script' }))

    await waitFor(() => {
      expect(runScriptingMock).toHaveBeenCalledWith(
        expect.objectContaining({
          llm_route: 'codex',
        }),
      )
    })
    expect(await screen.findByText('Generated Script')).toBeTruthy()
  })
})
