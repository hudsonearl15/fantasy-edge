import type { Metadata } from "next";
import Link from "next/link";
import { getAllPlayers, type Player } from "@/lib/data";

export const metadata: Metadata = {
  title: "Sleepers & Busts — 2026 Fantasy Baseball",
  description:
    "Find undervalued sleepers and overvalued busts for your 2026 fantasy baseball draft. Compare ADP to ZiPS projected value.",
};

function ValueRow({
  player,
  gap,
  isSleeper,
}: {
  player: Player;
  gap: number;
  isSleeper: boolean;
}) {
  return (
    <Link
      href={`/player/${player.slug}`}
      className="grid grid-cols-[1fr_3rem_3.5rem_4.5rem_4rem_4.5rem] items-center gap-2 px-4 py-2.5 hover:bg-zinc-800/50 transition border-b border-zinc-800/50 last:border-0"
    >
      <div className="min-w-0">
        <span className="text-sm font-medium text-white truncate block">
          {player.name}
        </span>
        <span className="text-xs text-zinc-500">
          {player.teamAbbr} &middot; {player.pos}
        </span>
      </div>
      <span className="text-sm text-zinc-400 text-right">{player.pos}</span>
      <span className="text-sm text-emerald-400 font-semibold text-right">
        {player.fantasy.FPTS.toFixed(0)}
      </span>
      <span className="text-sm text-zinc-400 text-right">
        #{player.rank}
      </span>
      <span className="text-sm text-zinc-400 text-right">
        {player.fantasy.ADP.toFixed(1)}
      </span>
      <span
        className={`text-sm font-bold text-right ${isSleeper ? "text-emerald-400" : "text-red-400"}`}
      >
        {isSleeper ? "+" : ""}
        {gap.toFixed(0)}
      </span>
    </Link>
  );
}

export default function SleepersPage() {
  const all = getAllPlayers();

  // Only consider players with real ADP data (exclude placeholder 999+ values)
  const withAdp = all.filter((p) => p.fantasy.ADP > 0 && p.fantasy.ADP < 500);

  // Calculate value gap: ADP - rank (positive = sleeper, negative = bust)
  const valued = withAdp.map((p) => {
    const overallRank = all.findIndex((a) => a.slug === p.slug) + 1;
    return { player: p, gap: p.fantasy.ADP - overallRank };
  });

  const sleepers = [...valued].sort((a, b) => b.gap - a.gap).slice(0, 50);
  const busts = [...valued].sort((a, b) => a.gap - b.gap).slice(0, 50);

  const headers = (
    <div className="grid grid-cols-[1fr_3rem_3.5rem_4.5rem_4rem_4.5rem] gap-2 px-4 py-2 bg-zinc-900 border-b border-zinc-800 text-xs text-zinc-500 font-medium">
      <span>Player</span>
      <span className="text-right">Pos</span>
      <span className="text-right">FPTS</span>
      <span className="text-right">Value #</span>
      <span className="text-right">ADP</span>
      <span className="text-right">Gap</span>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-extrabold text-white mb-2">
        Sleepers & Busts
      </h1>
      <p className="text-zinc-400 text-sm mb-8">
        Value Gap = ADP minus projected rank. Positive means the player is
        drafted later than their projected value (sleeper). Negative means
        they&apos;re drafted earlier (bust).
      </p>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Sleepers */}
        <div>
          <h2 className="text-lg font-bold text-emerald-400 mb-3">
            Top Sleepers
          </h2>
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
            {headers}
            {sleepers.map(({ player, gap }) => (
              <ValueRow
                key={player.slug}
                player={player}
                gap={gap}
                isSleeper
              />
            ))}
          </div>
        </div>

        {/* Busts */}
        <div>
          <h2 className="text-lg font-bold text-red-400 mb-3">
            Potential Busts
          </h2>
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
            {headers}
            {busts.map(({ player, gap }) => (
              <ValueRow
                key={player.slug}
                player={player}
                gap={gap}
                isSleeper={false}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
