"""Shared dataclasses for the Chepta Cup prediction leaderboard."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


STAGES = ["GROUP", "R32", "R16", "QF", "SF", "THIRD", "FINAL"]


@dataclass
class MatchPick:
    match_no: int           # FIFA official match number (1-104)
    stage: str              # one of STAGES
    team1: str              # canonical team name (template spelling)
    team2: str
    score1: Optional[int]   # predicted full-time score (after ET in knockouts)
    score2: Optional[int]
    pen1: Optional[int] = None  # predicted penalty shootout score, if any
    pen2: Optional[int] = None
    date: Optional[str] = None  # ISO date string from the sheet (local kickoff)
    venue: Optional[str] = None

    @property
    def result(self) -> Optional[str]:
        """'1' team1 wins, '2' team2 wins, 'X' draw (at full time)."""
        if self.score1 is None or self.score2 is None:
            return None
        if self.score1 > self.score2:
            return "1"
        if self.score1 < self.score2:
            return "2"
        return "X"

    @property
    def winner(self) -> Optional[str]:
        """Team advancing from a knockout match (uses pens on a draw)."""
        r = self.result
        if r == "1":
            return self.team1
        if r == "2":
            return self.team2
        if r == "X" and self.pen1 is not None and self.pen2 is not None:
            return self.team1 if self.pen1 > self.pen2 else self.team2
        return None


@dataclass
class AwardPicks:
    golden_ball: Optional[str] = None
    golden_boot: Optional[str] = None
    golden_glove: Optional[str] = None
    young_player: Optional[str] = None


@dataclass
class Prediction:
    name: str               # display name of the player
    source_file: str
    matches: list[MatchPick] = field(default_factory=list)
    awards: AwardPicks = field(default_factory=AwardPicks)
    champion: Optional[str] = None

    def teams_in_stage(self, stage: str) -> set[str]:
        """Set of teams this player predicted to appear in the given stage."""
        teams: set[str] = set()
        for m in self.matches:
            if m.stage == stage:
                teams.add(m.team1)
                teams.add(m.team2)
        return teams

    def to_dict(self) -> dict:
        return asdict(self)
