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
# Update players in-place
# Rankings and FPTS are intentionally NOT changed — ZiPS projections are the
# authoritative ranking source. We only update the live stat display fields.
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

        # Preserve original ZiPS projections on first update (one-time)
        if "projectedStats" not in player:
            player["projectedStats"] = orig_stats

        # Update live stats for display — does NOT touch FPTS or rankings
        if player_type == "hitter":
            new_stats = extract_hitter_stats(s)
            merge_advanced_stats(new_stats, orig_stats, "hitter")
            player["stats"] = new_stats
        else:
            new_stats = extract_pitcher_stats(s)
            merge_advanced_stats(new_stats, orig_stats, "pitcher")
            player["stats"] = new_stats

        # Update team if MLB API has a more current value
        if row.get("team"):
            player["team"] = row["team"]

    return matched, len(players)


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

    # 5. Rebuild all_players + search index
    # Rankings (rank, overallRank) and FPTS are intentionally preserved from
    # ZiPS — only raw stats were updated above for live display purposes.
    all_players = hitters + pitchers
    all_players.sort(key=lambda p: p.get("overallRank", 9999))

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

    # Show top-ranked players (by ZiPS rank, unchanged)
    top_h = sorted(hitters, key=lambda p: p.get("rank", 9999))
    top_p = sorted(pitchers, key=lambda p: p.get("rank", 9999))
    print(f"\nDone! {hm + pm} players updated with {TODAY} live stats (rankings unchanged).")
    if top_h:
        p = top_h[0]
        g = p["stats"].get("G", 0)
        print(f"  #1 hitter:  {p['name']} — {g}G, {p['stats'].get('HR',0)} HR, .{str(p['stats'].get('AVG',0))[2:]} AVG (ZiPS FPTS: {p['fantasy']['FPTS']})")
    if top_p:
        p = top_p[0]
        print(f"  #1 pitcher: {p['name']} — {p['stats'].get('IP',0)} IP, {p['stats'].get('ERA',0)} ERA, {p['stats'].get('SO',0)} K (ZiPS FPTS: {p['fantasy']['FPTS']})")


if __name__ == "__main__":
    main()
