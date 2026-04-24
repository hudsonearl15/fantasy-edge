"""
fetch_live_stats.py — Daily stats updater for FantasyEdge

Fetches current 2026 season stats from Fangraphs public API, matches players
by their Fangraphs ID, and updates site/data/*.json in-place.

- Preserves original ZiPS projections under `projectedStats`
- Overwrites `stats` with live 2026 season actuals
- Adds `lastUpdated` (ISO date) to every player
- Recalculates `fantasy.FPTS` and rankings based on current-pace stats
- Writes back hitters.json, pitchers.json, all_players.json, search_index.json

Safe to re-run: if Fangraphs is unreachable, exits 0 and keeps existing data.
"""

import json
import os
import sys
import time
from datetime import date, datetime
from typing import Any

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEASON = 2026
TODAY = date.today().isoformat()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.fangraphs.com/leaders/major-league",
    "Accept": "application/json, text/plain, */*",
}

# Roto scoring weights (standard 5x5: R, HR, RBI, SB, AVG — here we use
# counting stats approach common on Fangraphs draft tools)
# These match the FPTS formula used when generating the ZiPS CSVs.
HITTER_WEIGHTS = {
    "R":    1.0,
    "HR":   4.0,
    "RBI":  1.0,
    "SB":   2.0,
    "AVG":  0.0,   # categorical, not added to points
    "BB":   0.5,
    "H":    0.5,
    "2B":   1.0,
    "3B":   2.0,
}

PITCHER_WEIGHTS = {
    "W":    5.0,
    "SV":   5.0,
    "HLD":  2.0,
    "SO":   1.0,
    "ERA":  0.0,   # categorical
    "WHIP": 0.0,   # categorical
    "IP":   1.0,
}


# ---------------------------------------------------------------------------
# Fangraphs API fetch
# ---------------------------------------------------------------------------
FG_BASE = "https://www.fangraphs.com/api/leaders/major-league/data"
FG_PARAMS_BASE = (
    f"?pos=all&lg=all&qual=0&season={SEASON}&season1={SEASON}"
    "&startdate=&enddate=&month=0&hand=&team=0"
    "&pageitems=100000&pagenum=1&ind=0&rost=0&players=0"
    "&postseason=&sortdir=default"
)


def _fetch(url: str, label: str) -> list[dict] | None:
    """Fetch Fangraphs API, return data list or None on error."""
    try:
        print(f"  Fetching {label}…")
        r = requests.get(url, headers=HEADERS, timeout=40)
        r.raise_for_status()
        payload = r.json()
        # API may return {"data": [...]} or just [...]
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "Data", "players", "rows"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
        print(f"  WARNING: unexpected response shape for {label}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  WARNING: could not fetch {label}: {e}", file=sys.stderr)
        return None


def fetch_hitter_stats() -> list[dict] | None:
    url = FG_BASE + FG_PARAMS_BASE + "&stats=bat&type=8&sortstat=WAR"
    data = _fetch(url, "hitters/standard")
    if data:
        return data
    # Fallback: try dashboard stats
    url2 = FG_BASE + FG_PARAMS_BASE + "&stats=bat&type=0&sortstat=WAR"
    return _fetch(url2, "hitters/dashboard (fallback)")


def fetch_pitcher_stats() -> list[dict] | None:
    url = FG_BASE + FG_PARAMS_BASE + "&stats=pit&type=8&sortstat=WAR"
    data = _fetch(url, "pitchers/standard")
    if data:
        return data
    url2 = FG_BASE + FG_PARAMS_BASE + "&stats=pit&type=0&sortstat=WAR"
    return _fetch(url2, "pitchers/dashboard (fallback)")


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------
def _sf(val, default=0.0) -> float:
    try:
        v = float(val)
        import math
        return default if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return default


def _si(val, default=0) -> int:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Build lookup from API data: {str(playerid): row_dict}
# Also build name → row_dict as fallback
# ---------------------------------------------------------------------------
def build_lookup(rows: list[dict]) -> tuple[dict, dict]:
    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for row in rows:
        pid = row.get("playerid") or row.get("PlayerId") or row.get("xMLBAMID")
        name = (row.get("PlayerName") or row.get("Name") or "").strip()
        if pid:
            by_id[str(pid)] = row
        if name:
            by_name[name.lower()] = row
    return by_id, by_name


def find_row(player: dict, by_id: dict, by_name: dict) -> dict | None:
    """Match a player from our JSON to a Fangraphs API row."""
    pid = str(player.get("id", "")).strip()
    if pid and pid in by_id:
        return by_id[pid]
    name = player.get("name", "").strip().lower()
    if name in by_name:
        return by_name[name]
    return None


