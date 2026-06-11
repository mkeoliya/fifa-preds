"""Compute the Chepta Cup leaderboard from picks + real results.

Rules (per Preds_Scoring, ambiguities settled by group decision):
  * Match points need the predicted matchup to equal the real one
    (order-insensitive): 5 correct FT result, +2 exact FT score,
    +3 exact penalty-shootout score.
  * Advancement bonuses per round for # of predicted teams that really
    made that round; awarded once the round's field is fully known.
  * Awards: Golden Ball 5, Boot/Glove/Young Player 3 each, from
    data/actuals.json (maintained manually once winners are announced).
Writes docs/data/leaderboard.json for the frontend.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import Prediction  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PICKS_DIR = ROOT / "data" / "picks"
RESULTS = ROOT / "data" / "results.json"
ACTUALS = ROOT / "data" / "actuals.json"
OUT = ROOT / "docs" / "data" / "leaderboard.json"

PTS_RESULT, PTS_EXACT, PTS_PENS = 5, 2, 3

# (stage, [(min_correct, bonus)] highest tier first, round size)
BONUS_TIERS = {
    "R32": [(32, 20), (27, 16), (22, 12), (18, 8)],
    "R16": [(16, 15), (12, 10), (8, 5)],
    "QF":  [(8, 5), (7, 4), (6, 3)],
    "SF":  [(4, 5)],
    "FINAL": [(2, 5)],
}
ROUND_SIZE = {"R32": 32, "R16": 16, "QF": 8, "SF": 4, "FINAL": 2}
AWARD_PTS = {"golden_ball": 5, "golden_boot": 3, "golden_glove": 3,
             "young_player": 3}


def result_of(s1, s2):
    if s1 is None or s2 is None:
        return None
    return "1" if s1 > s2 else "2" if s1 < s2 else "X"


def score_match(pick, actual):
    """Points a single pick earns against a completed actual match."""
    pts = 0
    detail = []
    # orient predicted scores to the actual team order
    if pick.team1 == actual["team1"]:
        ps1, ps2, pp1, pp2 = pick.score1, pick.score2, pick.pen1, pick.pen2
    else:
        ps1, ps2, pp1, pp2 = pick.score2, pick.score1, pick.pen2, pick.pen1
    if result_of(ps1, ps2) is not None and \
            result_of(ps1, ps2) == result_of(actual["score1"], actual["score2"]):
        pts += PTS_RESULT
        detail.append("result")
        if (ps1, ps2) == (actual["score1"], actual["score2"]):
            pts += PTS_EXACT
            detail.append("exact")
    if actual["pen1"] is not None and pp1 is not None and \
            (pp1, pp2) == (actual["pen1"], actual["pen2"]):
        pts += PTS_PENS
        detail.append("pens")
    return pts, detail


def bonus_for(stage, n_correct):
    for tier_min, bonus in BONUS_TIERS[stage]:
        if n_correct >= tier_min:
            return bonus
    return 0


def norm(name):
    """Loose normalization for award player-name comparison."""
    return "".join(ch for ch in (name or "").lower() if ch.isalpha())


def main() -> int:
    results = json.loads(RESULTS.read_text())
    actuals = json.loads(ACTUALS.read_text()) if ACTUALS.exists() else {}
    award_winners = actuals.get("awards", {})

    preds: dict[str, Prediction] = {}
    for f in sorted(PICKS_DIR.glob("*.pkl")):
        with open(f, "rb") as fh:
            p = pickle.load(fh)
        preds[p.name] = p

    # index actual matches; key on stage + unordered team pair
    actual_by_key = {}
    completed = []
    live = []
    for m in results["matches"]:
        if m["team1"] and m["team2"]:
            actual_by_key[(m["stage"], frozenset((m["team1"], m["team2"])))] = m
        if m["completed"]:
            completed.append(m)
        elif m["state"] == "in" and m["score1"] is not None:
            live.append(m)
    completed.sort(key=lambda m: m["date"])

    # real teams known per knockout round (for bonuses)
    actual_round_teams = {}
    for stage, size in ROUND_SIZE.items():
        teams = set()
        for m in results["matches"]:
            if m["stage"] == stage:
                teams.update(t for t in (m["team1"], m["team2"]) if t)
        actual_round_teams[stage] = {"teams": teams,
                                     "complete": len(teams) == size}

    players = []
    for name, pred in sorted(preds.items()):
        pick_by_key = {(p.stage, frozenset((p.team1, p.team2))): p
                       for p in pred.matches}
        match_pts = 0
        per_match = {}  # actual match date+teams key -> detail
        timeline = []
        cum = 0
        for m in completed:
            key = (m["stage"], frozenset((m["team1"], m["team2"])))
            pick = pick_by_key.get(key)
            pts, detail = score_match(pick, m) if pick else (0, [])
            match_pts += pts
            cum += pts
            mid = f"{m['stage']}|{m['team1']}|{m['team2']}"
            per_match[mid] = {
                "points": pts, "detail": detail,
                "pick": [pick.score1, pick.score2] if pick and
                        pick.team1 == m["team1"] else
                        [pick.score2, pick.score1] if pick else None,
                "pick_pens": [pick.pen1, pick.pen2] if pick and
                              pick.team1 == m["team1"] else
                              [pick.pen2, pick.pen1] if pick else None,
            }
            timeline.append({"date": m["date"], "cum": cum})

        # provisional points for in-progress matches ("if it ended now");
        # never added to official totals
        live_pts = 0
        per_match_live = {}
        for m in live:
            key = (m["stage"], frozenset((m["team1"], m["team2"])))
            pick = pick_by_key.get(key)
            pts, detail = score_match(pick, m) if pick else (0, [])
            live_pts += pts
            mid = f"{m['stage']}|{m['team1']}|{m['team2']}"
            per_match_live[mid] = {
                "points": pts, "detail": detail,
                "pick": [pick.score1, pick.score2] if pick and
                        pick.team1 == m["team1"] else
                        [pick.score2, pick.score1] if pick else None,
                "pick_pens": [pick.pen1, pick.pen2] if pick and
                              pick.team1 == m["team1"] else
                              [pick.pen2, pick.pen1] if pick else None,
            }

        bonus_pts = 0
        bonuses = {}
        for stage, info in actual_round_teams.items():
            predicted = pred.teams_in_stage(stage)
            n_correct = len(predicted & info["teams"])
            awarded = bonus_for(stage, n_correct) if info["complete"] else 0
            if info["complete"]:
                bonus_pts += awarded
            bonuses[stage] = {"correct_so_far": n_correct,
                              "complete": info["complete"],
                              "points": awarded}

        award_pts = 0
        awards_detail = {}
        for cat, pts in AWARD_PTS.items():
            picked = getattr(pred.awards, cat)
            actual_winner = award_winners.get(cat)
            hit = bool(actual_winner) and norm(picked) == norm(actual_winner)
            if hit:
                award_pts += pts
            awards_detail[cat] = {"pick": picked, "hit": hit}

        players.append({
            "name": name,
            "champion": pred.champion,
            "match_points": match_pts,
            "bonus_points": bonus_pts,
            "award_points": award_pts,
            "total": match_pts + bonus_pts + award_pts,
            "live_points": live_pts,
            "bonuses": bonuses,
            "awards": awards_detail,
            "per_match": per_match,
            "per_match_live": per_match_live,
            "timeline": timeline,
        })

    players.sort(key=lambda p: (-p["total"], p["name"]))
    for i, p in enumerate(players):
        p["rank"] = i + 1
        if i and p["total"] == players[i - 1]["total"]:
            p["rank"] = players[i - 1]["rank"]

    out = {
        "updated_at": results["fetched_at"],
        "players": players,
        "matches": results["matches"],
        "award_winners": award_winners,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False))
    picks_out = OUT.parent / "picks.json"
    picks_out.write_text(json.dumps(
        {name: p.to_dict() for name, p in preds.items()}, ensure_ascii=False))
    print(f"Leaderboard: " + ", ".join(
        f"{p['name']} {p['total']}" for p in players[:5]) + f" ... -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
