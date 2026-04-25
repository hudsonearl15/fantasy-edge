"""
fetch_live_stats.py — Daily stats updater for FantasyEdge

Uses the official MLB Stats API (statsapi.mlb.com) — completely free,
no authentication required, no rate limiting for normal use.

What it does:
  1. Fetches current 2026 season hitting + pitching stats from MLB Stats API
  2. Matches players by name (case-insensitive, exact only — no fallback)
  3. Preserves original ZiPS projections under `projectedStats` (first run only)
  4. Updates `stats` with live season actuals
  5. For players with enough live data (15+ G hitters / 15+ IP pitchers):
       - Paces stats to a full season (162 G / 200 IP starters / 70 IP relievers)
       - Recalculates fantasy.FPTS using the same Fangraphs scoring formula
       - Updates fantasy.liveRank flag so the UI can indicate live ranking
  6. For players without enough live data: keeps ZiPS FPTS unchanged
  7. Re-ranks ALL players by their effective FPTS (live or ZiPS)
  8. Stamps `lastUpdated` and `statSource` on every player
  9. Writes back hitters.json, pitchers.json, all_players.json, search_index.json

Safe: if MLB API is unreachable, exits 0 keeping existing data intact.

Scoring formula (reverse-engineered from Fangraphs ZiPS FPTS column):
  Hitters:  R*2 + 1B*2 + 2B*4 + 3B*6 + HR*8 + RBI*2 + BB*2 + SB*4 + CS*-2 + HBP*2 + SO*-1
  Pitchers: W*3 + L*-3 + SV*5 + HLD*4 + IP*4 + SO*3 + BB*-3 + HR*-13
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

# Minimum live data required before we trust paced stats over ZiPS
MIN_GAMES_HITTER  = 15   # games played
MIN_IP_STARTER    = 20.0 # innings pitched
MIN_IP_RELIEVER   = 10.0 # innings pitched

# Full-season targets for pacing
FULL_GAMES        = 162
FULL_IP_STARTER   = 200.0
FULL_IP_RELIEVER  = 70.0

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
    """Return list of {name, mlb_id, team, stat} for all 2026 hitters."""
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
    """Return list of {name, mlb_id, team, stat} for all 2026 pitchers."""
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
# Exact-name-only lookup (no last-name fallback — that caused corrupt data)
# ---------------------------------------------------------------------------
def build_name_lookup(rows: list[dict]) -> dict:
    lookup = {}
    for row in rows:
        key = row["name"].lower()
        lookup[key] = row
    return lookup


def find_row(player: dict, lookup: dict):
    """Exact name match only. Returns None if not found."""
    name = player.get("name", "").strip().lower()
    return lookup.get(name)


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
    hbp = _si(s.get("hitByPitch"))
    singles = max(0, h - d - t - hr)

    avg = _sf(s.get("avg"))
    obp = _sf(s.get("obp"))
    slg = _sf(s.get("slg"))
    ops = _sf(s.get("ops")) or round(obp + slg, 3)

    return {
        "G": g, "AB": ab, "PA": pa, "H": h,
        "1B": singles, "2B": d, "3B": t, "HR": hr,
        "R": r, "RBI": rbi, "BB": bb, "SO": so,
        "SB": sb, "CS": cs, "HBP": hbp,
        "AVG":  round(avg, 3),
        "OBP":  round(obp, 3),
        "SLG":  round(slg, 3),
        "OPS":  round(ops, 3),
        "wOBA": 0.0, "ISO": round(max(0.0, slg - avg), 3),
        "BABIP": 0.0, "wRC+": 0.0, "WAR": 0.0,
    }


def extract_pitcher_stats(s: dict) -> dict:
    ip   = _parse_ip(s.get("inningsPitched", 0))
    g    = _si(s.get("gamesPitched") or s.get("gamesPlayed"))
    gs   = _si(s.get("gamesStarted"))
    w    = _si(s.get("wins"))
    l    = _si(s.get("losses"))
    sv   = _si(s.get("saves"))
    hld  = _si(s.get("holds"))
    so   = _si(s.get("strikeOuts"))
    bb   = _si(s.get("baseOnBalls"))
    hr   = _si(s.get("homeRuns"))
    era  = _sf(s.get("era"))
    whip = _sf(s.get("whip"))

    k9  = round((so / ip) * 9, 2) if ip > 0 else 0.0
    bb9 = round((bb / ip) * 9, 2) if ip > 0 else 0.0
    kbb = round(so / bb, 2) if bb > 0 else 0.0
    hr9 = round((hr / ip) * 9, 2) if ip > 0 else 0.0

    return {
        "W": w, "L": l, "G": g, "GS": gs, "SV": sv, "HLD": hld,
        "IP":   round(ip, 1),
        "ERA":  round(era, 2),
        "WHIP": round(whip, 3),
        "K/9":  k9, "BB/9": bb9, "K/BB": kbb, "HR/9": hr9,
        "SO":   so, "BB": bb, "HR": hr,
        "K%":   0.0, "BB%": 0.0,
        "FIP":  0.0, "WAR": 0.0,
    }


# ---------------------------------------------------------------------------
# Merge advanced stats from existing data (preserve wOBA, FIP, etc.)
# ---------------------------------------------------------------------------
def merge_advanced_stats(new_stats: dict, existing_stats: dict, player_type: str):
    if player_type == "hitter":
        for key in ("wOBA", "BABIP", "wRC+", "WAR"):
            if existing_stats.get(key, 0) != 0:
                new_stats[key] = existing_stats[key]
    else:
        for key in ("FIP", "WAR", "K%", "BB%"):
            if existing_stats.get(key, 0) != 0:
                new_stats[key] = existing_stats[key]


# ---------------------------------------------------------------------------
# FPTS calculation from live stats
# ---------------------------------------------------------------------------
def calc_hitter_fpts(stats: dict) -> float:
    """
    Fangraphs fantasy scoring formula (reverse-engineered from ZiPS FPTS):
      R*2 + 1B*2 + 2B*4 + 3B*6 + HR*8 + RBI*2 + BB*2 + SB*4 + CS*-2 + HBP*2 + SO*-1
    """
    return (
        stats.get("R",   0) * 2   +
        stats.get("1B",  0) * 2   +
        stats.get("2B",  0) * 4   +
        stats.get("3B",  0) * 6   +
        stats.get("HR",  0) * 8   +
        stats.get("RBI", 0) * 2   +
        stats.get("BB",  0) * 2   +
        stats.get("SB",  0) * 4   +
        stats.get("CS",  0) * -2  +
        stats.get("HBP", 0) * 2   +
        stats.get("SO",  0) * -1
    )


def calc_pitcher_fpts(stats: dict) -> float:
    """
    Fangraphs fantasy scoring formula (reverse-engineered from ZiPS FPTS):
      W*3 + L*-3 + SV*5 + HLD*4 + IP*4 + SO*3 + BB*-3 + HR*-13
    """
    return (
        stats.get("W",   0) * 3   +
        stats.get("L",   0) * -3  +
        stats.get("SV",  0) * 5   +
        stats.get("HLD", 0) * 4   +
        stats.get("IP",  0) * 4   +
        stats.get("SO",  0) * 3   +
        stats.get("BB",  0) * -3  +
        stats.get("HR",  0) * -13
    )


def pace_hitter_stats(stats: dict) -> dict:
    """Scale raw counting stats to a full 162-game season."""
    g = stats.get("G", 0)
    if g <= 0:
        return stats
    factor = FULL_GAMES / g
    paced = {}
    counting = {"AB","PA","H","1B","2B","3B","HR","R","RBI","BB","SO","SB","CS","HBP"}
    for k, v in stats.items():
        paced[k] = round(v * factor) if k in counting else v
    paced["G"] = FULL_GAMES
    return paced


def pace_pitcher_stats(stats: dict, is_starter: bool) -> dict:
    """Scale raw counting stats to a full-season IP target."""
    ip = stats.get("IP", 0.0)
    if ip <= 0:
        return stats
    target = FULL_IP_STARTER if is_starter else FULL_IP_RELIEVER
    factor = target / ip
    paced = {}
    counting = {"W","L","G","GS","SV","HLD","SO","BB","HR"}
    for k, v in stats.items():
        paced[k] = round(v * factor) if k in counting else v
    paced["IP"] = round(target, 1)
    return paced


# ---------------------------------------------------------------------------
# Update players in-place
# ---------------------------------------------------------------------------
def update_players(
    players: list[dict],
    lookup: dict,
    player_type: str,
    orig_lookup: dict,  # slug→original ZiPS player (source of truth for fallback FPTS)
) -> tuple[int, int]:
    matched = 0
    for player in players:
        row = find_row(player, lookup)
        slug = player["slug"]
        orig = orig_lookup.get(slug, {})

        # Always stamp today
        player["lastUpdated"] = TODAY

        # Preserve ZiPS projectedStats on first run
        if "projectedStats" not in player:
            player["projectedStats"] = orig.get("stats", dict(player["stats"]))

        if row is None:
            # Not yet in 2026 data — keep ZiPS stats + FPTS
            player["statSource"] = "ZiPS"
            continue

        matched += 1
        s = row["stat"]
        orig_stats = dict(player.get("projectedStats", player["stats"]))

        # Update live stats for display
        if player_type == "hitter":
            new_stats = extract_hitter_stats(s)
            merge_advanced_stats(new_stats, orig_stats, "hitter")
            player["stats"] = new_stats

            g = new_stats.get("G", 0)
            if g >= MIN_GAMES_HITTER:
                # Enough data — pace to full season and recalculate FPTS
                paced = pace_hitter_stats(new_stats)
                fpts = round(calc_hitter_fpts(paced), 1)
                fpts_g = round(fpts / FULL_GAMES, 3)
                player["fantasy"]["FPTS"] = fpts
                player["fantasy"]["FPTS_G"] = fpts_g
                player["statSource"] = "live"
            else:
                # Too few games — restore ZiPS FPTS
                player["fantasy"]["FPTS"]  = orig.get("fantasy", player["fantasy"])["FPTS"]
                player["fantasy"]["FPTS_G"] = orig.get("fantasy", player["fantasy"]).get("FPTS_G", 0)
                player["statSource"] = "live-partial"

        else:  # pitcher
            new_stats = extract_pitcher_stats(s)
            merge_advanced_stats(new_stats, orig_stats, "pitcher")
            player["stats"] = new_stats

            ip = new_stats.get("IP", 0.0)
            gs = new_stats.get("GS", 0)
            is_starter = gs >= 2  # has made at least 2 starts
            min_ip = MIN_IP_STARTER if is_starter else MIN_IP_RELIEVER

            if ip >= min_ip:
                paced = pace_pitcher_stats(new_stats, is_starter)
                fpts = round(calc_pitcher_fpts(paced), 1)
                ip_full = FULL_IP_STARTER if is_starter else FULL_IP_RELIEVER
                fpts_ip = round(fpts / ip_full, 3)
                player["fantasy"]["FPTS"] = fpts
                player["fantasy"]["FPTS_IP"] = fpts_ip
                player["statSource"] = "live"
            else:
                player["fantasy"]["FPTS"]   = orig.get("fantasy", player["fantasy"])["FPTS"]
                player["fantasy"]["FPTS_IP"] = orig.get("fantasy", player["fantasy"]).get("FPTS_IP", 0)
                player["statSource"] = "live-partial"

        # Update team from MLB API
        if row.get("team"):
            player["team"] = row["team"]

    return matched, len(players)


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def load_json(filename: str, data_dir: str = DATA_DIR) -> list:
    path = os.path.join(data_dir, filename)
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

    # 2. Build exact-name lookups
    hit_lookup = build_name_lookup(hit_rows)
    pit_lookup = build_name_lookup(pit_rows)

    # 3. Load existing site JSON + original ZiPS (source of truth)
    print("\nLoading existing JSON…")
    hitters  = load_json("hitters.json")
    pitchers = load_json("pitchers.json")

    # Load original ZiPS data for fallback FPTS
    orig_data_dir = os.path.normpath(os.path.join(ROOT, "..", "..", "data"))
    try:
        orig_hitters  = load_json("hitters.json",  orig_data_dir)
        orig_pitchers = load_json("pitchers.json", orig_data_dir)
        orig_h_lookup = {p["slug"]: p for p in orig_hitters}
        orig_p_lookup = {p["slug"]: p for p in orig_pitchers}
        print(f"  Loaded {len(orig_hitters)} ZiPS hitters, {len(orig_pitchers)} ZiPS pitchers as fallback")
    except Exception as e:
        print(f"  WARNING: could not load original ZiPS data ({e}); using current as fallback")
        orig_h_lookup = {p["slug"]: p for p in hitters}
        orig_p_lookup = {p["slug"]: p for p in pitchers}

    # 4. Update stats + recalculate FPTS where we have enough live data
    print("Updating hitters…")
    hm, ht = update_players(hitters, hit_lookup, "hitter", orig_h_lookup)
    live_h = sum(1 for p in hitters if p.get("statSource") == "live")
    print(f"  Matched {hm}/{ht} hitters | {live_h} have enough data for live ranking")

    print("Updating pitchers…")
    pm, pt = update_players(pitchers, pit_lookup, "pitcher", orig_p_lookup)
    live_p = sum(1 for p in pitchers if p.get("statSource") == "live")
    print(f"  Matched {pm}/{pt} pitchers | {live_p} have enough data for live ranking")

    # 5. Re-rank by updated FPTS
    print("\nRe-ranking…")
    hitters.sort(key=lambda p: p["fantasy"]["FPTS"], reverse=True)
    for i, p in enumerate(hitters):
        p["rank"] = i + 1

    pitchers.sort(key=lambda p: p["fantasy"]["FPTS"], reverse=True)
    for i, p in enumerate(pitchers):
        p["rank"] = i + 1

    all_players = hitters + pitchers
    all_players.sort(key=lambda p: p["fantasy"]["FPTS"], reverse=True)
    for i, p in enumerate(all_players):
        p["overallRank"] = i + 1

    # 6. Rebuild search index
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

    # 7. Save
    print("\nSaving…")
    save_json("hitters.json",     hitters)
    save_json("pitchers.json",    pitchers)
    save_json("all_players.json", all_players)
    save_json("search_index.json", search_index, indent=None)

    # 8. Summary
    top_h = hitters[:5]
    top_p = pitchers[:5]
    print(f"\nDone! Top hitters:")
    for p in top_h:
        src = p.get("statSource", "ZiPS")
        g = p["stats"].get("G", 0)
        print(f"  #{p['rank']} {p['name']} — FPTS: {p['fantasy']['FPTS']} [{src}, {g}G]")
    print(f"Top pitchers:")
    for p in top_p:
        src = p.get("statSource", "ZiPS")
        ip = p["stats"].get("IP", 0)
        print(f"  #{p['rank']} {p['name']} — FPTS: {p['fantasy']['FPTS']} [{src}, {ip}IP]")

    # Yordan check
    yordan = next((p for p in hitters if "yordan" in p["name"].lower()), None)
    if yordan:
        print(f"\nYordan Alvarez: #{yordan['rank']} hitter, #{yordan['overallRank']} overall | "
              f"FPTS={yordan['fantasy']['FPTS']} [{yordan.get('statSource')}] | "
              f"{yordan['stats'].get('G')}G {yordan['stats'].get('HR')}HR {yordan['stats'].get('AVG')} AVG")


if __name__ == "__main__":
    main()
