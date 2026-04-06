'use client'

import Link from 'next/link'
import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { AlertCircle, ArrowLeft } from 'lucide-react'

import { CompareView } from '@/components/compare-view'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function ComparePageContent() {
  const searchParams = useSearchParams()
  const sessionA = searchParams.get('a')
  const sessionB = searchParams.get('b')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionA || !sessionB) {
      setError('Missing session IDs. Both ?a= and ?b= parameters are required.')
      return
    }
    if (sessionA === sessionB) {
      setError('Pick two different sessions so the compare summary has something to measure.')
      return
    }
    setError(null)
  }, [sessionA, sessionB])

  if (error) {
    return (
      <div className="mx-auto flex min-h-96 max-w-content items-center justify-center px-page-x py-page-y">
        <Card className="max-w-xl">
          <CardHeader className="border-b border-border/70">
            <CardTitle className="flex items-center gap-2 text-[1.4rem]">
              <AlertCircle className="h-5 w-5 text-warning" />
              Invalid comparison
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-6">
            <p className="text-sm leading-6 text-muted-foreground">{error}</p>
            <p className="text-sm leading-6 text-muted-foreground">
              Return to the research archive, enable compare mode, and pick one baseline session
              plus one comparison session.
            </p>
            <Link href="/" className="inline-flex">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Sessions
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <CompareView sessionIdA={sessionA!} sessionIdB={sessionB!} />
    </div>
  )
}

export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-96 items-center justify-center">
          <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-primary" />
        </div>
      }
    >
      <ComparePageContent />
    </Suspense>
  )
}