# ---------------------------------------------------------------------------
# Stat extraction from API row
# ---------------------------------------------------------------------------
def extract_hitter_stats(row: dict) -> dict:
    g = _si(row.get("G"))
    ab = _si(row.get("AB"))
    pa = _si(row.get("PA"))
    h = _si(row.get("H"))
    hr = _si(row.get("HR"))
    r = _si(row.get("R"))
    rbi = _si(row.get("RBI"))
    bb = _si(row.get("BB"))
    so = _si(row.get("SO"))
    sb = _si(row.get("SB"))
    cs = _si(row.get("CS"))

    # Singles: try direct, else derive from H - 2B - 3B - HR
    singles = _si(row.get("1B"))
    doubles = _si(row.get("2B"))
    triples = _si(row.get("3B"))
    if singles == 0 and h > 0:
        singles = max(0, h - doubles - triples - hr)

    avg = _sf(row.get("AVG"))
    obp = _sf(row.get("OBP"))
    slg = _sf(row.get("SLG"))
    ops = _sf(row.get("OPS")) or round(obp + slg, 3)
    woba = _sf(row.get("wOBA"))
    iso = _sf(row.get("ISO")) or (round(slg - avg, 3) if slg and avg else 0.0)
    babip = _sf(row.get("BABIP"))
    wrc_plus = _sf(row.get("wRC+"))
    war = _sf(row.get("WAR"))

    return {
        "G": g, "AB": ab, "PA": pa, "H": h,
        "1B": singles, "2B": doubles, "3B": triples, "HR": hr,
        "R": r, "RBI": rbi, "BB": bb, "SO": so,
        "SB": sb, "CS": cs,
        "AVG": round(avg, 3), "OBP": round(obp, 3),
        "SLG": round(slg, 3), "OPS": round(ops, 3),
        "wOBA": round(woba, 3), "ISO": round(iso, 3),
        "BABIP": round(babip, 3),
        "wRC+": round(wrc_plus, 1),
        "WAR": round(war, 1),
    }


def extract_pitcher_stats(row: dict) -> dict:
    w = _si(row.get("W"))
    l = _si(row.get("L"))
    g = _si(row.get("G"))
    gs = _si(row.get("GS"))
    sv = _si(row.get("SV"))
    hld = _si(row.get("HLD"))
    ip = _sf(row.get("IP"))
    era = _sf(row.get("ERA"))
    whip = _sf(row.get("WHIP"))
    k9 = _sf(row.get("K/9"))
    bb9 = _sf(row.get("BB/9"))
    k_bb = _sf(row.get("K/BB"))
    hr9 = _sf(row.get("HR/9"))
    so = _si(row.get("SO"))
    bb = _si(row.get("BB"))
    hr = _si(row.get("HR"))
    # K% / BB% — Fangraphs returns as decimals (0.31 = 31%) or percentages
    kpct_raw = _sf(row.get("K%", 0))
    bbpct_raw = _sf(row.get("BB%", 0))
    k_pct = round(kpct_raw * 100, 1) if kpct_raw < 1 else round(kpct_raw, 1)
    bb_pct = round(bbpct_raw * 100, 1) if bbpct_raw < 1 else round(bbpct_raw, 1)
    fip = _sf(row.get("FIP"))
    war = _sf(row.get("WAR"))

    return {
        "W": w, "L": l, "G": g, "GS": gs, "SV": sv, "HLD": hld,
        "IP": round(ip, 1), "ERA": round(era, 2), "WHIP": round(whip, 3),
        "K/9": round(k9, 2), "BB/9": round(bb9, 2),
        "K/BB": round(k_bb, 2), "HR/9": round(hr9, 2),
        "SO": so, "BB": bb, "HR": hr,
        "K%": k_pct, "BB%": bb_pct,
        "FIP": round(fip, 2), "WAR": round(war, 1),
    }


# ---------------------------------------------------------------------------
# FPTS recalculation (paced to 600 PA for hitters, 200 IP for SP, 70 G for RP)
# ---------------------------------------------------------------------------
TARGET_PA = 600
TARGET_IP_SP = 200
TARGET_IP_RP = 70


def pace_hitter_fpts(stats: dict) -> tuple[float, float]:
    """Return (FPTS, FPTS_G) paced to a full season."""
    g = stats.get("G", 0)
    pa = stats.get("PA", 0)
    if g < 5 or pa < 15:
        return 0.0, 0.0  # too few games, not reliable

    # Scale factor: ratio of target PA to actual PA
    scale = TARGET_PA / pa if pa > 0 else 1.0
    # Cap scale to avoid exploding values early in season
    scale = min(scale, 10.0)

    pts = 0.0
    for stat, weight in HITTER_WEIGHTS.items():
        if weight == 0:
            continue
        pts += stats.get(stat, 0) * weight * scale

    fpts_g = pts / (g * scale) if (g * scale) > 0 else 0.0
    return round(pts, 1), round(fpts_g, 2)


