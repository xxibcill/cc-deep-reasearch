import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SessionReport } from '@/components/session-report';
import { getSessionReport } from '@/lib/api';

vi.mock('@/components/research-content-actions', () => ({
  ResearchContentActions: () => null,
}));

vi.mock('@/lib/api', () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
  getSessionReport: vi.fn(),
}));

const getSessionReportMock = vi.mocked(getSessionReport);

describe('SessionReport degraded results', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSessionReportMock.mockResolvedValue({
      session_id: 'partial-session',
      format: 'markdown',
      media_type: 'text/markdown',
      content: '# Partial findings\n\nRecovered evidence.',
    });
  });

  it('loads an available report after the run ends in failure', async () => {
    render(
      <SessionReport
        sessionId="partial-session"
        runStatus="failed"
        sessionSummary={null}
        hasReport
      />
    );

    await waitFor(() => {
      expect(getSessionReportMock).toHaveBeenCalledWith('partial-session', 'markdown');
    });
    expect(await screen.findByText('Partial findings')).toBeTruthy();
    expect(screen.getByText('Partial report available')).toBeTruthy();
  });

  it('keeps the failure state when no report artifact exists', () => {
    render(
      <SessionReport
        sessionId="failed-session"
        runStatus="failed"
        sessionSummary={null}
        hasReport={false}
      />
    );

    expect(screen.getByText('Research run failed')).toBeTruthy();
    expect(getSessionReportMock).not.toHaveBeenCalled();
  });
});

describe('SessionReport document rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSessionReportMock.mockImplementation(async (_sessionId, format) => {
      if (format === 'html') {
        return {
          session_id: 'readable-session',
          format: 'html',
          media_type: 'text/html',
          content:
            '<!doctype html><html><head><style>body{color:#333}</style></head><body><h1>Standalone HTML heading</h1></body></html>',
        };
      }

      return {
        session_id: 'readable-session',
        format: 'markdown',
        media_type: 'text/markdown',
        content:
          '# Readable research\n\nA long-form finding with [supporting evidence](https://example.com).\n\n| Genre | Rank |\n| --- | --- |\n| Strategy | 1 |',
      };
    });
  });

  it('renders Markdown as a scoped reading document with accessible overflow', async () => {
    render(
      <SessionReport
        sessionId="readable-session"
        runStatus="completed"
        sessionSummary={null}
        hasReport
      />
    );

    const document = await screen.findByTestId('research-markdown-document');
    expect(document.className).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Readable research', level: 1 })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'supporting evidence' }).getAttribute('target')).toBe(
      '_blank'
    );
    expect(
      screen.getByRole('region', { name: 'Scrollable report table' }).getAttribute('tabindex')
    ).toBe('0');
  });

  it('isolates a full HTML document in a script-disabled preview', async () => {
    render(
      <SessionReport
        sessionId="readable-session"
        runStatus="completed"
        sessionSummary={null}
        hasReport
      />
    );

    await screen.findByText('Readable research');
    fireEvent.click(screen.getByRole('button', { name: 'HTML' }));

    const frame = await screen.findByTitle('Standalone HTML report preview');
    expect(frame.tagName).toBe('IFRAME');
    expect(frame.getAttribute('sandbox')).toBe('');
    expect(frame.getAttribute('referrerpolicy')).toBe('no-referrer');
    expect(frame.getAttribute('srcdoc')).toContain('Standalone HTML heading');
    expect(screen.queryByText('Standalone HTML heading')).toBeNull();
  });
});
