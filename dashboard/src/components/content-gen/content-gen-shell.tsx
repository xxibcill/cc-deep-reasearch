'use client'

export function ContentGenShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">{children}</div>
  )
}
