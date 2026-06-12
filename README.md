# 🏆 Chepta Cup — FIFA World Cup 2026 Prediction Leaderboard

Live site: **https://mkeoliya.github.io/fifa-preds/**

14 friends filled in the [Hermann Baum WC2026 Excel predictor](https://hermann-baum.de/excel/WorldCup/)
with full group-stage scores, knockout brackets, and award picks. This repo
parses those workbooks, pulls live results from ESPN's public scoreboard API
and market odds from Kalshi, scores everyone, and publishes a leaderboard via
GitHub Pages. A GitHub Action refreshes everything every 20 minutes.

## Scoring

| What | Points |
|---|---|
| Correct FT result (any stage) | 5 |
| Exact FT score (bonus) | +2 |
| Exact penalty-shootout score | +3 |
| Round-of-32 field (32 / 27–31 / 22–26 / 18–21 correct teams) | 20 / 16 / 12 / 8 |
| Round-of-16 field (16 / 12–15 / 8–11) | 15 / 10 / 5 |
| Quarter-final field (8 / 7 / 6) | 5 / 4 / 3 |
| Semi-final field (all 4) | 5 |
| Final pairing (both teams) | 5 |
| Golden Ball | 5 |
| Golden Boot / Golden Glove / Best Young Player | 3 each |

Knockout match points require the predicted matchup to be the real one
(order-insensitive); the advancement bonuses reward getting teams through.

## Layout

```
data/raw/        original prediction workbooks (read-only)
data/picks/      parsed Prediction pickles (one per player)
data/results.json    latest ESPN results snapshot
data/actuals.json    manually-filled award winners (end of tournament)
pipeline/
  models.py      dataclasses (Prediction, MatchPick, AwardPicks)
  parser.py      xlsx -> .pkl (run once; re-run if workbooks change)
  results.py     ESPN scoreboard -> data/results.json
  kalshi.py      Kalshi market odds -> docs/data/kalshi.json
  scoring.py     picks + results -> docs/data/leaderboard.json + picks.json
  test_scoring.py  scoring sanity tests against simulated results
docs/            static frontend served by GitHub Pages
pipeline/update.sh  refresh + push script, run by local cron every 20 min
```

## Operating notes

* **Award winners**: when announced after the final, fill `data/actuals.json`
  and the next cron run scores them (name matching is case/diacritic-loose).
* **Refresh**: a crontab entry on the host machine runs
  `pipeline/update.sh` every 20 minutes (GitHub's scheduled Actions proved
  too sporadic). It pulls, refreshes data, and pushes as mkeoliya via a
  dedicated SSH key; log at `data/update.log`. For a manual refresh, run
  the script directly. The script self-disables after 2026-07-25.
* Two known blank picks (Shaun match 61, Vui match 54) score 0 for those
  matches. Missing award picks default to Kutu's per group decision
  (JJ, Mayukh); Majank, Vui, and Snacc have custom overrides supplied via
  chat (see AWARD_OVERRIDES in parser.py).
