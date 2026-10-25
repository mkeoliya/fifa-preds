"""End-of-tournament awards + final summary for the Chepta Cup.

Reads docs/data/leaderboard.json (run scoring.py first) and data/actuals.json,
writes docs/data/awards.json for the frontend's Awards tab.

Awards (all data-driven except Spirit of the Game, which is set by hand in
data/actuals.json -> "spirit_of_the_game"):
  champion    highest total
  repreds     most RO32 re-draft points
  comeback    biggest climb from worst mid-tournament rank to final rank
  spirit      manual pick
  biggest_l   last place
  oracle      most exact hits: exact scorelines (group + KO) + individual awards
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LB = ROOT / "docs" / "data" / "leaderboard.json"
ACTUALS = ROOT / "data" / "actuals.json"
OUT = ROOT / "docs" / "data" / "awards.json"


def rank_history(players):
    """Rank of every player after each completed match (match points + static bonuses,
    same convention as the Points Race chart)."""
    n = max(len(p["timeline"]) for p in players)
    hist = {p["name"]: [] for p in players}
    for t in range(n):
        totals = {p["name"]: (p["timeline"][t]["cum"] if t < len(p["timeline"]) else 0)
                  + p["bonus_points"] + p["fixture_bonus"] + p["award_points"]
                  for p in players}
        for name, v in totals.items():
            hist[name].append(1 + sum(1 for x in totals.values() if x > v))
    return hist


def exact_counts(p):
    pm = p["per_match"]
    grp = sum(1 for k, v in pm.items() if k.startswith("GROUP|") and "exact" in v["detail"])
    ko = sum(1 for k, v in pm.items() if not k.startswith("GROUP|") and "exact" in v["detail"])
    aw = sum(1 for a in p["awards"].values() if a["hit"])
    return grp, ko, aw


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def main() -> int:
    lb = json.loads(LB.read_text(encoding="utf-8"))
    actuals = json.loads(ACTUALS.read_text(encoding="utf-8"))
    players = lb["players"]
    by_name = {p["name"]: p for p in players}
    hist = rank_history(players)
    matches = lb["matches"]
    dates = sorted(m["date"] for m in matches if m["completed"])

    awards = []

    # 1. Champion
    champ = players[0]
    second = players[1]
    awards.append({
        "id": "champion", "emoji": "🏆", "title": "Chepta Cup Champion",
        "winner": champ["name"],
        "stat": f"{champ['total']} pts",
        "blurb": f"Top of the table with {champ['total']} points, "
                 f"{champ['total'] - second['total']} clear of {second['name']}.",
    })

    # 2. Re-preds winner
    rp = sorted(players, key=lambda p: (-p["repred_points"], p["name"]))
    awards.append({
        "id": "repreds", "emoji": "🔁", "title": "Re-Preds King",
        "winner": rp[0]["name"],
        "stat": f"{rp[0]['repred_points']} KO pts",
        "blurb": f"Most points from the Round-of-32 re-draft: {rp[0]['repred_points']}, "
                 f"edging {rp[1]['name']} ({rp[1]['repred_points']}).",
    })

    # 3. Comeback: biggest climb from worst rank to final rank. The first group
    #    matchday (24 games) is ignored as noise; ties go to the deeper hole.
    skip = 24

    def climb(p):
        h = hist[p["name"]][skip:-1] or [p["rank"]]
        worst = max(h)
        return worst - p["rank"], worst, skip + h.index(worst)
    cb = max(players, key=lambda p: (climb(p)[0], climb(p)[1], -p["rank"]))
    gain, worst, wi = climb(cb)
    awards.append({
        "id": "comeback", "emoji": "📈", "title": "Comeback Story",
        "winner": cb["name"],
        "stat": f"{ordinal(worst)} → {ordinal(cb['rank'])}",
        "blurb": f"Sat {ordinal(worst)} on {dates[wi][:10]} and clawed up "
                 f"{gain} places to finish {ordinal(cb['rank'])}.",
    })

    # 4. Spirit of the game (manual)
    spirit = actuals.get("spirit_of_the_game") or {}
    if spirit.get("name") in by_name:
        awards.append({
            "id": "spirit", "emoji": "🤝", "title": "Spirit of the Game",
            "winner": spirit["name"], "stat": spirit.get("stat", "Fair play"),
            "blurb": spirit.get("reason", ""),
        })

    # 5. Biggest L
    last = players[-1]
    best_rank = min(hist[last["name"]])
    awards.append({
        "id": "biggest_l", "emoji": "🥄", "title": "Biggest L of the Comp",
        "winner": last["name"],
        "stat": f"{last['total']} pts",
        "blurb": f"Wooden spoon: {ordinal(last['rank'])} of {len(players)} with {last['total']} points"
                 + (f", despite sitting as high as {ordinal(best_rank)} along the way."
                    if best_rank <= 5 else "."),
    })

    # 6. Oracle
    def oracle_key(p):
        g, k, a = exact_counts(p)
        return g + k + a
    orc = max(players, key=lambda p: (oracle_key(p), -p["rank"]))
    g, k, a = exact_counts(orc)
    awards.append({
        "id": "oracle", "emoji": "🔮", "title": "The Oracle",
        "winner": orc["name"],
        "stat": f"{g + k + a} perfect calls",
        "blurb": f"{g} exact group scorelines, {k} exact knockout scorelines and "
                 f"{a} individual award{'s' if a != 1 else ''} nailed.",
    })

    final = next(m for m in matches if m["stage"] == "FINAL")
    fw = final["team1"] if final["score1"] > final["score2"] else final["team2"]
    standings = []
    for p in players:
        g, k, a = exact_counts(p)
        standings.append({
            "rank": p["rank"], "name": p["name"], "total": p["total"],
            "group": p["og_group_points"], "repred": p["repred_points"],
            "advancement": p["bonus_points"], "fixture": p["fixture_bonus"],
            "awards": p["award_points"], "champion_pick": p["champion"],
            "exact_scores": g + k, "award_hits": a,
        })

    out = {
        "final": {"team1": final["team1"], "team2": final["team2"],
                  "score1": final["score1"], "score2": final["score2"],
                  "winner": fw, "venue": final.get("venue")},
        "real_awards": actuals.get("awards", {}),
        "awards": awards,
        "standings": standings,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for a in awards:
        print(f"{a['emoji']} {a['title']}: {a['winner']} ({a['stat']}) - {a['blurb']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
