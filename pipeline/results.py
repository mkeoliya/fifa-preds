"""Fetch real WC2026 match results from ESPN's public scoreboard API.

Keyless endpoint; one call covers the whole tournament window. Output is
data/results.json with team names normalized to the template's spellings.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "results.json"
URL = ("https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/"
       "scoreboard?dates=20260611-20260719&limit=300")

# ESPN displayName -> template name. Identity for names that already match.
TEAM_ALIASES = {
    "South Korea": "Rep. of Korea",
    "Czechia": "Czech Rep.",
    "Czech Republic": "Czech Rep.",
    "Bosnia-Herzegovina": "Bosnia/Herzeg.",
    "Bosnia and Herzegovina": "Bosnia/Herzeg.",
    "Türkiye": "Turkey",
    "United States": "USA",
    "USA": "USA",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Iran": "IR Iran",
    "Cape Verde Islands": "Cape Verde",
    "Cabo Verde": "Cape Verde",
    "Curacao": "Curaçao",
    "Democratic Republic of the Congo": "DR Congo",
    "Congo DR": "DR Congo",
}

# Template team vocabulary, used to flag unmapped ESPN names.
KNOWN_TEAMS = {
    "Mexico", "Czech Rep.", "Rep. of Korea", "South Africa", "Switzerland",
    "Canada", "Qatar", "Bosnia/Herzeg.", "Brazil", "Scotland", "Morocco",
    "Haiti", "Turkey", "USA", "Australia", "Paraguay", "Germany",
    "Ivory Coast", "Ecuador", "Curaçao", "Netherlands", "Sweden", "Japan",
    "Tunisia", "Belgium", "Egypt", "IR Iran", "New Zealand", "Spain",
    "Uruguay", "Saudi Arabia", "Cape Verde", "France", "Norway", "Senegal",
    "Iraq", "Argentina", "Austria", "Algeria", "Jordan", "Portugal",
    "Colombia", "DR Congo", "Uzbekistan", "England", "Croatia", "Ghana",
    "Panama",
}

# Stage boundaries as UTC instants (rest days give comfortable margins;
# cutoffs sit after the last possible late-night kickoff of each round).
STAGE_CUTOFFS = [
    ("GROUP", "2026-06-28T06:00"),
    ("R32",   "2026-07-04T06:00"),
    ("R16",   "2026-07-08T12:00"),
    ("QF",    "2026-07-13T00:00"),
    ("SF",    "2026-07-17T00:00"),
    ("THIRD", "2026-07-19T06:00"),
    ("FINAL", "2026-07-31T00:00"),
]
EXPECTED_COUNTS = {"GROUP": 72, "R32": 16, "R16": 8, "QF": 4, "SF": 2,
                   "THIRD": 1, "FINAL": 1}


def normalize_team(espn_name: str) -> str:
    return TEAM_ALIASES.get(espn_name, espn_name)


def stage_for(date_utc: datetime) -> str:
    for stage, cutoff in STAGE_CUTOFFS:
        if date_utc < datetime.fromisoformat(cutoff).replace(tzinfo=timezone.utc):
            return stage
    return "FINAL"


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fetch() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> int:
    data = fetch()
    matches = []
    warnings = []
    for e in sorted(data["events"], key=lambda e: e["date"]):
        comp = e["competitions"][0]
        date = datetime.strptime(e["date"], "%Y-%m-%dT%H:%MZ").replace(
            tzinfo=timezone.utc)
        home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
        away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
        state = e["status"]["type"]["state"]  # pre | in | post
        names = {}
        for side, c in (("1", home), ("2", away)):
            raw = c["team"]["displayName"]
            name = normalize_team(raw)
            # Placeholder fixtures ("Group A Winner") aren't real teams yet.
            if name not in KNOWN_TEAMS:
                if state != "pre":
                    warnings.append(f"unknown team name {raw!r} in {e['name']}")
                name = None
            names[side] = name
        started = state in ("in", "post")
        matches.append({
            "date": e["date"],
            "stage": stage_for(date),
            "team1": names["1"],
            "team2": names["2"],
            "score1": _int(home.get("score")) if started else None,
            "score2": _int(away.get("score")) if started else None,
            "pen1": _int(home.get("shootoutScore")),
            "pen2": _int(away.get("shootoutScore")),
            "state": state,
            "completed": bool(e["status"]["type"].get("completed")),
            "venue": (e.get("venue") or {}).get("displayName"),
        })

    counts = {}
    for m in matches:
        counts[m["stage"]] = counts.get(m["stage"], 0) + 1
    if counts != EXPECTED_COUNTS:
        warnings.append(f"stage counts {counts} != expected {EXPECTED_COUNTS}")

    out = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matches": matches,
        "warnings": warnings,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    done = sum(1 for m in matches if m["completed"])
    live = sum(1 for m in matches if m["state"] == "in")
    print(f"{len(matches)} matches ({done} final, {live} live) -> {OUT}")
    for w in warnings:
        print(f"  WARN: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
