# Promo Finder

Reads microdrama screenplay `.txt` files and finds 20-60s promo clips (hook at the start, cliffhanger at the end).

## How it works
1. `parse.py` turns each screenplay into a list of timed events (camera, action, dialogue). Timestamps come straight from the file.
2. `main.py` sends the transcript of 2 episodes at a time to an LLM (so promos can join episodes). The LLM returns start/end times, the hook, the cliffhanger, one line of why, and scores for hook, cliffhanger and standalone.
3. Code (not the LLM) then checks and fixes the answer:
   - snaps times to real line/shot boundaries so clips never cut mid-line
   - rejects clips that are not 20-60s or are out of story order
   - flags `weak_open` if nothing is said or done in the first 3s
   - score = 0.4 hook + 0.4 cliffhanger + 0.2 standalone (-1 if weak open)
   - removes overlapping duplicates, keeps max 3 per episode
4. Promos are ranked by score and saved to `outputs/` (`promos.csv`, `promos.json`, `report.md`).

`heuristic.py` is a no-LLM baseline (keywords + "ends near episode end"). Use `--no-llm` to run it, and compare it with the LLM to see where each fails.

Answers are cached in `cache/`, so re-runs are free and fast.

## Run
```
pip install -r requirements.txt
# put all episode .txt files in ./episodes

# Gemini free tier (default)
export LLM_API_KEY=your_key
python main.py --input episodes --out outputs

# swap model / provider
export LLM_MODEL=gpt-4o-mini LLM_BASE_URL=https://api.openai.com/v1
export LLM_PROVIDER=anthropic LLM_MODEL=<claude model>   # uses Anthropic API

python main.py --no-llm      # baseline, no key needed
```

## Assumptions
- Timestamps are in seconds as `mm:ss.ff`; if a new scene restarts at 00:00 it is added after the previous scene.
- Only the screenplay is used (no video), so "hook" is judged from text.

## Limits
- LLM scores are opinions; a human should review the top 10-15.
- The tool cannot see acting, music or visuals.
- Standalone clarity is the weakest check (the LLM is the only judge of it).
