import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Video-to-SOP Knowledge Assistant",
  description: "Turn manufacturing training videos into reviewable Standard Operating Procedures.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-graphite-950 text-graphite-100 antialiased">
        <header className="border-b border-graphite-700/80 bg-graphite-900/60 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="stamp text-xs text-amber-400">VSA</span>
              <span className="font-display text-lg font-bold tracking-tight">
                Video&nbsp;→&nbsp;SOP
              </span>
            </Link>
            <nav className="stamp flex items-center gap-6 text-xs text-graphite-400">
              <Link href="/upload" className="transition hover:text-amber-400">
                New Job
              </Link>
              <Link href="/sops" className="transition hover:text-blue-400">
                Monitor SOPs
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}