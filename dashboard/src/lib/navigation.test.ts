import { describe, expect, it } from 'vitest';

import {
  NAVIGATION_DESTINATIONS,
  PRIMARY_NAVIGATION_DESTINATIONS,
  navigationShortcutLegend,
} from '@/lib/navigation';

describe('navigation registry', () => {
  it('keeps route and shortcut metadata unique', () => {
    const hrefs = NAVIGATION_DESTINATIONS.map((destination) => destination.href);
    const shortcutKeys = NAVIGATION_DESTINATIONS.map(
      (destination) => destination.shortcutKey
    );

    expect(new Set(hrefs).size).toBe(hrefs.length);
    expect(new Set(shortcutKeys).size).toBe(shortcutKeys.length);
  });

  it('derives primary navigation and the shortcut legend from one registry', () => {
    expect(PRIMARY_NAVIGATION_DESTINATIONS.map((destination) => destination.id)).toEqual([
      'research',
      'analytics',
      'benchmark',
      'radar',
      'knowledge',
      'content-studio',
      'settings',
    ]);
    expect(navigationShortcutLegend).toBe('H/A/B/D/K/C/S/V');
  });
});
