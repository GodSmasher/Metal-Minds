# pacemaker.ai prototype

An end-to-end hackathon prototype for explainable commodity procurement decisions using LME-style price history and GDELT-style news.

## What it includes
- Pure Python ingestion and signal pipeline with no external dependencies
- Explainable decision engine for `Buy now`, `Wait`, `Stay lean`, and hedging-oriented guidance
- Static decision cockpit UI served by a local HTTP server
- Sample LME and GDELT CSVs so the demo works immediately
- API endpoints aligned to the hackathon plan

## Project layout
- `app.py`: local server and JSON API
- `pacemaker/`: ingestion, features, news clustering, event-study logic, and decision engine
- `static/`: cockpit UI
- `data/lme/` and `data/gdelt/`: drop real challenge CSVs here
- `tests/`: lightweight validation

## Run locally
```bash
python3 app.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## API
- `GET /api/metals`
- `GET /api/decision?metal=copper&horizon=10d`
- `GET /api/news-clusters?metal=copper`
- `GET /api/analog-events?metal=copper&theme=supply%20disruption`
- `GET /api/scenarios?metal=copper&horizon=10d`
- `GET /api/refresh`

## Data expectations

### LME CSV
Expected columns:
- `date`
- `metal` or `commodity`
- `price` or `close`

### GDELT CSV
Expected columns:
- `date`
- `title`
- `source`
- `region` or `location`
- `tone`
- `body`, `text`, or `summary`

## Pipeline summary
1. Normalize raw CSVs into canonical price and news records.
2. Compute rolling price features, regime labels, and anomaly flags.
3. Deduplicate and cluster news by date, metal tags, and theme.
4. Estimate event impacts with simple historical follow-through logic.
5. Convert price, news, and analog evidence into a procurement recommendation.

## Notes
- The current news clustering and summarization layers are heuristic to stay dependency-free.
- The architecture is intentionally modular so you can later swap in embeddings, real LLM summaries, or stronger models.
