import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import {
  getHitters,
  getPitchers,
  POSITIONS,
  PITCHER_POSITIONS,
  type Player,
} from "@/lib/data";

const ALL_POSITIONS = [...POSITIONS, ...PITCHER_POSITIONS];

export async function generateStaticParams() {
  return ALL_POSITIONS.map((pos) => ({ position: pos.toLowerCase() }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ position: string }>;
}): Promise<Metadata> {
  const { position } = await params;
  const pos = position.toUpperCase();
  const posName = pos === "SP" ? "Starting Pitcher" : pos === "RP" ? "Relief Pitcher" : pos;

  return {
    title: `${posName} Rankings — 2026 Fantasy Baseball`,
    description: `Top ${posName} rankings for 2026 fantasy baseball. ZiPS projections with stats, ADP, and WAR for every ${posName}.`,
  };
}

function HitterRow({ player, index }: { player: Player; index: number }) {
  const s = player.stats;
  return (
    <Link
      href={`/player/${player.slug}`}
      className="grid grid-cols-[2rem_1fr_3.5rem_3rem_3rem_3rem_3rem_3rem_3.5rem_3.5rem_3.5rem_3.5rem] items-center gap-1 px-3 py-2 hover:bg-zinc-800/50 transition text-sm border-b border-zinc-800/50 last:border-0"
    >
      <span className="text-xs text-zinc-500 text-right">{index + 1}</span>
      <div className="min-w-0">
        <span className="font-medium text-white truncate block">
          {player.name}
        </span>
        <span className="text-xs text-zinc-500">{player.teamAbbr}</span>
      </div>
      <span className="text-emerald-400 font-semibold text-right">
        {player.fantasy.FPTS.toFixed(0)}
      </span>
      <span className="text-zinc-400 text-right">{s.HR}</span>
      <span className="text-zinc-400 text-right">{s.R}</span>
      <span className="text-zinc-400 text-right">{s.RBI}</span>
      <span className="text-zinc-400 text-right">{s.SB}</span>
      <span className="text-zinc-400 text-right">{s.H}</span>
      <span className="text-zinc-400 text-right">
        {s.AVG?.toFixed(3) ?? "—"}
      </span>
      <span className="text-zinc-400 text-right">
        {s.OPS?.toFixed(3) ?? "—"}
      </span>
      <span className="text-zinc-500 text-right">
        {player.fantasy.ADP > 0 ? player.fantasy.ADP.toFixed(1) : "—"}
      </span>
      <span className="text-zinc-500 text-right">
        {s.WAR?.toFixed(1) ?? "—"}
      </span>
    </Link>
  );
}

function PitcherRow({ player, index }: { player: Player; index: number }) {
  const s = player.stats;
  return (
    <Link
      href={`/player/${player.slug}`}
      className="grid grid-cols-[2rem_1fr_3.5rem_3rem_3rem_3.5rem_3.5rem_3.5rem_3.5rem_3rem_3.5rem_3.5rem] items-center gap-1 px-3 py-2 hover:bg-zinc-800/50 transition text-sm border-b border-zinc-800/50 last:border-0"
    >
      <span className="text-xs text-zinc-500 text-right">{index + 1}</span>
      <div className="min-w-0">
        <span className="font-medium text-white truncate block">
          {player.name}
        </span>
        <span className="text-xs text-zinc-500">{player.teamAbbr}</span>
      </div>
      <span className="text-emerald-400 font-semibold text-right">
        {player.fantasy.FPTS.toFixed(0)}
      </span>
      <span className="text-zinc-400 text-right">{s.W}</span>
      <span className="text-zinc-400 text-right">{s.L}</span>
      <span className="text-zinc-400 text-right">{s.IP}</span>
      <span className="text-zinc-400 text-right">
        {s.ERA?.toFixed(2) ?? "—"}
      </span>
      <span className="text-zinc-400 text-right">
        {s.WHIP?.toFixed(3) ?? "—"}
      </span>
      <span className="text-zinc-400 text-right">
        {s["K/9"]?.toFixed(1) ?? "—"}
      </span>
      <span className="text-zinc-400 text-right">{s.SO}</span>
      <span className="text-zinc-500 text-right">
        {player.fantasy.ADP > 0 ? player.fantasy.ADP.toFixed(1) : "—"}
      </span>
      <span className="text-zinc-500 text-right">
        {s.WAR?.toFixed(1) ?? "—"}
      </span>
    </Link>
  );
}

