"""
repair_rankings.py — Restore correct ZiPS rankings in site/data/

The first GitHub Actions run (af3a390) corrupted fantasy.FPTS, rank, and
overallRank by recalculating them using a bad pacing formula + last-name
fallback matching. This script restores the correct values from the original
source data in fantasy-tool/data/*.json while keeping the live stats that
were fetched from the MLB API.
"""

import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_DATA = os.path.normpath(os.path.join(ROOT, "..", "data"))
ORIG_DATA = os.path.normpath(os.path.join(ROOT, "..", "..", "data"))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data, indent=2):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
    kb = os.path.getsize(path) // 1024
    print(f"  Wrote {os.path.basename(path)} ({len(data)} records, {kb} KB)")


def repair(site_players, orig_lookup, player_type):
    fixed = 0
    for p in site_players:
        slug = p["slug"]
        orig = orig_lookup.get(slug)
        if orig is None:
            print(f"  WARNING: no original for {p['name']} ({slug})")
            continue

        # Restore authoritative ZiPS values
        p["fantasy"] = orig["fantasy"]
        p["rank"] = orig["rank"]
        p["overallRank"] = orig["overallRank"]

        # Fix projectedStats to be the true ZiPS projected stats
        # (not whatever corrupted values were saved on first run)
        p["projectedStats"] = orig["stats"]

        fixed += 1
    return fixed


def main():
    print("=== Repairing rankings from original ZiPS data ===\n")

    # Load originals (source of truth)
    orig_hitters  = load(os.path.join(ORIG_DATA, "hitters.json"))
    orig_pitchers = load(os.path.join(ORIG_DATA, "pitchers.json"))

    orig_h_lookup = {p["slug"]: p for p in orig_hitters}
    orig_p_lookup = {p["slug"]: p for p in orig_pitchers}

    print(f"Original source: {len(orig_hitters)} hitters, {len(orig_pitchers)} pitchers")

    # Load site data (has live stats + corrupted rankings)
    site_hitters  = load(os.path.join(SITE_DATA, "hitters.json"))
    site_pitchers = load(os.path.join(SITE_DATA, "pitchers.json"))

    print(f"Site data:       {len(site_hitters)} hitters, {len(site_pitchers)} pitchers\n")

    # Repair
    print("Repairing hitters...")
    hf = repair(site_hitters, orig_h_lookup, "hitter")
    print(f"  Fixed {hf}/{len(site_hitters)} hitters")

    print("Repairing pitchers...")
    pf = repair(site_pitchers, orig_p_lookup, "pitcher")
    print(f"  Fixed {pf}/{len(site_pitchers)} pitchers\n")

    # Rebuild all_players sorted by overallRank
    all_players = site_hitters + site_pitchers
    all_players.sort(key=lambda p: p.get("overallRank", 9999))

    # Rebuild search index
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

    # Save
    print("Saving...")
    save(os.path.join(SITE_DATA, "hitters.json"),      site_hitters)
    save(os.path.join(SITE_DATA, "pitchers.json"),     site_pitchers)
    save(os.path.join(SITE_DATA, "all_players.json"),  all_players)
    with open(os.path.join(SITE_DATA, "search_index.json"), "w", encoding="utf-8") as f:
        json.dump(search_index, f)
    kb = os.path.getsize(os.path.join(SITE_DATA, "search_index.json")) // 1024
    print(f"  Wrote search_index.json ({len(search_index)} records, {kb} KB)")

    # Spot-check
    print("\n=== Spot-check: Top 10 overall ===")
    for p in all_players[:10]:
        print(f"  #{p['overallRank']} {p['name']} ({p.get('teamAbbr','?')}, {p['pos']}) — FPTS: {p['fantasy']['FPTS']}")

    print("\n=== Top 5 pitchers ===")
    top_p = sorted(site_pitchers, key=lambda p: p.get("rank", 9999))[:5]
    for p in top_p:
        print(f"  #{p['rank']} {p['name']} — FPTS: {p['fantasy']['FPTS']} | ERA: {p['stats'].get('ERA','?')}")

    print("\n=== Garrett Crochet ===")
    crochet = next((p for p in site_pitchers if "crochet" in p["name"].lower()), None)
    if crochet:
        print(f"  Rank: #{crochet['rank']} | Overall: #{crochet['overallRank']} | FPTS: {crochet['fantasy']['FPTS']}")
        print(f"  Live ERA: {crochet['stats'].get('ERA','?')} | IP: {crochet['stats'].get('IP','?')}")

    print("\nDone! Push this to GitHub to deploy.")


if __name__ == "__main__":
    main()
