import dynamic from 'next/dynamic';

const ConfigEditor = dynamic(
  () => import('@/components/config-editor').then((mod) => mod.ConfigEditor),
  {
    loading: () => <div className="text-sm text-muted-foreground">Loading configuration…</div>,
  },
);

const SearchCachePanel = dynamic(
  () => import('@/components/search-cache-panel').then((mod) => mod.SearchCachePanel),
  {
    loading: () => <div className="text-sm text-muted-foreground">Loading cache controls…</div>,
  },
);

export default function SettingsPage() {
  return (
    <main className="px-page-x py-10">
      <div className="mx-auto max-w-content space-y-5">
        <ConfigEditor />
        <SearchCachePanel />
      </div>
    </main>
  );
}
