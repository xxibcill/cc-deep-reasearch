import type { Page } from '@playwright/test';
import path from 'node:path';

/**
 * Mock session type for test fixtures.
 * This is a stub implementation for testing purposes.
 */
export interface MockSession {
  session_id: string;
  label?: string;
  created_at: string;
  total_time_ms?: number;
  total_sources?: number;
  status: string;
  active?: boolean;
  event_count?: number;
  last_event_at?: string;
  query?: string;
  depth?: string;
  completed_at?: string;
  has_session_payload?: boolean;
  has_report?: boolean;
  archived?: boolean;
}

interface MockDashboardOptions {
  sessions?: MockSession[];
}

/**
 * Get the screenshot output path for a given filename.
 * This is a stub implementation.
 */
export function screenshotPath(filename: string): string {
  return path.join('/tmp/dashboard-screenshots', filename);
}

/**
 * Mock the dashboard API endpoints for testing.
 * This is a stub implementation.
 */
export async function mockDashboardApis(
  _page: Page,
  _options: MockDashboardOptions = {}
): Promise<void> {
  // Stub implementation - no-op for now
  // Full implementation would mock API responses
}
