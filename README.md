# 🏆 Chepta Cup — FIFA World Cup 2026 Prediction Leaderboard

Live site: **https://nvelingker.github.io/fifa-preds/**

13 friends filled in the [Hermann Baum WC2026 Excel predictor](https://hermann-baum.de/excel/WorldCup/)
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
.github/workflows/update.yml  20-min refresh cron
```

## Operating notes

* **Award winners**: when announced after the final, fill `data/actuals.json`
  and the next cron run scores them (name matching is case/diacritic-loose).
* **Manual refresh**: trigger the *Update leaderboard* workflow from the
  Actions tab, or run the three pipeline scripts locally and push.
* Two known blank picks (Shaun match 61, Vui match 54) score 0 for those
  matches. Missing award picks default to Kutu's per group decision
  (JJ, Mayukh, Snacc, Vui) with a custom override for Majank (see parser.py).
