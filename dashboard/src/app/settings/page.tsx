import { ConfigEditor } from '@/components/config-editor';
import { SearchCachePanel } from '@/components/search-cache-panel';

export default function SettingsPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(35,96,196,0.12),_transparent_30%),linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(241,245,249,0.92))] px-4 py-10">
      <div className="mx-auto max-w-7xl space-y-5">
        <ConfigEditor />
        <SearchCachePanel />
      </div>
    </main>
  );
}

