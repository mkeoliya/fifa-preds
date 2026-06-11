Steps for FIFA World Cup Prediction Leaderboard

1. Use existing environment: `conda activate ecg`

2. Set up a github repo, use `gh cli` to create it and push. Check if you have access.

3. Unzip the `/home/nvelingker/mkeoliya/fifa/Chepta Cup-20260611T165941Z-3-001.zip` file.

4. Read KutuPreds.xlsx; specifically read 3 sheets
  - `World Cup` defines the predicted scores for each match
  - `Awards` defines the predicted awards (Golden Boot, Golden Glove, etc.)
  - `Preds_Scoring` is the scoring system, which tells you how points are calculated.
  
5. Each file in `/home/nvelingker/mkeoliya/fifa/` is for a different person's predictions. Make a Python dataclass and functions to parse the files. Store them in a serialized way, in `.pkl` files. Don't modify the existing files; for each file check that we can load it correctly. Ensure that the format of the serialized files is such that it can be easily used to calculate the total points for each person.

6. Check that we can compute scores for each game. Set up an API call to an existing FIFA / other sports google API and use it to derive the scores of every match. 

7. Make a frontend to view the leaderboard and host it on GitHub pages if possible. Use whatever is most convenient; strealit, etc. all is good. Ensure the scores are updated in real-time via API calls. If that is too complicated, we can host it on this machine and expose a publically usable domain name (for free, e.g. like Gradio. but Gradio domains lapse in 1 week but we want one for ~1.5 months). 

8. Flesh out the entire plan and interview me about each step via the AskUserQuestion tool. Recommend some nice features if possible, we are doing this with friends. Perhaps we can integrate Kalshi probabilities for different match outcomes as well / make the visualization more flashy. 


Golden Ball (Best Player)	Pedri
Golden Boot (Top Scorer)	Erling Haaland
Golden Glove (Most Clean Sheets)	Jordan Pickford
Best Young Player (Under 21)	Lamine Yamal



- 15 mins update (GitHub pages)
- leaderboard 
- per player, evolution of their scores + bracket view of their predictions
- Kalshi predictions per game
- ESPN for live scores 