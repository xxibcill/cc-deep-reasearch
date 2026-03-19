'use client';

import { useSearchParams } from 'next/navigation';
import { useEffect, useState, Suspense } from 'react';
import { AlertCircle } from 'lucide-react';
import { CompareView } from '@/components/compare-view';

function ComparePageContent() {
  const searchParams = useSearchParams();
  const sessionA = searchParams.get('a');
  const sessionB = searchParams.get('b');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionA || !sessionB) {
      setError('Missing session IDs. Both ?a= and ?b= parameters are required.');
    }
  }, [sessionA, sessionB]);

  if (error) {
    return (
      <div className="flex min-h-96 items-center justify-center">
        <div className="max-w-md rounded-lg border border-amber-200 bg-amber-50 p-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
            <div>
              <p className="font-medium text-amber-800">Invalid comparison</p>
              <p className="text-sm text-amber-700">{error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return <CompareView sessionIdA={sessionA!} sessionIdB={sessionB!} />;
}

export default function ComparePage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-96 items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
      </div>
    }>
      <ComparePageContent />
    </Suspense>
  );
}
