import { ConfigEditor } from '@/components/config-editor';
import { SearchCachePanel } from '@/components/search-cache-panel';

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

