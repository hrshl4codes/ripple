# Ripple

Ripple is a trend-driven social content generator. It runs a 6-agent CrewAI pipeline that researches what is trending in a given niche (Reddit, HackerNews, Serper/Google), generates scored content for Twitter, LinkedIn, and Instagram, and learns over time via a local ChromaDB vector database.

---

## Project Layout

```
Ripple/
├── main.py                  CLI entry point (typer)
├── ui/app.py                Streamlit UI (primary interface)
├── core/
│   ├── config.py            RunConfig, RunResult, ContentPiece, Settings, PLATFORM_LIMITS
│   └── pipeline.py          run(), load_result(), list_runs()
├── agents/
│   ├── crew_runner.py       CrewAI orchestration, agent + task wiring, output parser
│   └── config/
│       ├── agents.yaml      Agent role/goal/backstory definitions
│       └── tasks.yaml       Task descriptions and expected outputs
├── tools/
│   ├── reddit_tool.py       Reddit (PRAW) + HackerNews fallback
│   ├── hackernews_tool.py   HackerNews Algolia API
│   ├── search_tool.py       Serper (Google Search)
│   └── memory_tool.py       ChromaDB semantic similarity lookup
├── memory/
│   ├── chroma_client.py     ChromaDB client, sentence-transformers embeddings
│   └── ingest.py            CSV ingestion for real engagement data
├── api/
│   ├── server.py            FastAPI app
│   └── routes/
│       ├── runs.py          POST /runs, GET /runs, GET /runs/{id}
│       └── memory.py        POST /memory/ingest
└── outputs/                 JSON run results (auto-created)
```

---

## Key Design Decisions

**LLM:** Gemini 1.5 Flash via LiteLLM (`gemini/gemini-1.5-flash`). Free tier: 1500 req/day, 1M tokens/day. Set with `GEMINI_API_KEY`.

**Embeddings:** sentence-transformers `all-MiniLM-L6-v2` running locally via chromadb's `SentenceTransformerEmbeddingFunction`. No API cost, no key required.

**Agent pipeline:** Sequential CrewAI process. Tasks pass context forward explicitly (each task receives relevant prior task outputs as context). `allow_delegation=False` on all agents to prevent unexpected routing.

**Output parsing:** `_parse_output_to_pieces()` in `crew_runner.py` does best-effort block parsing keyed on `PLATFORM | ANGLE | VARIATION` label lines. Falls back to a raw dump if parsing fails. This is intentionally lenient because LLM output formatting is unpredictable.

**Character limits:** Enforced at parse time in `_build_piece()`. Body is truncated at word boundary if over limit. Limits live in `PLATFORM_LIMITS` in `core/config.py`.

**Memory learning:** After posting, user uploads a CSV with columns `content_id, text, platform, niche, likes, shares, comments`. Engagement score = `likes + 5*shares + 2*comments`. Stored in ChromaDB. The Performance Analyst agent queries this on every run.

---

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Get free at aistudio.google.com |
| `SERPER_API_KEY` | Yes | Get free at serper.dev (2500/month) |
| `REDDIT_CLIENT_ID` | No | Better trend data; app-only auth |
| `REDDIT_CLIENT_SECRET` | No | Pairs with CLIENT_ID |
| `CHROMA_PERSIST_DIR` | No | Defaults to `./memory/performance_db` |
| `OUTPUTS_DIR` | No | Defaults to `./outputs` |

Copy `.env.example` to `.env` and fill in keys.

---

## Running the Project

```bash
cd ~/Projects/Ripple

# Install deps (first time only)
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Launch UI
streamlit run ui/app.py

# Or use CLI
python main.py run "AI productivity tools" --platforms twitter,linkedin --angles 3
python main.py ui          # also launches the UI
python main.py runs        # list past runs
python main.py ingest path/to/results.csv

# API server
uvicorn api.server:app --reload --port 8000
```

---

## What to Work On Next

Things that are not yet built but are planned:

1. Score breakdown parsing: the Performance Analyst returns scores as text but `_parse_output_to_pieces()` does not yet extract per-dimension scores into `score_breakdown`. Needs a regex or structured output pass.

2. Streaming: currently the UI shows a spinner until all 6 agents complete. Adding `st.write_stream` with CrewAI callbacks would let users see each agent's output as it arrives.

3. Deduplication: before writing a new piece, query ChromaDB and skip if cosine similarity is above 0.92 with any past post. Prevents the model from regenerating very similar content over time.

4. Reddit credentials flow: currently the app silently falls back to HackerNews if Reddit keys are missing. A better UX would be a settings page in the UI that validates credentials on save.

5. Post scheduling: add a `scheduled_for` field to `ContentPiece` and a simple calendar view in the UI showing which posts are lined up for which day.

---

## Pitfalls

Agent YAML formatting is sensitive. Jinja-style `{variable}` interpolation happens in `crew_runner.py` via Python `.format()` on the description/goal strings. If a YAML value contains a literal `{` for any other reason it will break. Escape with `{{`.

The `SentenceTransformerEmbeddingFunction` downloads the model on first run (~90MB). Subsequent runs are instant.

If `GEMINI_API_KEY` is missing or invalid, CrewAI raises a generic LiteLLM error with no helpful message. Check the key first before debugging agents.