def pace_pitcher_fpts(stats: dict, pos: str) -> tuple[float, float]:
    """Return (FPTS, FPTS_IP) paced to a full season."""
    g = stats.get("G", 0)
    ip = stats.get("IP", 0.0)
    if g < 2 or ip < 5:
        return 0.0, 0.0

    target_ip = TARGET_IP_SP if pos == "SP" else TARGET_IP_RP
    scale = target_ip / ip if ip > 0 else 1.0
    scale = min(scale, 15.0)

    pts = 0.0
    for stat, weight in PITCHER_WEIGHTS.items():
        if weight == 0:
            continue
        pts += stats.get(stat, 0) * weight * scale

    fpts_ip = pts / (ip * scale) if (ip * scale) > 0 else 0.0
    return round(pts, 1), round(fpts_ip, 2)


# ---------------------------------------------------------------------------
# Main update logic
# ---------------------------------------------------------------------------
def update_players(
    players: list[dict],
    by_id: dict,
    by_name: dict,
    player_type: str,  # "hitter" or "pitcher"
) -> tuple[int, int]:
    """Update players in-place. Returns (matched, total)."""
    matched = 0
    for player in players:
        row = find_row(player, by_id, by_name)
        if row is None:
            # No live data found — keep existing stats, just stamp date
            player["lastUpdated"] = TODAY
            continue

        matched += 1

        # Preserve original ZiPS projections the first time we see them
        if "projectedStats" not in player:
            player["projectedStats"] = dict(player["stats"])

        # Overwrite stats with current season actuals
        if player_type == "hitter":
            player["stats"] = extract_hitter_stats(row)
            fpts, fpts_g = pace_hitter_fpts(player["stats"])
            if fpts > 0:
                player["fantasy"]["FPTS"] = fpts
                player["fantasy"]["FPTS_G"] = fpts_g
        else:
            player["stats"] = extract_pitcher_stats(row)
            fpts, fpts_ip = pace_pitcher_fpts(player["stats"], player.get("pos", "SP"))
            if fpts > 0:
                player["fantasy"]["FPTS"] = fpts
                player["fantasy"]["FPTS_IP"] = fpts_ip

        player["lastUpdated"] = TODAY

    return matched, len(players)


def re_rank(players: list[dict], rank_key: str = "rank"):
    """Re-sort by FPTS descending and assign sequential ranks."""
    players.sort(key=lambda p: p["fantasy"]["FPTS"], reverse=True)
    for i, p in enumerate(players):
        p[rank_key] = i + 1


# ---------------------------------------------------------------------------
# Load / save helpers
# ---------------------------------------------------------------------------
def load_json(filename: str) -> list:
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, data: Any, indent: int = 2):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
    print(f"  Wrote {filename} ({len(data)} records)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print(f"=== FantasyEdge stats update — {TODAY} ===")

    # 1. Fetch from Fangraphs
    print("\nFetching Fangraphs live stats…")
    hitter_rows = fetch_hitter_stats()
    time.sleep(1)  # be polite
    pitcher_rows = fetch_pitcher_stats()

    if not hitter_rows and not pitcher_rows:
        print("\nNo data fetched — Fangraphs may be unreachable. Keeping existing data.")
        sys.exit(0)

    # 2. Build lookups
    h_by_id, h_by_name = build_lookup(hitter_rows or [])
    p_by_id, p_by_name = build_lookup(pitcher_rows or [])
    print(f"  {len(h_by_id)} hitters / {len(p_by_id)} pitchers available from Fangraphs")

    # 3. Load existing JSON
    print("\nLoading existing JSON…")
    hitters = load_json("hitters.json")
    pitchers = load_json("pitchers.json")

    # 4. Update stats
    print("\nUpdating hitters…")
    hm, ht = update_players(hitters, h_by_id, h_by_name, "hitter")
    print(f"  Matched {hm}/{ht} hitters")

    print("Updating pitchers…")
    pm, pt = update_players(pitchers, p_by_id, p_by_name, "pitcher")
    print(f"  Matched {pm}/{pt} pitchers")

    # 5. Re-rank
    re_rank(hitters, "rank")
    re_rank(pitchers, "rank")

    # 6. Rebuild all_players
    all_players = hitters + pitchers
    all_players.sort(key=lambda p: p["fantasy"]["FPTS"], reverse=True)
    for i, p in enumerate(all_players):
        p["overallRank"] = i + 1

    # 7. Rebuild search index
    search_index = [
        {
            "n": p["name"],
            "s": p["slug"],
            "t": p.get("teamAbbr", ""),
            "p": p["pos"],
            "r": p["overallRank"],
            "f": p["fantasy"]["FPTS"],
        }
        for p in all_players
    ]

    # 8. Save
    print("\nSaving…")
    save_json("hitters.json", hitters)
    save_json("pitchers.json", pitchers)
    save_json("all_players.json", all_players)
    save_json("search_index.json", search_index, indent=None)

    print(f"\nDone! {hm + pm} players updated with {TODAY} stats.")
    print(f"  Top hitter: {hitters[0]['name']} — {hitters[0]['fantasy']['FPTS']} FPTS")
    print(f"  Top pitcher: {pitchers[0]['name']} — {pitchers[0]['fantasy']['FPTS']} FPTS")


if __name__ == "__main__":
    main()
