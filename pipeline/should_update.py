"""Gate for the cron refresh: exit 0 only when an update is worth running.

Worth running when now is:
  * inside a match window — kickoff-5min to kickoff+2h45m (group) or
    +4h (knockouts, for extra time + pens + settling), or
  * a match in the last snapshot is still marked live (covers delays
    and overruns past the nominal window), or
  * the daily 12:00 UTC sync slot (keeps Kalshi odds from going stale
    and self-heals anything a missed window left behind).
Kickoff times come from the last results.json snapshot; they are fixed
by FIFA, so a stale snapshot still gates correctly.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RES = Path(__file__).resolve().parent.parent / "data" / "results.json"

PRE = timedelta(minutes=5)
DURATION = {"GROUP": timedelta(hours=2, minutes=45)}
KO_DURATION = timedelta(hours=4)


def main() -> int:
    now = datetime.now(timezone.utc)
    matches = json.loads(RES.read_text())["matches"]
    for m in matches:
        if m["state"] == "in":
            print(f"live: {m['team1']} vs {m['team2']}")
            return 0
        ko = datetime.strptime(m["date"], "%Y-%m-%dT%H:%MZ").replace(
            tzinfo=timezone.utc)
        dur = DURATION.get(m["stage"], KO_DURATION)
        if ko - PRE <= now <= ko + dur and not m["completed"]:
            print(f"window: {m['team1'] or 'TBD'} vs {m['team2'] or 'TBD'} "
                  f"(ko {m['date']})")
            return 0
    if now.hour == 12 and now.minute < 5:
        print("daily sync")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
