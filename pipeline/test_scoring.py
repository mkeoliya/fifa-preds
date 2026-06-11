"""Sanity-test scoring against a simulated results.json.

Simulates: match 1 (Mexico 2-1 South Africa) and a hypothetical completed
R32 with exactly Kutu's predicted field, then checks hand-computed points.
"""
import json
import pickle
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "results.json"

real = json.loads(RESULTS.read_text())
backup = RESULTS.with_suffix(".json.bak")
backup.write_text(json.dumps(real))

with open(ROOT / "data" / "picks" / "Kutu.pkl", "rb") as f:
    kutu = pickle.load(f)

sim = json.loads(json.dumps(real))
# Mexico 2-1 South Africa: Kutu predicted 2-1 -> 5 + 2 = 7
m0 = sim["matches"][0]
assert (m0["team1"], m0["team2"]) == ("Mexico", "South Africa")
m0.update(score1=2, score2=1, state="post", completed=True)
# Czech 1-1 Korea, Kutu predicted Korea 1 - Czech 1 -> 5 + 2 (oriented) = 7
m1 = sim["matches"][1]
assert {m1["team1"], m1["team2"]} == {"Rep. of Korea", "Czech Rep."}
m1.update(score1=1, score2=1, state="post", completed=True)
# Fill the real R32 with Kutu's predicted field -> 32 correct = +20 bonus,
# and make his R32 match 74 (Germany 2-0 Morocco, his pick) completed: +7.
kutu_r32 = [p for p in kutu.matches if p.stage == "R32"]
r32_slots = [m for m in sim["matches"] if m["stage"] == "R32"]
for slot, pick in zip(r32_slots, kutu_r32):
    slot.update(team1=pick.team1, team2=pick.team2)
g = next(m for m in r32_slots if {m["team1"], m["team2"]} == {"Germany", "Morocco"})
g.update(score1=2, score2=0, state="post", completed=True)
RESULTS.write_text(json.dumps(sim))

try:
    subprocess.run([sys.executable, str(ROOT / "pipeline" / "scoring.py")],
                   check=True)
    lb = json.loads((ROOT / "docs" / "data" / "leaderboard.json").read_text())
    k = next(p for p in lb["players"] if p["name"] == "Kutu")
    assert k["match_points"] == 21, k["match_points"]  # 7 + 7 + 7
    assert k["bonuses"]["R32"] == {"correct_so_far": 32, "complete": True,
                                   "points": 20}, k["bonuses"]["R32"]
    assert k["bonus_points"] == 20
    assert k["total"] == 41, k["total"]
    # every player has the 2 group matches + 1 R32 match in per_match
    for p in lb["players"]:
        assert len(p["per_match"]) == 3, (p["name"], len(p["per_match"]))
    # pens path: rerun with a drawn KO match decided on pens, per Kutu's pick
    pick = next(p for p in kutu_r32 if p.pen1 is not None)
    slot = next(m for m in r32_slots
                if {m["team1"], m["team2"]} == {pick.team1, pick.team2})
    slot.update(score1=pick.score1, score2=pick.score2,
                pen1=pick.pen1, pen2=pick.pen2, state="post", completed=True)
    RESULTS.write_text(json.dumps(sim))
    subprocess.run([sys.executable, str(ROOT / "pipeline" / "scoring.py")],
                   check=True)
    lb = json.loads((ROOT / "docs" / "data" / "leaderboard.json").read_text())
    k = next(p for p in lb["players"] if p["name"] == "Kutu")
    assert k["match_points"] == 21 + 5 + 2 + 3, k["match_points"]
    print("ALL SCORING TESTS PASSED")
finally:
    RESULTS.write_text(backup.read_text())
    backup.unlink()
    subprocess.run([sys.executable, str(ROOT / "pipeline" / "scoring.py")],
                   check=True)
