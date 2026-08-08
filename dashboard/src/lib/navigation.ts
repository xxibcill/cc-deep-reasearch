import {
  BarChart3,
  FileVideo,
  FlaskConical,
  GitCompare,
  Network,
  Radar,
  Settings,
  Trophy,
  type LucideIcon,
} from 'lucide-react';

export interface NavigationDestination {
  id: string;
  href: string;
  label: string;
  commandLabel: string;
  description: string;
  icon: LucideIcon;
  shortcutKey: string;
  showInPrimaryNav: boolean;
}

export const NAVIGATION_DESTINATIONS = [
  {
    id: 'research',
    href: '/',
    label: 'Research',
    commandLabel: 'Go to Research',
    description: 'View sessions and start new research',
    icon: FlaskConical,
    shortcutKey: 'h',
    showInPrimaryNav: true,
  },
  {
    id: 'analytics',
    href: '/analytics',
    label: 'Analytics',
    commandLabel: 'Go to Analytics',
    description: 'Review aggregate operational trends',
    icon: BarChart3,
    shortcutKey: 'a',
    showInPrimaryNav: true,
  },
  {
    id: 'benchmark',
    href: '/benchmark',
    label: 'Benchmark',
    commandLabel: 'Go to Benchmark',
    description: 'View evaluation results',
    icon: Trophy,
    shortcutKey: 'b',
    showInPrimaryNav: true,
  },
  {
    id: 'radar',
    href: '/radar',
    label: 'Radar',
    commandLabel: 'Go to Radar',
    description: 'Review monitored opportunities and sources',
    icon: Radar,
    shortcutKey: 'd',
    showInPrimaryNav: true,
  },
  {
    id: 'knowledge',
    href: '/knowledge',
    label: 'Knowledge',
    commandLabel: 'Go to Knowledge',
    description: 'Explore evidence and research relationships',
    icon: Network,
    shortcutKey: 'k',
    showInPrimaryNav: true,
  },
  {
    id: 'content-studio',
    href: '/content-gen',
    label: 'Content',
    commandLabel: 'Go to Content Studio',
    description: 'Manage production workflows',
    icon: FileVideo,
    shortcutKey: 'c',
    showInPrimaryNav: true,
  },
  {
    id: 'settings',
    href: '/settings',
    label: 'Settings',
    commandLabel: 'Go to Settings',
    description: 'Configure runtime controls',
    icon: Settings,
    shortcutKey: 's',
    showInPrimaryNav: true,
  },
  {
    id: 'compare',
    href: '/compare',
    label: 'Compare',
    commandLabel: 'Jump to Compare',
    description: 'Compare two sessions side by side',
    icon: GitCompare,
    shortcutKey: 'v',
    showInPrimaryNav: false,
  },
] as const satisfies readonly NavigationDestination[];

export const PRIMARY_NAVIGATION_DESTINATIONS = NAVIGATION_DESTINATIONS.filter(
  (destination) => destination.showInPrimaryNav
);

export const navigationShortcutLegend = NAVIGATION_DESTINATIONS.map((destination) =>
  destination.shortcutKey.toUpperCase()
).join('/');
