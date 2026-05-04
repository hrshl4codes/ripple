from __future__ import annotations
import os
import re
import time
from pathlib import Path
from crewai import Agent, Crew, Task, LLM, Process
from pydantic import BaseModel, Field
import yaml

from core.config import RunConfig, RunResult, ContentPiece, PLATFORM_LIMITS
from tools.reddit_tool import RedditTrendTool
from tools.hackernews_tool import HackerNewsTool
from tools.search_tool import SerperSearchTool
from tools.memory_tool import MemoryQueryTool


_CONFIG_DIR = Path(__file__).parent / "config"

# Tried in order when a model hits its quota. All are free-tier Gemini models.
_FALLBACK_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]


def _is_quota_error(exc: Exception) -> bool:
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


def _is_daily_limit(exc: Exception) -> bool:
    return "PerDay" in str(exc) or "per_day" in str(exc).lower()


def _retry_delay(exc: Exception) -> float:
    match = re.search(r"retry in (\d+\.?\d*)", str(exc), re.IGNORECASE)
    return float(match.group(1)) + 3 if match else 20.0


# ── Structured output models for agent tasks ─────────────────────────────────

class RawPiece(BaseModel):
    platform: str
    angle: str
    hook: str
    body: str
    hashtags: list[str] = Field(default_factory=list)
    # YouTube Shorts only — empty string for other platforms
    title: str = ""
    thumbnail_text: str = ""
    cta: str = ""

class CopywriterOutput(BaseModel):
    pieces: list[RawPiece]

class ScoredPiece(BaseModel):
    platform: str
    angle: str
    hook: str
    body: str
    hashtags: list[str] = Field(default_factory=list)
    title: str = ""
    thumbnail_text: str = ""
    cta: str = ""
    score: float = Field(ge=0, le=100)
    scroll_stop: float = Field(ge=0, le=30)
    emotional_resonance: float = Field(ge=0, le=25)
    platform_fit: float = Field(ge=0, le=20)
    clarity: float = Field(ge=0, le=15)
    originality: float = Field(ge=0, le=10)
    recommended: bool = False

class AnalystOutput(BaseModel):
    pieces: list[ScoredPiece]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_yaml(filename: str) -> dict:
    with open(_CONFIG_DIR / filename) as f:
        return yaml.safe_load(f)


def _make_llm(model: str | None = None) -> LLM:
    return LLM(
        model=model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        api_key=os.getenv("GEMINI_API_KEY", ""),
        temperature=0.7,
    )


def _enforce_limits(piece: RawPiece | ScoredPiece, platform: str) -> tuple[str, str, int]:
    limit = PLATFORM_LIMITS.get(platform, 280)
    hook = piece.hook.strip()
    body = piece.body.strip()
    tags = " ".join(f"#{t.lstrip('#')}" for t in piece.hashtags[:5])
    full = f"{hook}\n\n{body}\n\n{tags}".strip() if tags else f"{hook}\n\n{body}".strip()
    if len(full) > limit:
        available = limit - len(hook) - (len(tags) + 4 if tags else 0) - 6
        body = body[:max(0, available)].rsplit(" ", 1)[0].rstrip() + "..."
        full = f"{hook}\n\n{body}\n\n{tags}".strip() if tags else f"{hook}\n\n{body}".strip()
    return hook, body, len(full)


def _pieces_from_structured(output: AnalystOutput | CopywriterOutput, config: RunConfig) -> list[ContentPiece]:
    pieces = []
    raw_list = output.pieces

    for i, raw in enumerate(raw_list):
        platform = raw.platform.lower().strip()
        if platform not in PLATFORM_LIMITS:
            platform = config.platforms[0]

        hook, body, char_count = _enforce_limits(raw, platform)

        score = 0.0
        breakdown: dict[str, float] = {}
        recommended = False
        if isinstance(raw, ScoredPiece):
            score = raw.score
            breakdown = {
                "scroll_stop": raw.scroll_stop,
                "emotional_resonance": raw.emotional_resonance,
                "platform_fit": raw.platform_fit,
                "clarity": raw.clarity,
                "originality": raw.originality,
            }
            recommended = raw.recommended

        pieces.append(ContentPiece(
            platform=platform,
            angle=raw.angle[:60],
            hook=hook,
            body=body,
            hashtags=[t.lstrip("#") for t in raw.hashtags[:5]],
            char_count=char_count,
            score=score,
            score_breakdown=breakdown,
            recommended=recommended,
            variation_index=i,
            title=getattr(raw, "title", "") or "",
            thumbnail_text=getattr(raw, "thumbnail_text", "") or "",
            cta=getattr(raw, "cta", "") or "",
        ))

    return pieces


def _extract_trends(task_output) -> list[str]:
    if not task_output:
        return []
    trends = []
    for line in str(task_output).splitlines():
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith(("*", "-", "•"))):
            cleaned = line.lstrip("0123456789.*-•) ").strip()
            if len(cleaned) > 10:
                trends.append(cleaned)
    return trends[:10]


# ── Main runner ───────────────────────────────────────────────────────────────

def run_crew(config: RunConfig, status_callback=None) -> RunResult:
    start = time.time()

    preferred = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    model_queue = [preferred] + [m for m in _FALLBACK_MODELS if m != preferred]

    last_error: Exception | None = None

    for model in model_queue:
        try:
            return _run_with_model(config, model, start, status_callback)
        except Exception as exc:
            last_error = exc
            if not _is_quota_error(exc):
                break
            if _is_daily_limit(exc):
                continue
            wait = _retry_delay(exc)
            time.sleep(wait)
            try:
                return _run_with_model(config, model, start, status_callback)
            except Exception as retry_exc:
                last_error = retry_exc
                if _is_quota_error(retry_exc):
                    continue
                break

    return RunResult(
        run_id=config.run_id,
        niche=config.niche,
        platforms=config.platforms,
        error=(
            "All Gemini models have hit their free-tier daily quota. "
            "Try again tomorrow, or add billing to your Google AI Studio project. "
            f"Last error: {last_error}"
        ),
        duration_seconds=round(time.time() - start, 1),
    )


