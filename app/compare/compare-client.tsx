"use client";

import { useState, useMemo } from "react";

interface ComparePlayer {
  name: string;
  slug: string;
  team: string;
  pos: string;
  type: "hitter" | "pitcher";
  fpts: number;
  adp: number;
  stats: Record<string, number>;
}

function PlayerSearch({
  players,
  onSelect,
  label,
}: {
  players: ComparePlayer[];
  onSelect: (p: ComparePlayer) => void;
  label: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    if (query.length < 2) return [];
    const q = query.toLowerCase();
    return players.filter((p) => p.name.toLowerCase().includes(q)).slice(0, 8);
  }, [query, players]);

  return (
    <div className="relative">
      <label className="text-xs text-zinc-500 mb-1 block">{label}</label>
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search player..."
        className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
      />
      {open && filtered.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-zinc-900 border border-zinc-700 rounded-lg overflow-hidden z-10 shadow-xl">
          {filtered.map((p) => (
            <button
              key={p.slug}
              onClick={() => {
                onSelect(p);
                setQuery(p.name);
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-zinc-800 transition flex justify-between"
            >
              <span className="text-white">{p.name}</span>
              <span className="text-zinc-500">
                {p.team} &middot; {p.pos}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function StatCompareRow({
  label,
  a,
  b,
  higher,
}: {
  label: string;
  a: string;
  b: string;
  higher: "a" | "b" | "none";
}) {
  return (
    <div className="grid grid-cols-3 items-center py-2 border-b border-zinc-800/50">
      <span
        className={`text-right text-sm font-medium ${higher === "a" ? "text-emerald-400" : "text-zinc-300"}`}
      >
        {a}
      </span>
      <span className="text-center text-xs text-zinc-500">{label}</span>
      <span
        className={`text-left text-sm font-medium ${higher === "b" ? "text-emerald-400" : "text-zinc-300"}`}
      >
        {b}
      </span>
    </div>
  );
}

export default function CompareClient({
  players,
}: {
  players: ComparePlayer[];
}) {
  const [playerA, setPlayerA] = useState<ComparePlayer | null>(null);
  const [playerB, setPlayerB] = useState<ComparePlayer | null>(null);

  const bothHitters = playerA?.type === "hitter" && playerB?.type === "hitter";
  const bothPitchers =
    playerA?.type === "pitcher" && playerB?.type === "pitcher";

  const hitterStats = ["HR", "R", "RBI", "SB", "H", "BB", "SO", "AVG", "OBP", "SLG", "OPS", "wOBA", "wRC+", "WAR"];
  const pitcherStats = ["W", "SO", "IP", "ERA", "WHIP", "K/9", "BB/9", "FIP", "WAR"];
  const lowerIsBetter = new Set(["ERA", "WHIP", "BB/9", "SO", "L"]);

  function formatStat(val: number | undefined, key: string): string {
    if (val === undefined || val === null) return "—";
    if (["AVG", "OBP", "SLG", "OPS", "wOBA", "WHIP"].includes(key))
      return val.toFixed(3);
    if (["ERA", "FIP", "K/9", "BB/9", "K/BB", "HR/9"].includes(key))
      return val.toFixed(2);
    if (key === "wRC+") return val.toFixed(0);
    if (key === "WAR") return val.toFixed(1);
    if (key === "IP") return val.toFixed(1);
    return String(val);
  }

  function getHigher(
    a: number | undefined,
    b: number | undefined,
    key: string
  ): "a" | "b" | "none" {
    if (a == null || b == null) return "none";
    if (a === b) return "none";
    const flip = lowerIsBetter.has(key);
    if (flip) return a < b ? "a" : "b";
    return a > b ? "a" : "b";
  }

  const stats =
    bothHitters ? hitterStats : bothPitchers ? pitcherStats : [...new Set([...hitterStats, ...pitcherStats])];

  return (
    <div>
      <div className="grid grid-cols-2 gap-4 mb-8">
        <PlayerSearch
          players={players}
          onSelect={setPlayerA}
          label="Player A"
        />
        <PlayerSearch
          players={players}
          onSelect={setPlayerB}
          label="Player B"
        />
      </div>

      {playerA && playerB && (
        <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 overflow-hidden">
          {/* Headers */}
          <div className="grid grid-cols-3 items-center px-4 py-3 bg-zinc-900 border-b border-zinc-800">
            <div className="text-right">
              <div className="text-sm font-bold text-white">{playerA.name}</div>
              <div className="text-xs text-zinc-500">
                {playerA.team} &middot; {playerA.pos}
              </div>
            </div>
            <div className="text-center text-xs text-zinc-600">vs</div>
            <div className="text-left">
              <div className="text-sm font-bold text-white">{playerB.name}</div>
              <div className="text-xs text-zinc-500">
                {playerB.team} &middot; {playerB.pos}
              </div>
            </div>
          </div>

          {/* FPTS */}
          <div className="px-4">
            <StatCompareRow
              label="FPTS"
              a={playerA.fpts.toFixed(0)}
              b={playerB.fpts.toFixed(0)}
              higher={
                playerA.fpts > playerB.fpts
                  ? "a"
                  : playerA.fpts < playerB.fpts
                    ? "b"
                    : "none"
              }
            />
            <StatCompareRow
              label="ADP"
              a={playerA.adp > 0 ? playerA.adp.toFixed(1) : "—"}
              b={playerB.adp > 0 ? playerB.adp.toFixed(1) : "—"}
              higher={getHigher(playerA.adp, playerB.adp, "ADP")}
            />

            {stats.map((key) => {
              const a = playerA.stats[key];
              const b = playerB.stats[key];
              if (a === undefined && b === undefined) return null;
              return (
                <StatCompareRow
                  key={key}
                  label={key}
                  a={formatStat(a, key)}
                  b={formatStat(b, key)}
                  higher={getHigher(a, b, key)}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
