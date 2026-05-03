# Ripple

Ripple watches what people are actually talking about in your niche right now, then writes scored, platform-ready social posts for you to review and publish. No templates, no generic copy. Everything starts from real trending conversations on Reddit, HackerNews, and Google.

---

## How it works

Six AI agents run in sequence. The first finds what is trending in your niche today. The second figures out the emotional undercurrent driving those conversations. The third translates that into platform-specific content angles. The fourth writes the actual posts with hooks, bodies, and hashtags. The fifth sharpens anything that sounds weak or corporate. The sixth scores every piece from 0 to 100 and flags your top picks.

After you post and get real engagement data, you upload a CSV and Ripple stores it locally. Every future run uses that memory to score more accurately for your specific audience.

---

## Stack

Everything here runs on free tiers. No credit card required for the first month (and far beyond for personal use).

| Layer | What |
|---|---|
| Agents | CrewAI |
| LLM | Google Gemini 1.5 Flash (free: 1500 req/day) |
| Embeddings | sentence-transformers, runs locally |
| Vector memory | ChromaDB, stored on disk |
| Trend sources | Reddit, HackerNews, Serper/Google |
| UI | Streamlit |
| API | FastAPI |

---

## Setup

**Step 1.** Clone and create the virtual environment:

```bash
git clone https://github.com/YOUR_USERNAME/ripple.git
cd ripple
uv venv --python 3.12
source .venv/bin/activate
uv pip install pip
uv pip install -r requirements.txt
```

**Step 2.** Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

You need two keys to get started:

- `GEMINI_API_KEY` from [aistudio.google.com](https://aistudio.google.com) (free, no credit card)
- `SERPER_API_KEY` from [serper.dev](https://serper.dev) (2500 free queries per month)

Reddit credentials are optional but give richer trend data. Get them at [reddit.com/prefs/apps](https://reddit.com/prefs/apps) by creating a script app.

**Step 3.** Launch:

```bash
streamlit run ui/app.py
```

Or use the CLI:

```bash
python main.py run "AI productivity tools for students" --platforms twitter,linkedin --angles 3
```

---

## Project structure

```
ripple/
  core/           config models, pipeline orchestrator
  agents/         CrewAI runner + agent/task YAML configs
  tools/          Reddit, HackerNews, Serper, memory query tools
  memory/         ChromaDB client + CSV performance ingestion
  api/            FastAPI server and routes
  ui/             Streamlit dashboard
  outputs/        generated run results (JSON, git-ignored)
  main.py         CLI entry point
```

---

## Closing the learning loop

After publishing your posts, collect their engagement metrics (likes, shares, comments) and upload them:

```bash
python main.py ingest my_results.csv
```

Your CSV needs these columns: `content_id`, `text`, `platform`, `niche`, `likes`, `shares`, `comments`. Ripple scores future content based on what actually worked for your audience, not just general heuristics.

---

## API

If you prefer to integrate Ripple into another tool, start the API server:

```bash
uvicorn api.server:app --reload --port 8000
```

Key endpoints:

```
POST /runs/          run the pipeline, returns all generated content
GET  /runs/          list past runs
GET  /runs/{id}      retrieve a specific run
POST /memory/ingest  upload a performance CSV
GET  /health         service status
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit conventions, and PR expectations.
