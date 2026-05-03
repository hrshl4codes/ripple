from __future__ import annotations
import os
import time
from pathlib import Path
from crewai import Agent, Crew, Task, LLM, Process
import yaml

from core.config import RunConfig, RunResult, ContentPiece, PLATFORM_LIMITS
from tools.reddit_tool import RedditTrendTool
from tools.hackernews_tool import HackerNewsTool
from tools.search_tool import SerperSearchTool
from tools.memory_tool import MemoryQueryTool


_CONFIG_DIR = Path(__file__).parent / "config"


def _load_yaml(filename: str) -> dict:
    with open(_CONFIG_DIR / filename) as f:
        return yaml.safe_load(f)


def _make_llm() -> LLM:
    return LLM(
        model=os.getenv("GEMINI_MODEL", "gemini/gemini-1.5-flash"),
        api_key=os.getenv("GEMINI_API_KEY", ""),
        temperature=0.7,
    )


def _parse_output_to_pieces(raw: str, config: RunConfig) -> list[ContentPiece]:
    """
    Best-effort parser: extracts labelled content blocks from the crew's final output.
    Falls back to a single piece with the full text if parsing fails.
    """
    pieces: list[ContentPiece] = []
    blocks = raw.strip().split("\n\n")
    current: dict = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current.get("body"):
                pieces.append(_build_piece(current, config))
                current = {}
            continue

        lower = line.lower()
        if any(p in lower for p in ["twitter", "linkedin", "instagram"]) and "|" in line:
            if current.get("body"):
                pieces.append(_build_piece(current, config))
            parts = [p.strip() for p in line.split("|")]
            current = {
                "platform": next((p for p in ["twitter", "linkedin", "instagram"] if p in lower), "twitter"),
                "angle": parts[1] if len(parts) > 1 else "general",
                "variation": parts[2] if len(parts) > 2 else "1",
                "hook": "",
                "body": "",
                "hashtags": [],
            }
        elif current and not current.get("hook"):
            current["hook"] = line
        elif current and line.startswith("#"):
            current["hashtags"] = [w.lstrip("#") for w in line.split() if w.startswith("#")]
        elif current:
            current["body"] = (current.get("body", "") + " " + line).strip()

    if current.get("body") or current.get("hook"):
        pieces.append(_build_piece(current, config))

    if not pieces:
        for platform in config.platforms:
            pieces.append(ContentPiece(
                platform=platform,
                angle="general",
                hook=raw[:100],
                body=raw[100:500],
                hashtags=[],
                char_count=min(len(raw), PLATFORM_LIMITS.get(platform, 280)),
                score=50.0,
            ))

    return pieces


def _build_piece(data: dict, config: RunConfig) -> ContentPiece:
    platform = data.get("platform", config.platforms[0])
    limit = PLATFORM_LIMITS.get(platform, 280)
    body = data.get("body", "")
    hook = data.get("hook", "")
    hashtags = data.get("hashtags", [])

    full = f"{hook}\n\n{body}".strip()
    if len(full) > limit:
        body = body[: limit - len(hook) - 10].rsplit(" ", 1)[0] + "..."

    return ContentPiece(
        platform=platform,
        angle=data.get("angle", "general"),
        hook=hook,
        body=body,
        hashtags=hashtags[:5],
        char_count=len(full),
        score=0.0,
    )


def run_crew(config: RunConfig) -> RunResult:
    start = time.time()
    llm = _make_llm()

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

    def make_task(key: str, agent: Agent, context=None) -> Task:
        cfg = tasks_cfg[key]
        return Task(
            description=cfg["description"].format(
                niche=config.niche,
                platforms=", ".join(config.platforms),
                angles=config.angles,
                variations=config.variations,
            ),
            expected_output=cfg["expected_output"].format(
                angles=config.angles,
                variations=config.variations,
            ),
            agent=agent,
            context=context or [],
        )

    t_research = make_task("trend_research", trend_hunter)
    t_audience = make_task("audience_analysis", psychologist, [t_research])
    t_strategy = make_task("content_strategy", strategist, [t_research, t_audience])
    t_copy = make_task("copywriting", copywriter, [t_strategy, t_audience])
    t_review = make_task("creative_review", director, [t_copy])
    t_score = make_task("scoring", analyst, [t_review])

    crew = Crew(
        agents=[trend_hunter, psychologist, strategist, copywriter, director, analyst],
        tasks=[t_research, t_audience, t_strategy, t_copy, t_review, t_score],
        process=Process.sequential,
        verbose=False,
    )

    try:
        result = crew.kickoff()
        raw_output = str(result)
        pieces = _parse_output_to_pieces(raw_output, config)

        pieces.sort(key=lambda p: p.score, reverse=True)
        for i, piece in enumerate(pieces[:10]):
            piece.recommended = True

        trends_found: list[str] = []
        if t_research.output:
            for line in str(t_research.output).splitlines():
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    trends_found.append(line.lstrip("0123456789.-) "))

        return RunResult(
            run_id=config.run_id,
            niche=config.niche,
            platforms=config.platforms,
            pieces=pieces,
            trends_found=trends_found[:10],
            duration_seconds=round(time.time() - start, 1),
        )

    except Exception as e:
        return RunResult(
            run_id=config.run_id,
            niche=config.niche,
            platforms=config.platforms,
            error=str(e),
            duration_seconds=round(time.time() - start, 1),
        )
