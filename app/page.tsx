import Link from "next/link";
import { getAllPlayers, POSITIONS, type Player } from "@/lib/data";

function StatBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-zinc-900 rounded-lg px-4 py-3 text-center">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-zinc-500 mt-0.5">{label}</div>
    </div>
  );
}

function PlayerRow({ player, index }: { player: Player; index: number }) {
  return (
    <Link
      href={`/player/${player.slug}`}
      className="grid grid-cols-[2.5rem_1fr_3.5rem_4.5rem_3.5rem] sm:grid-cols-[2.5rem_1fr_3.5rem_3.5rem_5rem_5rem_4rem] items-center gap-2 px-4 py-2.5 hover:bg-zinc-800/50 transition group border-b border-zinc-800/50 last:border-0"
    >
      <span className="text-xs text-zinc-500 text-right">{index + 1}</span>
      <div className="min-w-0">
        <span className="text-sm font-medium text-white group-hover:text-blue-400 transition truncate block">
          {player.name}
        </span>
        <span className="text-xs text-zinc-500 sm:hidden">
          {player.teamAbbr} &middot; {player.pos}
        </span>
      </div>
      <span className="text-xs text-zinc-400 text-center hidden sm:block">
        {player.pos}
      </span>
      <span className="text-xs text-zinc-500 text-center hidden sm:block">
        {player.teamAbbr}
      </span>
      <span className="text-sm font-semibold text-emerald-400 text-right">
        {player.fantasy.FPTS.toFixed(0)}
      </span>
      <span className="text-sm text-zinc-400 text-right hidden sm:block">
        {player.fantasy.ADP > 0 ? player.fantasy.ADP.toFixed(1) : "—"}
      </span>
      <span className="text-sm text-zinc-500 text-right">
        {player.stats.WAR?.toFixed(1) ?? "—"}
      </span>
    </Link>
  );
}

export default function HomePage() {
  const all = getAllPlayers();
  const top200 = all.slice(0, 200);
  const hitterCount = all.filter((p) => p.type === "hitter").length;
  const pitcherCount = all.filter((p) => p.type === "pitcher").length;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Hero */}
      <section className="mb-10">
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
          2026 Fantasy Baseball Rankings
        </h1>
        <p className="mt-2 text-zinc-400 max-w-2xl">
          Free player rankings and projections powered by ZiPS 2026. Search{" "}
          {hitterCount.toLocaleString()} hitters and{" "}
          {pitcherCount.toLocaleString()} pitchers. Compare players, find
          sleepers, and win your draft.
        </p>
        <div className="flex flex-wrap gap-3 mt-6">
          <StatBadge
            label="Total Players"
            value={all.length.toLocaleString()}
          />
          <StatBadge label="Hitters" value={hitterCount.toLocaleString()} />
          <StatBadge label="Pitchers" value={pitcherCount.toLocaleString()} />
          <StatBadge label="Projection Source" value="ZiPS" />
        </div>
      </section>

      {/* Position quick links */}
      <section className="mb-8">
        <div className="flex flex-wrap gap-2">
          {POSITIONS.map((pos) => (
            <Link
              key={pos}
              href={`/rankings/${pos.toLowerCase()}`}
              className="px-3 py-1.5 text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-full transition"
            >
              {pos}
            </Link>
          ))}
          <Link
            href="/rankings/sp"
            className="px-3 py-1.5 text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-full transition"
          >
            SP
          </Link>
          <Link
            href="/rankings/rp"
            className="px-3 py-1.5 text-xs font-medium bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-full transition"
          >
            RP
          </Link>
        </div>
      </section>

      {/* Top 200 Overall */}
      <section>
        <h2 className="text-xl font-bold text-white mb-4">
          Top 200 Overall Rankings
        </h2>
        <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
          <div className="grid grid-cols-[2.5rem_1fr_3.5rem_4.5rem_3.5rem] sm:grid-cols-[2.5rem_1fr_3.5rem_3.5rem_5rem_5rem_4rem] gap-2 px-4 py-2 bg-zinc-900 border-b border-zinc-800 text-xs text-zinc-500 font-medium">
            <span className="text-right">#</span>
            <span>Player</span>
            <span className="text-center hidden sm:block">Pos</span>
            <span className="text-center hidden sm:block">Team</span>
            <span className="text-right">FPTS</span>
            <span className="text-right hidden sm:block">ADP</span>
            <span className="text-right">WAR</span>
          </div>
          {top200.map((player, i) => (
            <PlayerRow key={player.slug} player={player} index={i} />
          ))}
        </div>
      </section>
    </div>
  );
}
