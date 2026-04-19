import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import {
  getAllPlayers,
  getPlayerBySlug,
  type Player,
} from "@/lib/data";

export const dynamicParams = false;

export async function generateStaticParams() {
  const players = getAllPlayers();
  return players.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const player = getPlayerBySlug(slug);
  if (!player) return { title: "Player Not Found" };

  const desc =
    player.type === "hitter"
      ? `${player.name} 2026 fantasy baseball projections: ${player.stats.HR} HR, ${player.stats.RBI} RBI, ${player.stats.R} R, .${Math.round(player.stats.AVG * 1000)} AVG. ZiPS projects ${player.fantasy.FPTS.toFixed(0)} fantasy points.`
      : `${player.name} 2026 fantasy baseball projections: ${player.stats.W} W, ${player.stats.ERA} ERA, ${player.stats.SO} K, ${player.stats.WHIP} WHIP. ZiPS projects ${player.fantasy.FPTS.toFixed(0)} fantasy points.`;

  return {
    title: `${player.name} — 2026 Fantasy Projections`,
    description: desc,
    openGraph: {
      title: `${player.name} — 2026 Fantasy Projections`,
      description: desc,
    },
  };
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="bg-zinc-900 rounded-lg p-3 text-center">
      <div className="text-xs text-zinc-500 mb-1">{label}</div>
      <div
        className={`text-xl font-bold ${accent ? "text-emerald-400" : "text-white"}`}
      >
        {value}
      </div>
    </div>
  );
}

function HitterStats({ player }: { player: Player }) {
  const s = player.stats;
  return (
    <>
      <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Projected Stats
      </h3>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 mb-6">
        <StatCard label="G" value={s.G} />
        <StatCard label="AB" value={s.AB} />
        <StatCard label="H" value={s.H} />
        <StatCard label="HR" value={s.HR} accent />
        <StatCard label="R" value={s.R} accent />
        <StatCard label="RBI" value={s.RBI} accent />
        <StatCard label="SB" value={s.SB} accent />
        <StatCard label="BB" value={s.BB} />
        <StatCard label="SO" value={s.SO} />
      </div>
      <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Rate Stats
      </h3>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
        <StatCard label="AVG" value={s.AVG?.toFixed(3) ?? "—"} />
        <StatCard label="OBP" value={s.OBP?.toFixed(3) ?? "—"} />
        <StatCard label="SLG" value={s.SLG?.toFixed(3) ?? "—"} />
        <StatCard label="OPS" value={s.OPS?.toFixed(3) ?? "—"} />
        <StatCard label="wOBA" value={s.wOBA?.toFixed(3) ?? "—"} />
        <StatCard label="ISO" value={s.ISO?.toFixed(3) ?? "—"} />
        <StatCard label="BABIP" value={s.BABIP?.toFixed(3) ?? "—"} />
        <StatCard label="wRC+" value={s["wRC+"]?.toFixed(0) ?? "—"} accent />
        <StatCard label="WAR" value={s.WAR?.toFixed(1) ?? "—"} accent />
      </div>
    </>
  );
}

function PitcherStats({ player }: { player: Player }) {
  const s = player.stats;
  return (
    <>
      <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Projected Stats
      </h3>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 mb-6">
        <StatCard label="W" value={s.W} accent />
        <StatCard label="L" value={s.L} />
        <StatCard label={player.pos === "SP" ? "GS" : "G"} value={player.pos === "SP" ? s.GS : s.G} />
        {player.pos === "RP" && <StatCard label="SV" value={s.SV} accent />}
        {player.pos === "RP" && <StatCard label="HLD" value={s.HLD} />}
        <StatCard label="IP" value={s.IP} />
        <StatCard label="SO" value={s.SO} accent />
        <StatCard label="BB" value={s.BB} />
        <StatCard label="HR" value={s.HR} />
      </div>
      <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
        Rate Stats
      </h3>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
        <StatCard label="ERA" value={s.ERA?.toFixed(2) ?? "—"} accent />
        <StatCard label="WHIP" value={s.WHIP?.toFixed(3) ?? "—"} accent />
        <StatCard label="K/9" value={s["K/9"]?.toFixed(2) ?? "—"} />
        <StatCard label="BB/9" value={s["BB/9"]?.toFixed(2) ?? "—"} />
        <StatCard label="K/BB" value={s["K/BB"]?.toFixed(2) ?? "—"} />
        <StatCard label="HR/9" value={s["HR/9"]?.toFixed(2) ?? "—"} />
        <StatCard label="K%" value={s["K%"] != null ? `${s["K%"].toFixed(1)}%` : "—"} />
        <StatCard label="FIP" value={s.FIP?.toFixed(2) ?? "—"} />
        <StatCard label="WAR" value={s.WAR?.toFixed(1) ?? "—"} accent />
      </div>
    </>
  );
}

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const player = getPlayerBySlug(slug);
  if (!player) notFound();

  const all = getAllPlayers();
  const overallRank =
    player.overallRank ?? all.findIndex((p) => p.slug === slug) + 1;

  // Find similar players (same position, close in FPTS)
  const similar = all
    .filter(
      (p) =>
        p.pos === player.pos &&
        p.slug !== player.slug &&
        Math.abs(p.fantasy.FPTS - player.fantasy.FPTS) < player.fantasy.FPTS * 0.2
    )
    .slice(0, 5);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <div className="text-sm text-zinc-500 mb-6">
        <Link href="/" className="hover:text-zinc-300 transition">
          Home
        </Link>
        <span className="mx-2">/</span>
        <Link
          href={`/rankings/${player.pos.toLowerCase()}`}
          className="hover:text-zinc-300 transition"
        >
          {player.pos}
        </Link>
        <span className="mx-2">/</span>
        <span className="text-zinc-300">{player.name}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-4 mb-8">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-xs font-medium bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
              #{overallRank} Overall
            </span>
            <span className="text-xs font-medium bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full">
              {player.pos}
            </span>
          </div>
          <h1 className="text-3xl font-extrabold text-white">
            {player.name}
          </h1>
          <p className="text-zinc-400 mt-1">
            {player.team} &middot; {player.pos} &middot;{" "}
            {player.type === "hitter" ? "Hitter" : "Pitcher"}
          </p>
        </div>
        <div className="flex gap-4">
          <div className="text-center">
            <div className="text-3xl font-extrabold text-emerald-400">
              {player.fantasy.FPTS.toFixed(0)}
            </div>
            <div className="text-xs text-zinc-500">Proj FPTS</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-extrabold text-white">
              {player.fantasy.ADP > 0 ? player.fantasy.ADP.toFixed(1) : "—"}
            </div>
            <div className="text-xs text-zinc-500">ADP</div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="mb-10">
        {player.type === "hitter" ? (
          <HitterStats player={player} />
        ) : (
          <PitcherStats player={player} />
        )}
      </div>

      {/* Similar players */}
      {similar.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Similar Players at {player.pos}
          </h3>
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
            {similar.map((p) => (
              <Link
                key={p.slug}
                href={`/player/${p.slug}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-zinc-800/50 transition border-b border-zinc-800/50 last:border-0"
              >
                <div>
                  <span className="text-sm font-medium text-white">
                    {p.name}
                  </span>
                  <span className="text-xs text-zinc-500 ml-2">
                    {p.teamAbbr}
                  </span>
                </div>
                <span className="text-sm font-semibold text-emerald-400">
                  {p.fantasy.FPTS.toFixed(0)} FPTS
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