def _run_with_model(config: RunConfig, model: str, start: float, status_callback=None) -> RunResult:
    llm = _make_llm(model)
    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")

    shared_tools = [
        RedditTrendTool(niche=config.niche, subreddits=config.subreddits),
        HackerNewsTool(),
        SerperSearchTool(),
    ]
    memory_tool = MemoryQueryTool(top_k=config.top_k_memory)

    def make_agent(key: str, tools=None) -> Agent:
        cfg = agents_cfg[key]
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"].format(
                niche=config.niche,
                platforms=", ".join(config.platforms),
                angles=config.angles,
                variations=config.variations,
            ),
            backstory=cfg["backstory"],
            llm=llm,
            tools=tools or [],
            verbose=False,
            allow_delegation=False,
        )

    trend_hunter = make_agent("trend_hunter", shared_tools)
    psychologist = make_agent("audience_psychologist")
    strategist = make_agent("content_strategist")
    copywriter = make_agent("copywriter")
    director = make_agent("creative_director")
    analyst = make_agent("performance_analyst", [memory_tool])

    fmt = dict(
        niche=config.niche,
        platforms=", ".join(config.platforms),
        angles=config.angles,
        variations=config.variations,
    )

    def make_task(key: str, agent: Agent, context=None, output_pydantic=None) -> Task:
        cfg = tasks_cfg[key]
        kwargs = dict(
            description=cfg["description"].format(**fmt),
            expected_output=cfg["expected_output"].format(**fmt),
            agent=agent,
            context=context or [],
        )
        if output_pydantic:
            kwargs["output_pydantic"] = output_pydantic
        return Task(**kwargs)

    t_research = make_task("trend_research", trend_hunter)
    t_audience = make_task("audience_analysis", psychologist, [t_research])
    t_strategy = make_task("content_strategy", strategist, [t_research, t_audience])
    t_copy = make_task("copywriting", copywriter, [t_strategy, t_audience], CopywriterOutput)
    t_review = make_task("creative_review", director, [t_copy])
    t_score = make_task("scoring", analyst, [t_review, t_copy], AnalystOutput)

    def _on_task_done(task_output) -> None:
        if status_callback:
            role = getattr(task_output, "agent", "") or ""
            status_callback(str(role), str(getattr(task_output, "raw", "") or "")[:120])

    crew = Crew(
        agents=[trend_hunter, psychologist, strategist, copywriter, director, analyst],
        tasks=[t_research, t_audience, t_strategy, t_copy, t_review, t_score],
        process=Process.sequential,
        task_callback=_on_task_done,
        verbose=False,
    )

    crew.kickoff()

    pieces: list[ContentPiece] = []

    if t_score.output and hasattr(t_score.output, "pydantic") and t_score.output.pydantic:
        pieces = _pieces_from_structured(t_score.output.pydantic, config)
    elif t_copy.output and hasattr(t_copy.output, "pydantic") and t_copy.output.pydantic:
        pieces = _pieces_from_structured(t_copy.output.pydantic, config)

    if not pieces and t_review.output:
        pieces = _parse_raw_fallback(str(t_review.output), config)

    pieces.sort(key=lambda p: p.score, reverse=True)
    for piece in pieces[:10]:
        piece.recommended = True

    return RunResult(
        run_id=config.run_id,
        niche=config.niche,
        platforms=config.platforms,
        pieces=pieces,
        trends_found=_extract_trends(t_research.output),
        duration_seconds=round(time.time() - start, 1),
    )


def _parse_raw_fallback(raw: str, config: RunConfig) -> list[ContentPiece]:
    """Last-resort parser when structured output is unavailable."""
    pieces: list[ContentPiece] = []
    current: dict = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current.get("hook"):
                pieces.append(_build_piece_from_dict(current, config))
                current = {}
            continue

        lower = line.lower()
        is_header = any(p in lower for p in ["twitter", "linkedin", "instagram"])

        if is_header:
            if current.get("hook"):
                pieces.append(_build_piece_from_dict(current, config))
            platform = next((p for p in ["twitter", "linkedin", "instagram"] if p in lower), config.platforms[0])
            parts = [p.strip() for p in line.split("|")]
            current = {
                "platform": platform,
                "angle": parts[1] if len(parts) > 1 else "general",
                "hook": "",
                "body": "",
                "hashtags": [],
            }
        elif current and not current.get("hook") and len(line) > 5:
            current["hook"] = line
        elif current and all(w.startswith("#") for w in line.split() if w):
            current["hashtags"] = [w.lstrip("#") for w in line.split()]
        elif current:
            current["body"] = (current.get("body", "") + " " + line).strip()

    if current.get("hook"):
        pieces.append(_build_piece_from_dict(current, config))

    return pieces


def _build_piece_from_dict(data: dict, config: RunConfig) -> ContentPiece:
    platform = data.get("platform", config.platforms[0])
    hook, body, char_count = _enforce_limits(
        type("_", (), {"hook": data.get("hook", ""), "body": data.get("body", ""), "hashtags": data.get("hashtags", [])})(),
        platform,
    )
    return ContentPiece(
        platform=platform,
        angle=data.get("angle", "general"),
        hook=hook,
        body=body,
        hashtags=data.get("hashtags", [])[:5],
        char_count=char_count,
        score=0.0,
    )
