import { Suspense } from 'react'
import { ContentGenShell } from '@/components/content-gen/content-gen-shell'

export default function ContentGenLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <Suspense>
      <ContentGenShell>{children}</ContentGenShell>
    </Suspense>
  )
}
