# Ripple

Ripple is a trend-driven social content generator. It runs a 6-agent CrewAI pipeline that researches what is trending in a given niche (Reddit, HackerNews, Serper/Google), generates scored content for Twitter, LinkedIn, Instagram, and YouTube Shorts, and learns over time via a local ChromaDB vector database.

GitHub repo: https://github.com/hrshl4codes/ripple

---

## Current State (as of May 2026)

Everything below is built and working.

**Core pipeline**
6 CrewAI agents run sequentially: Trend Hunter, Audience Psychologist, Content Strategist, Copywriter, Creative Director, Performance Analyst. Output comes back as structured Pydantic models (not free text), so parsing is reliable.

**Platforms supported**
Twitter (280 chars), LinkedIn (3000 chars), Instagram (2200 chars), YouTube Shorts (structured 60-second script with hook, body, CTA, title, thumbnail text).

**Trend sources**
Reddit (via PRAW, requires credentials), HackerNews Algolia API (free, no auth, used as fallback), Serper/Google Search.

**Memory loop**
ChromaDB with sentence-transformers `all-MiniLM-L6-v2` embeddings running locally. After posting, user uploads a CSV with engagement data. Future runs use past performance to bias scoring.

**UI**
Streamlit at `ui/app.py`. Live agent streaming via `st.status()` — shows each agent completing in real time instead of a blank spinner. Reddit credentials can be entered and tested directly from the sidebar without touching `.env`. Shorts pieces render as structured script cards (Hook / Script / CTA sections). Past runs visible in sidebar. CSV export on every run.

**Model fallback chain**
When a Gemini model hits its free-tier daily quota (429), the runner automatically tries the next model in this order:
`gemini-2.5-flash-lite → gemini-2.5-flash → gemini-2.0-flash → gemini-2.0-flash-lite → gemini-flash-lite-latest → gemini-flash-latest`

**GitHub**
Conventional Commits on all commits. Annotated tags for releases. v0.1.0 released. See the GitHub Workflow Standards section below for the full process.

---

## Project Layout

```
Ripple/
├── main.py                  CLI entry point (typer)
├── ui/
│   ├── app.py               Streamlit UI (primary interface)
│   └── assets/ripple.png    Logo
├── core/
│   ├── config.py            RunConfig, RunResult, ContentPiece, Settings,
│   │                        PLATFORM_LIMITS, SHORTS_PLATFORM
│   └── pipeline.py          run(config, status_callback), load_result(), list_runs()
├── agents/
│   ├── crew_runner.py       CrewAI orchestration, Pydantic output models,
│   │                        model fallback chain, task_callback wiring
│   └── config/
│       ├── agents.yaml      Agent role/goal/backstory definitions
│       └── tasks.yaml       Task descriptions and expected JSON output schemas
├── tools/
│   ├── reddit_tool.py       Reddit (PRAW) with HackerNews fallback
│   ├── hackernews_tool.py   HackerNews Algolia API (free, no auth)
│   ├── search_tool.py       Serper (Google Search)
│   └── memory_tool.py       ChromaDB semantic similarity lookup
├── memory/
│   ├── chroma_client.py     ChromaDB client, sentence-transformers embeddings
│   └── ingest.py            CSV performance ingestion
├── api/
│   ├── server.py            FastAPI app
│   └── routes/
│       ├── runs.py          POST /runs, GET /runs, GET /runs/{id}
│       └── memory.py        POST /memory/ingest
└── outputs/                 JSON run results (auto-created, git-ignored)
```

---

## Key Design Decisions

**LLM:** Gemini 2.5 Flash Lite via CrewAI native provider. Default model: `gemini-2.5-flash-lite`. Overridden by `GEMINI_MODEL` env var. Free tier on Google AI Studio (new key from aistudio.google.com, not GCP console — the GCP console keys often have limit:0 on free tier models).

**Embeddings:** sentence-transformers `all-MiniLM-L6-v2` via ChromaDB's `SentenceTransformerEmbeddingFunction`. Runs locally on CPU. Downloads ~90MB on first run, instant after that. No API key or cost.

**Structured output:** Copywriter task uses `output_pydantic=CopywriterOutput`, Analyst task uses `output_pydantic=AnalystOutput`. Both defined in `crew_runner.py`. This replaced the original brittle text parser. If structured output fails, `_parse_raw_fallback()` attempts text extraction as last resort.

**YouTube Shorts fields:** `RawPiece` and `ScoredPiece` have optional `title`, `thumbnail_text`, `cta` fields. Empty string for non-Shorts platforms. `ContentPiece.full_text()` branches on `platform == SHORTS_PLATFORM` to format the script layout.

**Streaming:** `pipeline.run()` accepts an optional `status_callback(agent_role, preview)`. The UI passes a callback that puts messages onto a `queue.Queue`. A background thread runs the crew; the main thread drains the queue inside `st.status()`, updating the display as each agent finishes.

**Agent pipeline:** Sequential CrewAI process. `allow_delegation=False` on all agents. Tasks receive prior task outputs as explicit `context`. `task_callback=_on_task_done` fires after each task and calls `status_callback` if set.

