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

# Install deps (first time only — uses uv-managed Python 3.12)
uv venv --python 3.12 --clear
source .venv/bin/activate
uv pip install pip
uv pip install -r requirements.txt

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

Use imperative mood in the subject ("add" not "added"). No period at the end. Body wraps at 72 characters. Breaking changes use `!` after type: `feat(api)!: rename endpoint`.

Good examples:
```
feat(agents): add parallel execution for psychologist and strategist tasks
fix(parser): handle missing platform label in crew output
chore: bump crewai to 0.131.0
docs: document CSV ingest format in README
```

### Pull requests

Keep PRs under 400 lines. Review quality drops sharply above that — split large features into sequential PRs instead.

Every PR description answers: what changed, why it was needed, how to verify it. Open as draft early for complex work.

### Releases and tagging

Semantic versioning: `vMAJOR.MINOR.PATCH`

```
PATCH   bug fix, no new features     v1.0.1
MINOR   new feature, backwards compat v1.1.0
MAJOR   breaking change               v2.0.0
```

Always use annotated tags (not lightweight):
```bash
git tag -a v1.0.0 -m "v1.0.0: initial release"
git push origin v1.0.0
```

Create a GitHub Release for every tag. The release body is the changelog for that version.

### Creating a new GitHub repo from scratch

```bash
cd ~/Projects/Ripple

# 1. init and first commit already done — skip if repo exists
git init
git add -A
git commit -m "feat: initial project scaffold"

# 2. create remote repo (gh CLI)
gh repo create ripple --public --description "Trend-driven social content generator" --source=. --remote=origin --push

# 3. tag the initial release
git tag -a v0.1.0 -m "v0.1.0: initial release"
git push origin v0.1.0

# 4. create a GitHub release
gh release create v0.1.0 --title "v0.1.0: Initial release" --notes "First working version of the Ripple pipeline."

# 5. protect main branch (requires repo admin)
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field enforce_admins=false
```

### Day-to-day push workflow

```bash
# Start work
git checkout -b feature/your-feature-name

# Commit as you go
git add path/to/changed/files
git commit -m "feat(scope): description"

# Keep branch current
git fetch origin
git rebase origin/main

# Push and open PR
git push -u origin feature/your-feature-name
gh pr create --title "feat: your feature" --body "What, why, how to test"

# After merge, clean up
git checkout main
git pull origin main
git branch -d feature/your-feature-name
```

### What never goes in a commit

`.env` files, credentials, API keys, large binaries, build artifacts, `__pycache__`, `.venv`. All covered in `.gitignore`. If a secret is accidentally committed, rotate the key immediately — do not just delete the file in a new commit, as it remains in history.
