"""Compute the Chepta Cup leaderboard from picks + real results.

Two scoring stacks add together:

1) ORIGINAL bracket (data/picks/)
   - Group stage: +5 correct result, +2 exact score
   - Team advancement bonus per round (how many of your picks really made it)
   - Exact fixture bonus: +3 for each knockout matchup your OG bracket called correctly
   - Awards: Golden Ball +5; Boot/Glove/Young +3 each

2) RO32 re-draft (data/picks_r32/)
   - Everyone re-predicts the real knockout bracket before the first RO32 kick-off
   - Per match: +5 correct winner, +2 exact FT score, +2 called pens, +5 exact FT+pens
   - Score/pen bonuses only awarded if you called the right fixture (right two teams)
   - Winner-only (+5) awarded even for wrong-fixture picks if you named the real winner
   - Falls back to OG bracket if no re-draft file exists for a player

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
PICKS_R32_DIR = ROOT / "data" / "picks_r32"
RESULTS = ROOT / "data" / "results.json"
ACTUALS = ROOT / "data" / "actuals.json"
OUT = ROOT / "docs" / "data" / "leaderboard.json"

PTS_RESULT, PTS_EXACT, PTS_PENS_OG = 5, 2, 3

# Team advancement bonus tiers (OG bracket only)
BONUS_TIERS = {
    "R32": [(32, 20), (27, 16), (22, 12), (18, 8)],
    "R16": [(16, 15), (12, 10), (8, 5)],
    "QF":  [(8, 5), (7, 4), (6, 3)],
    # SF and FINAL are per-team (3 pts each)
}
PTS_PER_TEAM_LATE = 3  # SF (4 teams max 12) and FINAL (2 teams max 6)
ROUND_SIZE = {"R32": 32, "R16": 16, "QF": 8, "SF": 4, "FINAL": 2}
AWARD_PTS = {"golden_ball": 5, "golden_boot": 3, "golden_glove": 3,
             "young_player": 3}

# Re-draft scoring constants
REPRED_PTS_WINNER = 5
REPRED_PTS_EXACT = 2
REPRED_PTS_PENS_CALL = 2
REPRED_PTS_PENS_EXACT = 5

# Player-specific zero overrides: these (stage, frozenset_of_teams) score 0 regardless
ZERO_OVERRIDES: dict[str, set] = {
    "Majank": {("R32", frozenset({"Canada", "South Africa"}))},
}


def norm_team(name):
    """Fix double-encoded UTF-8 team names (e.g. ESPN returns Curaçao as \\xc3\\xa7)."""
    if not name:
        return name
    try:
        return name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def result_of(s1, s2):
    if s1 is None or s2 is None:
        return None
    return "1" if s1 > s2 else "2" if s1 < s2 else "X"


def actual_winner_team(m):
    """Return the name of the team that won match m, or None if incomplete."""
    s1, s2 = m.get("score1"), m.get("score2")
    p1, p2 = m.get("pen1"), m.get("pen2")
    if s1 is None or s2 is None:
        return None
    if s1 > s2:
        return m["team1"]
    if s2 > s1:
        return m["team2"]
    if p1 is not None and p2 is not None:
        return m["team1"] if p1 > p2 else m["team2"]
    return None


def predicted_winner_team(pick):
    """Return the name of the team the pick predicts to win, or None."""
    s1, s2 = pick.score1, pick.score2
    p1, p2 = pick.pen1, pick.pen2
    if s1 is None or s2 is None:
        return None
    if s1 > s2:
        return pick.team1
    if s2 > s1:
        return pick.team2
    if p1 is not None and p2 is not None:
        return pick.team1 if p1 > p2 else pick.team2
    return None


def score_og_match(pick, actual):
    """Score an OG pick against a completed group-stage match."""
    pts = 0
    detail = []
    if norm_team(pick.team1) == norm_team(actual["team1"]):
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
        pts += PTS_PENS_OG
        detail.append("pens")
    return pts, detail


def score_repred_match(pick, actual):
    """Score a re-draft pick against a completed knockout match.

    Full bonus (score/pens) only if pick teams == actual teams.
    Winner bonus always applies if predicted winner == actual winner.
    """
    pts = 0
    detail = []

    teams_match = (frozenset((norm_team(pick.team1), norm_team(pick.team2))) ==
                   frozenset((norm_team(actual["team1"]), norm_team(actual["team2"]))))
    a_winner = actual_winner_team(actual)
    p_winner = predicted_winner_team(pick)

    if p_winner and p_winner == a_winner:
        pts += REPRED_PTS_WINNER
        detail.append("winner")

    if teams_match:
        # Orient pick scores to actual team order
        if norm_team(pick.team1) == norm_team(actual["team1"]):
            ps1, ps2, pp1, pp2 = pick.score1, pick.score2, pick.pen1, pick.pen2
        else:
            ps1, ps2, pp1, pp2 = pick.score2, pick.score1, pick.pen2, pick.pen1

        a1, a2 = actual["score1"], actual["score2"]
        ap1, ap2 = actual.get("pen1"), actual.get("pen2")

        if ps1 is not None and ps2 is not None:
            if (ps1, ps2) == (a1, a2):
                pts += REPRED_PTS_EXACT
                detail.append("exact")
            # +2 for calling it to pens (pick is a draw AND match went to pens)
            if ps1 == ps2 and ap1 is not None:
                pts += REPRED_PTS_PENS_CALL
                detail.append("pens_call")
            # +5 for exact FT score AND exact pen score combined
            if ap1 is not None and pp1 is not None:
                if (ps1, ps2) == (a1, a2) and (pp1, pp2) == (ap1, ap2):
                    pts += REPRED_PTS_PENS_EXACT
                    detail.append("pens_exact")

    return pts, detail


def bonus_for(stage, n_correct):
    if stage in ("SF", "FINAL"):
        return n_correct * PTS_PER_TEAM_LATE
    for tier_min, bonus in BONUS_TIERS[stage]:
        if n_correct >= tier_min:
            return bonus
    return 0


def norm(name):
    return "".join(ch for ch in (name or "").lower() if ch.isalpha())


def main() -> int:
    results = json.loads(RESULTS.read_text())
    actuals = json.loads(ACTUALS.read_text()) if ACTUALS.exists() else {}
    award_winners = actuals.get("awards", {})

    # Load OG picks
    og_preds: dict[str, Prediction] = {}
    for f in sorted(PICKS_DIR.glob("*.pkl")):
        with open(f, "rb") as fh:
            p = pickle.load(fh)
        og_preds[p.name] = p

    # Load re-draft picks; fall back to OG if not submitted
    repred_preds: dict[str, Prediction] = {}
    for name, og in og_preds.items():
        fname = PICKS_R32_DIR / f"{name.replace(' ', '_')}.pkl"
        if fname.exists():
            with open(fname, "rb") as fh:
                repred_preds[name] = pickle.load(fh)
        else:
            repred_preds[name] = og  # fallback

    # Index actual matches
    actual_by_key: dict = {}  # (stage, frozenset) -> match
    completed_group = []
    completed_ko = []
    live = []
    for m in results["matches"]:
        if m["team1"] and m["team2"]:
            actual_by_key[(m["stage"], frozenset((norm_team(m["team1"]), norm_team(m["team2"]))))] = m
        if m["completed"]:
            if m["stage"] == "GROUP":
                completed_group.append(m)
            else:
                completed_ko.append(m)
        elif m["state"] == "in" and m["score1"] is not None:
            live.append(m)
    completed_group.sort(key=lambda m: m["date"])
    completed_ko.sort(key=lambda m: m["date"])

    # Real teams known per knockout round (for advancement bonuses)
    actual_round_teams: dict = {}
    for stage, size in ROUND_SIZE.items():
        teams: set = set()
        for m in results["matches"]:
            if m["stage"] == stage:
                teams.update(t for t in (m["team1"], m["team2"]) if t)
        actual_round_teams[stage] = {"teams": teams,
                                     "complete": len(teams) == size}

    players = []
    for name, og_pred in sorted(og_preds.items()):
        repred = repred_preds[name]
        using_og_fallback = repred is og_pred

        # --- group stage scoring (OG picks) ---
        og_pick_by_key = {(p.stage, frozenset((norm_team(p.team1), norm_team(p.team2)))): p
                          for p in og_pred.matches}
        group_pts = 0
        per_match: dict = {}
        timeline = []
        cum = 0
        for m in completed_group:
            key = ("GROUP", frozenset((norm_team(m["team1"]), norm_team(m["team2"]))))
            pick = og_pick_by_key.get(key)
            pts, detail = score_og_match(pick, m) if pick else (0, [])
            group_pts += pts
            cum += pts
            mid = f"GROUP|{m['team1']}|{m['team2']}"
            per_match[mid] = {
                "points": pts, "detail": detail,
                "pick": [pick.score1, pick.score2] if pick and
                        norm_team(pick.team1) == norm_team(m["team1"]) else
                        [pick.score2, pick.score1] if pick else None,
                "pick_pens": [pick.pen1, pick.pen2] if pick and
                              norm_team(pick.team1) == norm_team(m["team1"]) else
                              [pick.pen2, pick.pen1] if pick else None,
            }
            timeline.append({"date": m["date"], "cum": cum})

        # --- knockout scoring (re-draft picks) ---
        repred_ko_picks = [p for p in repred.matches if p.stage != "GROUP"]
        repred_by_key = {(p.stage, frozenset((norm_team(p.team1), norm_team(p.team2)))): p
                         for p in repred_ko_picks}

        ko_pts = 0
        used_repred_picks: set = set()  # ids of picks consumed by exact-fixture match

        for m in completed_ko:
            key = (m["stage"], frozenset((norm_team(m["team1"]), norm_team(m["team2"]))))
            pick = repred_by_key.get(key)
            if pick is not None:
                pts, detail = score_repred_match(pick, m)
                used_repred_picks.add(id(pick))
            else:
                # wrong fixture — check if any unmatched pick in this stage
                # had the right winner
                pts, detail = 0, []
                a_winner = actual_winner_team(m)
                for rp in repred_ko_picks:
                    if id(rp) in used_repred_picks:
                        continue
                    if rp.stage != m["stage"]:
                        continue
                    if predicted_winner_team(rp) == a_winner:
                        pts = REPRED_PTS_WINNER
                        detail = ["winner"]
                        used_repred_picks.add(id(rp))
                        break

            # Apply player-specific zero overrides
            zero_key = (m["stage"], frozenset({norm_team(m["team1"]), norm_team(m["team2"])}))
            if zero_key in ZERO_OVERRIDES.get(name, set()):
                pts, detail = 0, []

            ko_pts += pts
            cum += pts
            mid = f"{m['stage']}|{m['team1']}|{m['team2']}"
            per_match[mid] = {
                "points": pts, "detail": detail,
                "pick": None,  # filled below if pick exists
                "pick_pens": None,
            }
            if pick is not None:
                per_match[mid]["pick"] = (
                    [pick.score1, pick.score2] if norm_team(pick.team1) == norm_team(m["team1"])
                    else [pick.score2, pick.score1]
                )
                per_match[mid]["pick_pens"] = (
                    [pick.pen1, pick.pen2] if norm_team(pick.team1) == norm_team(m["team1"])
                    else [pick.pen2, pick.pen1]
                )
            timeline.append({"date": m["date"], "cum": cum})

        # --- live provisional points (re-draft picks) ---
        live_pts = 0
        per_match_live: dict = {}
        used_live: set = set()
        for m in live:
            key = (m["stage"], frozenset((norm_team(m["team1"]), norm_team(m["team2"]))))
            pick = repred_by_key.get(key) if m["stage"] != "GROUP" else og_pick_by_key.get(key)
            if pick is not None and m["stage"] == "GROUP":
                pts, detail = score_og_match(pick, m)
            elif pick is not None:
                pts, detail = score_repred_match(pick, m)
                used_live.add(id(pick))
            else:
                pts, detail = 0, []
            live_pts += pts
            mid = f"{m['stage']}|{m['team1']}|{m['team2']}"
            per_match_live[mid] = {
                "points": pts, "detail": detail,
                "pick": (
                    [pick.score1, pick.score2] if pick and norm_team(pick.team1) == norm_team(m["team1"])
                    else [pick.score2, pick.score1] if pick else None
                ),
                "pick_pens": (
                    [pick.pen1, pick.pen2] if pick and norm_team(pick.team1) == norm_team(m["team1"])
                    else [pick.pen2, pick.pen1] if pick else None
                ),
            }

        # --- exact fixture bonus (OG knockout picks vs real fixtures) ---
        fixture_bonus = 0
        fixture_bonuses: dict = {}
        for pick in og_pred.matches:
            if pick.stage == "GROUP":
                continue
            key = (pick.stage, frozenset((norm_team(pick.team1), norm_team(pick.team2))))
            hit = key in actual_by_key
            bonus = 3 if hit else 0
            fixture_bonus += bonus
            mid = f"{pick.stage}|{pick.team1}|{pick.team2}"
            fixture_bonuses[mid] = {"hit": hit, "points": bonus,
                                    "stage": pick.stage,
                                    "team1": pick.team1, "team2": pick.team2}

        # --- team advancement bonuses (OG bracket) ---
        bonus_pts = 0
        bonuses: dict = {}
        for stage, info in actual_round_teams.items():
            predicted = og_pred.teams_in_stage(stage)
            n_correct = len(predicted & info["teams"])
            awarded = bonus_for(stage, n_correct) if info["complete"] else 0
            if info["complete"]:
                bonus_pts += awarded
            bonuses[stage] = {"correct_so_far": n_correct,
                              "complete": info["complete"],
                              "points": awarded,
                              "max": (ROUND_SIZE[stage] * PTS_PER_TEAM_LATE
                                      if stage in ("SF", "FINAL") else None)}

        # --- award points (OG bracket) ---
        award_pts = 0
        awards_detail: dict = {}
        for cat, pts in AWARD_PTS.items():
            picked = getattr(og_pred.awards, cat)
            actual_winner = award_winners.get(cat)
            hit = bool(actual_winner) and norm(picked) == norm(actual_winner)
            if hit:
                award_pts += pts
            awards_detail[cat] = {"pick": picked, "hit": hit}

        match_pts = group_pts + ko_pts
        total = match_pts + fixture_bonus + bonus_pts + award_pts

        players.append({
            "name": name,
            "champion": og_pred.champion,
            "match_points": match_pts,
            "og_group_points": group_pts,
            "repred_points": ko_pts,
            "repred_fallback": using_og_fallback,
            "fixture_bonus": fixture_bonus,
            "bonus_points": bonus_pts,
            "award_points": award_pts,
            "total": total,
            "live_points": live_pts,
            "bonuses": bonuses,
            "fixture_bonuses": fixture_bonuses,
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
        {name: p.to_dict() for name, p in og_preds.items()}, ensure_ascii=False))
    # also write re-draft picks for the frontend
    repred_out = OUT.parent / "picks_r32.json"
    repred_out.write_text(json.dumps(
        {name: p.to_dict() for name, p in repred_preds.items()}, ensure_ascii=False))
    print(f"Leaderboard: " + ", ".join(
        f"{p['name']} {p['total']}" for p in players[:5]) + f" ... -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