**Memory learning:** Engagement score = `likes + 5*shares + 2*comments`. Stored in ChromaDB with platform and niche metadata. Performance Analyst queries on every run using `MemoryQueryTool`.

---

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Get free at aistudio.google.com (not GCP console) |
| `SERPER_API_KEY` | Yes | serper.dev — 2500 free queries/month |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.5-flash-lite` |
| `REDDIT_CLIENT_ID` | No | reddit.com/prefs/apps — create a script app |
| `REDDIT_CLIENT_SECRET` | No | Pairs with CLIENT_ID |
| `REDDIT_USER_AGENT` | No | Defaults to `Ripple/1.0` |
| `CHROMA_PERSIST_DIR` | No | Defaults to `./memory/performance_db` |
| `OUTPUTS_DIR` | No | Defaults to `./outputs` |

---

## Running the Project

```bash
cd ~/Projects/Ripple

# Install deps (first time only — uses uv-managed Python 3.12)
uv venv --python 3.12 --clear
source .venv/bin/activate
uv pip install pip
uv pip install -r requirements.txt
uv pip install google-genai   # required for CrewAI Gemini native provider

# Launch UI (primary way to use Ripple)
streamlit run ui/app.py

# CLI
python main.py run "AI productivity tools" --platforms twitter,linkedin,youtube_shorts --angles 3
python main.py runs        # list past runs
python main.py ingest path/to/results.csv

# API server
uvicorn api.server:app --reload --port 8000
```

---

## What to Build Next

These are not yet implemented, ranked by impact:

**1. Content deduplication**
Before generating, query ChromaDB for any past post with cosine similarity above 0.92. Skip generating if a near-duplicate exists. Prevents the same content from being regenerated across runs. Lives in `crew_runner.py` before the copywriting task.

**2. Post scheduling**
Add a `scheduled_for: datetime | None` field to `ContentPiece`. Add a calendar view in the UI (Streamlit has no native calendar — use `streamlit-calendar` or a simple date-grouped list) showing posts queued per day.

**3. Twitter thread generation**
When a LinkedIn-length piece is generated for Twitter, offer a thread breakdown (1/ 2/ 3/ format). Add a "Convert to thread" button in the UI that calls a lightweight agent to split it.

**4. Settings page**
A dedicated Settings tab in the UI for: entering/testing API keys (Gemini, Serper, Reddit), selecting default model, setting default platforms. Currently requires editing `.env` directly for everything except Reddit.

---

## Pitfalls

YAML task descriptions use Python `.format()` for variable interpolation. Any literal `{` in the YAML will break it. Escape with `{{`.

The `google-genai` package must be installed separately (`uv pip install google-genai`) — it is not pulled in by `crewai` automatically and its absence causes a confusing ImportError.

API keys from the GCP Console often have `limit: 0` on free-tier Gemini models. Always use keys generated from aistudio.google.com for free tier access.

If Streamlit is already running when `.env` is updated, restart the process — `load_dotenv()` runs at import time and the old values stay in memory.

---

## GitHub Workflow Standards

These are the standards followed on this project. Apply them every time you push or open a PR.

### Branch strategy

Never commit to `main` directly. Every change lives on its own branch, merged via PR.

```
feature/   new capability        e.g. feature/thread-generation
fix/       bug correction        e.g. fix/twitter-char-overflow
refactor/  structural change     e.g. refactor/memory-client
docs/      documentation only    e.g. docs/api-endpoints
chore/     tooling or config     e.g. chore/update-dependencies
perf/      performance work      e.g. perf/parallel-agents
```

Branch names: lowercase, hyphenated, under 50 characters. Branch from `main`, merge back to `main`. Delete the branch after merge.

### Commit message format (Conventional Commits)

```
<type>(<scope>): <short description under 50 chars>

[optional body — explain WHY, not what the diff shows]

[optional footer — e.g. Closes #12]
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `perf`, `test`, `ci`

Use imperative mood ("add" not "added"). No period at the end. Body wraps at 72 characters. Breaking changes use `!` after type: `feat(api)!: rename endpoint`.

### Pull requests

Keep PRs under 400 lines. Split large features into sequential PRs. Every PR description answers: what changed, why it was needed, how to verify it.

### Releases and tagging

Semantic versioning: `vMAJOR.MINOR.PATCH`

Always use annotated tags:
```bash
git tag -a v1.1.0 -m "v1.1.0: description"
git push origin v1.1.0
gh release create v1.1.0 --title "v1.1.0: description" --notes "Changelog here."
```

### Day-to-day push workflow

```bash
git checkout -b feature/your-feature-name
# make changes
git add specific/files
git commit -m "feat(scope): description"
git fetch origin && git rebase origin/main
git push -u origin feature/your-feature-name
gh pr create --title "feat: your feature" --body "What, why, how to test"
# after merge
git checkout main && git pull origin main
git branch -d feature/your-feature-name
```

### What never goes in a commit

`.env`, credentials, API keys, `__pycache__`, `.venv`, `outputs/`, `memory/performance_db/`. All in `.gitignore`. If a secret is accidentally committed, rotate the key immediately.
