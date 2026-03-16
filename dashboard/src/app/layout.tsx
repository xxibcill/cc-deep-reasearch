import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'CC Deep Research Monitoring',
  description: 'Real-time monitoring dashboard for CC Deep Research',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
