import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "FantasyEdge — 2026 Fantasy Baseball Rankings & Projections",
    template: "%s | FantasyEdge",
  },
  description:
    "Free fantasy baseball rankings, player projections, and draft tools powered by ZiPS 2026 projections. Compare players, find sleepers, and dominate your draft.",
  metadataBase: new URL("https://fantasybaseballedge.com"),
  openGraph: {
    siteName: "FantasyEdge",
    type: "website",
  },
  robots: { index: true, follow: true },
  verification: {
    google: "g4jPl0zXdn7-nkoBN4U1cVYWs0Si6K79tyEsrzRzXhA",
  },
};

function Nav() {
  return (
    <nav className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
        <Link href="/" className="text-lg font-bold text-white tracking-tight">
          Fantasy<span className="text-blue-400">Edge</span>
        </Link>
        <div className="hidden sm:flex items-center gap-1 text-sm">
          <Link
            href="/rankings"
            className="px-3 py-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          >
            Rankings
          </Link>
          <Link
            href="/rankings/sp"
            className="px-3 py-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          >
            Pitchers
          </Link>
          <Link
            href="/compare"
            className="px-3 py-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          >
            Compare
          </Link>
          <Link
            href="/sleepers"
            className="px-3 py-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          >
            Sleepers
          </Link>
        </div>
      </div>
    </nav>
  );
}

function Footer() {
  return (
    <footer className="border-t border-zinc-800 py-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 text-center text-xs text-zinc-500">
        <p>
          FantasyEdge &copy; {new Date().getFullYear()} &mdash; Projections
          powered by ZiPS 2026. Not affiliated with Fangraphs or MLB.
        </p>
        <p className="mt-1">
          Data updated for the 2026 season. Rankings are projections, not
          guarantees.
        </p>
      </div>
    </footer>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.className} dark`}>
      <body className="bg-zinc-950 text-zinc-100 min-h-screen flex flex-col">
        <Nav />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
