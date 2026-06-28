# 🏆 Chepta Cup — FIFA World Cup 2026 Prediction Leaderboard

Live site: **https://mkeoliya.github.io/fifa-preds/**

14 friends filled in the [Hermann Baum WC2026 Excel predictor](https://hermann-baum.de/excel/WorldCup/)
with full group-stage scores, knockout brackets, and award picks. This repo
parses those workbooks, pulls live results from ESPN's public scoreboard API
and market odds from Kalshi, scores everyone, and publishes a leaderboard via
GitHub Pages. A cron job on a remote machine refreshes everything every 20 minutes.

## Scoring

Total points = **Original bracket points** + **RO32 re-draft points**

### 1 — Original bracket (data/picks/)

| What | Points |
|---|---|
| Correct FT result — group stage | 5 |
| Exact FT score — group stage (bonus) | +2 |
| Exact fixture bonus — knockout (right two teams, right round) | +3 per match |
| Round-of-32 field (32 / 27–31 / 22–26 / 18–21 correct teams) | 20 / 16 / 12 / 8 |
| Round-of-16 field (16 / 12–15 / 8–11) | 15 / 10 / 5 |
| Quarter-final field (8 / 7 / 6) | 5 / 4 / 3 |
| Semi-final field — per correct team (max 4 × 3 = 12) | 3 per team |
| Final pairing — per correct team (max 2 × 3 = 6) | 3 per team |
| Golden Ball | 5 |
| Golden Boot / Golden Glove / Best Young Player | 3 each |

### 2 — RO32 re-draft (data/picks_r32/)

Before the first Round of 32 kick-off, everyone re-predicts the real knockout bracket.
Each knockout match is scored from the re-draft picks (not the original bracket).

| What | Points |
|---|---|
| Correct winner (team advancing) | 5 |
| Exact full-time score (incl. extra time) | +2 |
| Called it to go to penalties (and it did) | +2 |
| Exact FT score **and** exact penalty-shootout score combined | +5 |

Score/pen bonuses are only awarded if the re-draft called the right fixture (right two teams).
If the fixture is wrong but the predicted winner advanced, only the +5 winner bonus applies.

If no re-draft is submitted, the player's original bracket is used as their re-draft.
There are no team advancement or fixture match bonuses for re-draft picks.

## Layout

```
data/raw/            original prediction workbooks (read-only)
data/picks/          parsed Prediction pickles (one per player, OG bracket)
data/picks_r32/      re-draft Prediction pickles (one per player, knockout only)
data/results.json    latest ESPN results snapshot
data/actuals.json    manually-filled award winners (end of tournament)
pipeline/
  models.py          dataclasses (Prediction, MatchPick, AwardPicks)
  parser.py          xlsx -> .pkl (run once; re-run if workbooks change)
  results.py         ESPN scoreboard -> data/results.json
  kalshi.py          Kalshi market odds -> docs/data/kalshi.json
  scoring.py         picks + results -> docs/data/leaderboard.json + picks.json + picks_r32.json
  test_scoring.py    scoring sanity tests against simulated results
docs/                static frontend served by GitHub Pages
pipeline/update.sh   refresh + push script, run by local cron every 20 min
```

## Operating notes

* **Re-draft picks**: place parsed `.pkl` files in `data/picks_r32/` with the same
  filename convention as `data/picks/` (`Name.pkl` or `First_Last.pkl`). The cron
  job will pick them up on the next run and score them automatically.
* **Award winners**: when announced after the final, fill `data/actuals.json`
  and the next cron run scores them (name matching is case/diacritic-loose).
* **Refresh**: a crontab entry on the host machine runs
  `pipeline/update.sh` every 20 minutes. `pipeline/should_update.py` gates it to
  actual match windows, any live match in the last snapshot, and a daily odds sync.
  For a manual refresh run `FORCE=1 pipeline/update.sh`. The script self-disables
  after 2026-07-25.
