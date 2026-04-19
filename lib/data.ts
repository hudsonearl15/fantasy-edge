import fs from "fs";
import path from "path";

export interface PlayerStats {
  [key: string]: number;
}

export interface PlayerFantasy {
  FPTS: number;
  FPTS_G?: number;
  FPTS_IP?: number;
  ADP: number;
}

export interface Player {
  name: string;
  slug: string;
  team: string;
  teamAbbr: string;
  pos: string;
  type: "hitter" | "pitcher";
  id: string;
  rank: number;
  overallRank?: number;
  stats: PlayerStats;
  fantasy: PlayerFantasy;
}

const DATA_DIR = path.join(process.cwd(), "data");

let _hitters: Player[] | null = null;
let _pitchers: Player[] | null = null;
let _all: Player[] | null = null;

export function getHitters(): Player[] {
  if (!_hitters) {
    _hitters = JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "hitters.json"), "utf-8")
    );
  }
  return _hitters!;
}

export function getPitchers(): Player[] {
  if (!_pitchers) {
    _pitchers = JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "pitchers.json"), "utf-8")
    );
  }
  return _pitchers!;
}

export function getAllPlayers(): Player[] {
  if (!_all) {
    _all = JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "all_players.json"), "utf-8")
    );
  }
  return _all!;
}

export function getPlayerBySlug(slug: string): Player | undefined {
  return getAllPlayers().find((p) => p.slug === slug);
}

export function getPlayersByPosition(pos: string): Player[] {
  return getHitters().filter((h) => h.pos === pos);
}

export const POSITIONS = ["C", "1B", "2B", "SS", "3B", "OF", "DH"] as const;
export const PITCHER_POSITIONS = ["SP", "RP"] as const;

export const TEAM_COLORS: Record<string, string> = {
  NYY: "#003087",
  LAD: "#005A9C",
  BOS: "#BD3039",
  HOU: "#002D62",
  ATL: "#CE1141",
  PHI: "#E81828",
  SEA: "#0C2C56",
  SDP: "#2F241D",
  NYM: "#002D72",
  CHC: "#0E3386",
  DET: "#0C2340",
  KCR: "#004687",
  BAL: "#DF4601",
  MIN: "#002B5C",
  TBR: "#092C5C",
  CLE: "#00385D",
  TEX: "#003278",
  TOR: "#134A8E",
  SFG: "#FD5A1E",
  ARI: "#A71930",
  MIL: "#FFC52F",
  CIN: "#C6011F",
  STL: "#C41E3A",
  PIT: "#27251F",
  COL: "#333366",
  MIA: "#00A3E0",
  WSN: "#AB0003",
  LAA: "#BA0021",
  OAK: "#003831",
  CHW: "#27251F",
};
