from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Callable

from core.config import RunConfig, RunResult


def run(config: RunConfig, status_callback: Callable[[str, str], None] | None = None) -> RunResult:
    from agents.crew_runner import run_crew
    result = run_crew(config, status_callback=status_callback)
    _persist(result)
    return result


def _persist(result: RunResult) -> None:
    out_dir = Path(os.getenv("OUTPUTS_DIR", "./outputs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.run_id}.json"
    with open(path, "w") as f:
        json.dump(result.model_dump(), f, indent=2)


def load_result(run_id: str) -> RunResult | None:
    out_dir = Path(os.getenv("OUTPUTS_DIR", "./outputs"))
    path = out_dir / f"{run_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return RunResult.model_validate(json.load(f))


def list_runs() -> list[dict]:
    out_dir = Path(os.getenv("OUTPUTS_DIR", "./outputs"))
    if not out_dir.exists():
        return []
    runs = []
    for p in sorted(out_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p) as f:
                data = json.load(f)
            runs.append({
                "run_id": data["run_id"],
                "niche": data["niche"],
                "platforms": data["platforms"],
                "pieces": len(data.get("pieces", [])),
                "duration_seconds": data.get("duration_seconds", 0),
                "error": data.get("error"),
            })
        except Exception:
            continue
    return runs
