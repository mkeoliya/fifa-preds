"""Fetch Kalshi market probabilities for WC2026.

Keyless public endpoints:
  * KXWCGAME series  -> 1X2 winner markets per match
  * KXMENWORLDCUP-26 -> tournament winner markets
Writes docs/data/kalshi.json. Prices are last-trade dollars (= implied prob);
falls back to bid/ask mid when a market hasn't traded.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from results import TEAM_ALIASES, KNOWN_TEAMS  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "kalshi.json"
BASE = "https://api.elections.kalshi.com/trade-api/v2"

KALSHI_ALIASES = dict(TEAM_ALIASES)
KALSHI_ALIASES.update({
    "Turkiye": "Turkey",
    "Korea Republic": "Rep. of Korea",
    "South Korea": "Rep. of Korea",
    "Bosnia": "Bosnia/Herzeg.",
    "Czech Republic": "Czech Rep.",
})


def get(path: str, **params) -> dict:
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def prob(m: dict):
    last = m.get("last_price_dollars")
    if last and float(last) > 0:
        return round(float(last), 4)
    bid, ask = m.get("yes_bid_dollars"), m.get("yes_ask_dollars")
    if bid and ask and float(ask) > 0:
        return round((float(bid) + float(ask)) / 2, 4)
    return None


def team_name(raw: str) -> str:
    return KALSHI_ALIASES.get(raw, raw)


def fetch_match_markets() -> dict:
    """event ticker -> match prob entry."""
    markets, cursor = [], None
    while True:
        params = {"series_ticker": "KXWCGAME", "status": "open", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        d = get("markets", **params)
        markets.extend(d.get("markets", []))
        cursor = d.get("cursor")
        if not cursor:
            break

    events: dict[str, dict] = {}
    for m in markets:
        ev = m["event_ticker"]  # e.g. KXWCGAME-26JUN11MEXRSA
        entry = events.setdefault(ev, {"teams": {}, "tie": None})
        sub = m.get("yes_sub_title") or ""
        p = prob(m)
        if sub.lower() == "tie":
            entry["tie"] = p
        elif sub:
            entry["teams"][team_name(sub)] = p

    out = {}
    for ev, entry in events.items():
        names = list(entry["teams"])
        unknown = [n for n in names if n not in KNOWN_TEAMS]
        if unknown:
            print(f"  WARN: unmapped Kalshi team(s) {unknown} in {ev}")
        if len(names) == 2:
            out["|".join(sorted(names))] = {
                "probs": entry["teams"], "tie": entry["tie"], "event": ev}
    return out


def fetch_winner_markets() -> list[dict]:
    d = get("events", series_ticker="KXMENWORLDCUP", limit=10,
            with_nested_markets="true")
    rows = []
    for e in d.get("events", []):
        for m in e.get("markets", []):
            p = prob(m)
            sub = m.get("yes_sub_title")
            if sub and p is not None:
                rows.append({"team": team_name(sub), "prob": p})
    rows.sort(key=lambda r: -r["prob"])
    return rows


def main() -> int:
    try:
        matches = fetch_match_markets()
        winner = fetch_winner_markets()
    except Exception as e:
        # Kalshi is a nice-to-have: keep the previous snapshot on failure.
        print(f"Kalshi fetch failed ({e}); keeping previous snapshot")
        return 0
    out = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matches": matches,
        "winner": winner,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False))
    print(f"Kalshi: {len(matches)} match markets, "
          f"{len(winner)} winner markets -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