export default async function PositionRankings({
  params,
}: {
  params: Promise<{ position: string }>;
}) {
  const { position } = await params;
  const pos = position.toUpperCase();

  if (!ALL_POSITIONS.includes(pos as typeof ALL_POSITIONS[number])) {
    notFound();
  }

  const isPitcher = pos === "SP" || pos === "RP";
  let players: Player[];

  if (isPitcher) {
    players = getPitchers()
      .filter((p) => p.pos === pos)
      .sort((a, b) => b.fantasy.FPTS - a.fantasy.FPTS);
  } else {
    players = getHitters()
      .filter((p) => p.pos === pos)
      .sort((a, b) => b.fantasy.FPTS - a.fantasy.FPTS);
  }

  const top = players.filter((p) => p.fantasy.FPTS > 50).slice(0, 200);
  const posName = pos === "SP" ? "Starting Pitcher" : pos === "RP" ? "Relief Pitcher" : pos;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="text-sm text-zinc-500 mb-4">
        <Link href="/" className="hover:text-zinc-300 transition">
          Home
        </Link>
        <span className="mx-2">/</span>
        <span className="text-zinc-300">{posName} Rankings</span>
      </div>

      <h1 className="text-2xl font-extrabold text-white mb-2">
        {posName} Rankings — 2026
      </h1>
      <p className="text-zinc-400 text-sm mb-6">
        Top {top.length} {posName}s ranked by projected fantasy points (ZiPS
        2026).
      </p>

      {/* Position tabs */}
      <div className="flex flex-wrap gap-2 mb-6">
        {ALL_POSITIONS.map((p) => (
          <Link
            key={p}
            href={`/rankings/${p.toLowerCase()}`}
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition ${
              p === pos
                ? "bg-blue-500/20 text-blue-400"
                : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800"
            }`}
          >
            {p}
          </Link>
        ))}
      </div>

      <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden overflow-x-auto">
        {isPitcher ? (
          <>
            <div className="grid grid-cols-[2rem_1fr_3.5rem_3rem_3rem_3.5rem_3.5rem_3.5rem_3.5rem_3rem_3.5rem_3.5rem] gap-1 px-3 py-2 bg-zinc-900 border-b border-zinc-800 text-xs text-zinc-500 font-medium min-w-[640px]">
              <span className="text-right">#</span>
              <span>Player</span>
              <span className="text-right">FPTS</span>
              <span className="text-right">W</span>
              <span className="text-right">L</span>
              <span className="text-right">IP</span>
              <span className="text-right">ERA</span>
              <span className="text-right">WHIP</span>
              <span className="text-right">K/9</span>
              <span className="text-right">SO</span>
              <span className="text-right">ADP</span>
              <span className="text-right">WAR</span>
            </div>
            <div className="min-w-[640px]">
              {top.map((p, i) => (
                <PitcherRow key={p.slug} player={p} index={i} />
              ))}
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-[2rem_1fr_3.5rem_3rem_3rem_3rem_3rem_3rem_3.5rem_3.5rem_3.5rem_3.5rem] gap-1 px-3 py-2 bg-zinc-900 border-b border-zinc-800 text-xs text-zinc-500 font-medium min-w-[640px]">
              <span className="text-right">#</span>
              <span>Player</span>
              <span className="text-right">FPTS</span>
              <span className="text-right">HR</span>
              <span className="text-right">R</span>
              <span className="text-right">RBI</span>
              <span className="text-right">SB</span>
              <span className="text-right">H</span>
              <span className="text-right">AVG</span>
              <span className="text-right">OPS</span>
              <span className="text-right">ADP</span>
              <span className="text-right">WAR</span>
            </div>
            <div className="min-w-[640px]">
              {top.map((p, i) => (
                <HitterRow key={p.slug} player={p} index={i} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
