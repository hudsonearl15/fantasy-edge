import type { Metadata } from "next";
import { getAllPlayers } from "@/lib/data";
import CompareClient from "./compare-client";

export const metadata: Metadata = {
  title: "Compare Players — 2026 Fantasy Baseball",
  description:
    "Compare fantasy baseball players side-by-side. See ZiPS 2026 projections, stats, and fantasy points for any two players.",
};

export default function ComparePage() {
  const all = getAllPlayers().map((p) => ({
    name: p.name,
    slug: p.slug,
    team: p.teamAbbr,
    pos: p.pos,
    type: p.type,
    fpts: p.fantasy.FPTS,
    adp: p.fantasy.ADP,
    stats: p.stats,
  }));

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-extrabold text-white mb-2">
        Compare Players
      </h1>
      <p className="text-zinc-400 text-sm mb-8">
        Search and compare any two players side-by-side.
      </p>
      <CompareClient players={all} />
    </div>
  );
}
