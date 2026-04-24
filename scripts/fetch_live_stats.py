"""
fetch_live_stats.py — Daily stats updater for FantasyEdge

Uses the official MLB Stats API (statsapi.mlb.com) — completely free,
no authentication required, no rate limiting for normal use.

What it does:
  1. Fetches current 2026 season hitting + pitching stats from MLB Stats API
  2. Matches players by name (case-insensitive) against our existing JSON
  3. Preserves original ZiPS projections under `projectedStats` (first run only)
  4. Updates `stats` with live season actuals
  5. Recalculates `fantasy.FPTS` paced to a full season
  6. Stamps `lastUpdated` on every updated player
  7. Re-ranks all players by paced FPTS
  8. Writes back hitters.json, pitchers.json, all_players.json, search_index.json

Safe: if MLB API is unreachable, exits 0 keeping existing data intact.
"""

import json
import math
import os
import sys
import time
from datetime import date

try:
    import requests
except ImportError:
    print("requests not installed — run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(ROOT, "..", "data"))
TODAY = date.today().isoformat()
SEASON = 2026

HEADERS = {
    "User-Agent": "FantasyEdge/1.0 (fantasy baseball stats updater)",
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# MLB Stats API
# ---------------------------------------------------------------------------
MLB_BASE = "https://statsapi.mlb.com/api/v1"


def _get(url: str, label: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  WARNING: {label}: {e}", file=sys.stderr)
        return None


def fetch_hitting_stats() -> list[dict]:
    """Return list of {player_name, stats_dict} for all 2026 hitters."""
    url = (
        f"{MLB_BASE}/stats"
        f"?stats=season&group=hitting&gameType=R"
        f"&season={SEASON}&playerPool=All&limit=3000&offset=0"
    )
    data = _get(url, "MLB hitting stats")
    if not data:
        return []
    results = []
    for stat_group in data.get("stats", []):
        for split in stat_group.get("splits", []):
            player = split.get("player", {})
            name = player.get("fullName", "").strip()
            s = split.get("stat", {})
            if not name:
                continue
            results.append({
                "name": name,
                "mlb_id": str(player.get("id", "")),
                "team": split.get("team", {}).get("name", ""),
                "stat": s,
            })
    return results


def fetch_pitching_stats() -> list[dict]:
    """Return list of {player_name, stats_dict} for all 2026 pitchers."""
    url = (
        f"{MLB_BASE}/stats"
        f"?stats=season&group=pitching&gameType=R"
        f"&season={SEASON}&playerPool=All&limit=3000&offset=0"
    )
    data = _get(url, "MLB pitching stats")
    if not data:
        return []
    results = []
    for stat_group in data.get("stats", []):
        for split in stat_group.get("splits", []):
            player = split.get("player", {})
            name = player.get("fullName", "").strip()
            s = split.get("stat", {})
            if not name:
                continue
            results.append({
                "name": name,
                "mlb_id": str(player.get("id", "")),
                "team": split.get("team", {}).get("name", ""),
                "stat": s,
            })
    return results


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------
def _sf(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        # MLB API returns rate stats as strings like ".285" or "3.45"
        v = float(str(val).replace(",", ""))
        return default if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return default


def _si(val, default=0) -> int:
    try:
        return int(float(str(val).replace(",", "")))
    except (TypeError, ValueError):
        return default


def _parse_ip(ip_str) -> float:
    """Convert MLB innings pitched string '45.1' to decimal 45.333..."""
    try:
        s = str(ip_str)
        if "." in s:
            whole, frac = s.split(".", 1)
            outs = int(frac[0]) if frac else 0
            return float(whole) + outs / 3.0
        return float(s)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Build lookup: name (lower) → row
# ---------------------------------------------------------------------------
def build_name_lookup(rows: list[dict]) -> dict:
    lookup = {}
    for row in rows:
        key = row["name"].lower()
        lookup[key] = row
    return lookup


def find_row(player: dict, lookup: dict):
    name = player.get("name", "").strip().lower()
    if name in lookup:
        return lookup[name]
    # Try last name only as weak fallback
    parts = name.split()
    if len(parts) >= 2:
        last = parts[-1]
        for k, v in lookup.items():
            if k.endswith(last) and abs(len(k) - len(name)) < 5:
                return v
    return None


# ---------------------------------------------------------------------------
# Stat extraction from MLB API row
# ---------------------------------------------------------------------------
def extract_hitter_stats(s: dict) -> dict:
    g   = _si(s.get("gamesPlayed"))
    ab  = _si(s.get("atBats"))
    pa  = _si(s.get("plateAppearances"))
    h   = _si(s.get("hits"))
    hr  = _si(s.get("homeRuns"))
    r   = _si(s.get("runs"))
    rbi = _si(s.get("rbi"))
    bb  = _si(s.get("baseOnBalls"))
    so  = _si(s.get("strikeOuts"))
    sb  = _si(s.get("stolenBases"))
    cs  = _si(s.get("caughtStealing"))
    d   = _si(s.get("doubles"))
    t   = _si(s.get("triples"))
    singles = max(0, h - d - t - hr)

    avg  = _sf(s.get("avg"))
    obp  = _sf(s.get("obp"))
    slg  = _sf(s.get("slg"))
    ops  = _sf(s.get("ops")) or round(obp + slg, 3)

    return {
        "G": g, "AB": ab, "PA": pa, "H": h,
        "1B": singles, "2B": d, "3B": t, "HR": hr,
        "R": r, "RBI": rbi, "BB": bb, "SO": so,
        "SB": sb, "CS": cs,
        "AVG":  round(avg, 3),
        "OBP":  round(obp, 3),
        "SLG":  round(slg, 3),
        "OPS":  round(ops, 3),
        # Advanced stats not in MLB API — preserve existing or zero
        "wOBA": 0.0, "ISO": round(max(0.0, slg - avg), 3),
        "BABIP": 0.0, "wRC+": 0.0, "WAR": 0.0,
    }


def extract_pitcher_stats(s: dict) -> dict:
    ip  = _parse_ip(s.get("inningsPitched", 0))
    g   = _si(s.get("gamesPitched") or s.get("gamesPlayed"))
    gs  = _si(s.get("gamesStarted"))
    w   = _si(s.get("wins"))
    l   = _si(s.get("losses"))
    sv  = _si(s.get("saves"))
    hld = _si(s.get("holds"))
    so  = _si(s.get("strikeOuts"))
    bb  = _si(s.get("baseOnBalls"))
    hr  = _si(s.get("homeRuns"))
    era = _sf(s.get("era"))
    whip = _sf(s.get("whip"))

    k9  = round((so / ip) * 9, 2) if ip > 0 else 0.0
    bb9 = round((bb / ip) * 9, 2) if ip > 0 else 0.0
    kbb = round(so / bb, 2) if bb > 0 else 0.0
    hr9 = round((hr / ip) * 9, 2) if ip > 0 else 0.0
    kpct = round((so / (so + bb + _si(s.get("battersFaced", 0)) - so - bb) * 100), 1) if ip > 0 else 0.0

    return {
        "W": w, "L": l, "G": g, "GS": gs, "SV": sv, "HLD": hld,
        "IP":   round(ip, 1),
        "ERA":  round(era, 2),
        "WHIP": round(whip, 3),
        "K/9":  k9, "BB/9": bb9, "K/BB": kbb, "HR/9": hr9,
        "SO":   so, "BB": bb, "HR": hr,
        "K%":   kpct, "BB%": 0.0,
        "FIP":  0.0, "WAR": 0.0,
    }


# ---------------------------------------------------------------------------
# Merge advanced stats from existing data (preserve wOBA, FIP, etc.)
# ---------------------------------------------------------------------------
def merge_advanced_stats(new_stats: dict, existing_stats: dict, player_type: str):
    """Keep advanced stats from existing data that MLB API doesn't provide."""
    if player_type == "hitter":
        for key in ("wOBA", "BABIP", "wRC+", "WAR"):
            if existing_stats.get(key, 0) != 0:
                new_stats[key] = existing_stats[key]
    else:
        for key in ("FIP", "WAR", "K%", "BB%"):
            if existing_stats.get(key, 0) != 0:
                new_stats[key] = existing_stats[key]


# ---------------------------------------------------------------------------
# FPTS pacing — project current stats to a full season
# ---------------------------------------------------------------------------
TARGET_PA   = 600    # full season for a hitter
TARGET_IP_SP = 180   # full season for a starter
TARGET_IP_RP = 65    # full season for a reliever


def pace_hitter_fpts(stats: dict, proj_fpts: float) -> tuple[float, float]:
    g  = stats.get("G", 0)
    pa = stats.get("PA", 0)
    if g < 5 or pa < 15:
        # Too few games — return the original ZiPS projection unchanged
        return proj_fpts, round(proj_fpts / TARGET_PA, 2)

    scale = min(TARGET_PA / pa, 8.0)

    pts  = (stats.get("R",   0) * 1.0 +
            stats.get("HR",  0) * 4.0 +
            stats.get("RBI", 0) * 1.0 +
            stats.get("SB",  0) * 2.0 +
            stats.get("BB",  0) * 0.5 +
            stats.get("H",   0) * 0.5 +
            stats.get("2B",  0) * 1.0 +
            stats.get("3B",  0) * 2.0) * scale

    fpts_g = pts / (g * scale) if g * scale > 0 else 0.0
    return round(pts, 1), round(fpts_g, 2)


def pace_pitcher_fpts(stats: dict, pos: str, proj_fpts: float) -> tuple[float, float]:
    g  = stats.get("G", 0)
    ip = stats.get("IP", 0.0)
    if g < 2 or ip < 5:
        return proj_fpts, round(proj_fpts / (TARGET_IP_SP if pos == "SP" else TARGET_IP_RP), 2)

    target = TARGET_IP_SP if pos == "SP" else TARGET_IP_RP
    scale  = min(target / ip, 12.0)

    pts = (stats.get("W",   0) * 5.0 +
           stats.get("SV",  0) * 5.0 +
           stats.get("HLD", 0) * 2.0 +
           stats.get("SO",  0) * 1.0 +
           stats.get("IP",  0) * 1.0) * scale

    fpts_ip = pts / (ip * scale) if ip * scale > 0 else 0.0
    return round(pts, 1), round(fpts_ip, 2)


# ---------------------------------------------------------------------------
# Update players in-place
# ---------------------------------------------------------------------------
def update_players(players: list[dict], lookup: dict, player_type: str) -> tuple[int, int]:
    matched = 0
    for player in players:
        row = find_row(player, lookup)
        player["lastUpdated"] = TODAY

        if row is None:
            continue

        matched += 1
        s = row["stat"]
        orig_stats = dict(player["stats"])

        # Preserve ZiPS projections on first update
        if "projectedStats" not in player:
            player["projectedStats"] = orig_stats

        # Update stats with current season actuals
        if player_type == "hitter":
            new_stats = extract_hitter_stats(s)
            merge_advanced_stats(new_stats, orig_stats, "hitter")
            player["stats"] = new_stats
            fpts, fpts_g = pace_hitter_fpts(new_stats, player["fantasy"]["FPTS"])
            player["fantasy"]["FPTS"]   = fpts
            player["fantasy"]["FPTS_G"] = fpts_g
        else:
            new_stats = extract_pitcher_stats(s)
            merge_advanced_stats(new_stats, orig_stats, "pitcher")
            player["stats"] = new_stats
            fpts, fpts_ip = pace_pitcher_fpts(new_stats, player.get("pos", "SP"), player["fantasy"]["FPTS"])
            player["fantasy"]["FPTS"]    = fpts
            player["fantasy"]["FPTS_IP"] = fpts_ip

        # Update team if we got one from MLB API
        if row.get("team"):
            player["team"] = row["team"]

    return matched, len(players)


def re_rank(players: list[dict], key: str = "rank"):
    players.sort(key=lambda p: p["fantasy"]["FPTS"], reverse=True)
    for i, p in enumerate(players):
        p[key] = i + 1


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def load_json(filename: str) -> list:
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, data, indent=2):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
    kb = os.path.getsize(path) // 1024
    print(f"  Wrote {filename} ({len(data)} records, {kb} KB)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print(f"=== FantasyEdge stats update — {TODAY} ===")

    # 1. Fetch MLB Stats API
    print("\nFetching MLB Stats API…")
    hit_rows = fetch_hitting_stats()
    time.sleep(0.5)
    pit_rows = fetch_pitching_stats()

    if not hit_rows and not pit_rows:
        print("No data returned — keeping existing data.")
        sys.exit(0)

    print(f"  {len(hit_rows)} hitters / {len(pit_rows)} pitchers from MLB API")

    # 2. Build lookups
    hit_lookup = build_name_lookup(hit_rows)
    pit_lookup = build_name_lookup(pit_rows)

    # 3. Load existing JSON
    print("\nLoading existing JSON…")
    hitters  = load_json("hitters.json")
    pitchers = load_json("pitchers.json")

    # 4. Update
    print("Updating hitters…")
    hm, ht = update_players(hitters, hit_lookup, "hitter")
    print(f"  Matched {hm}/{ht} hitters")

    print("Updating pitchers…")
    pm, pt = update_players(pitchers, pit_lookup, "pitcher")
    print(f"  Matched {pm}/{pt} pitchers")

    # 5. Re-rank
    re_rank(hitters, "rank")
    re_rank(pitchers, "rank")

    # 6. Rebuild all_players + search index
    all_players = hitters + pitchers
    all_players.sort(key=lambda p: p["fantasy"]["FPTS"], reverse=True)
    for i, p in enumerate(all_players):
        p["overallRank"] = i + 1

    search_index = [
        {"n": p["name"], "s": p["slug"], "t": p.get("teamAbbr", ""),
         "p": p["pos"], "r": p["overallRank"], "f": p["fantasy"]["FPTS"]}
        for p in all_players
    ]

    # 7. Save
    print("\nSaving…")
    save_json("hitters.json",    hitters)
    save_json("pitchers.json",   pitchers)
    save_json("all_players.json", all_players)
    save_json("search_index.json", search_index, indent=None)

    print(f"\nDone! {hm + pm} players updated with {TODAY} stats.")
    if hitters:
        print(f"  Top hitter:  {hitters[0]['name']} — {hitters[0]['fantasy']['FPTS']} FPTS")
    if pitchers:
        print(f"  Top pitcher: {pitchers[0]['name']} — {pitchers[0]['fantasy']['FPTS']} FPTS")


if __name__ == "__main__":
    main()
