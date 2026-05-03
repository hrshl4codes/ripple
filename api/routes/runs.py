from __future__ import annotations
from fastapi import APIRouter, HTTPException
from core.config import RunConfig, RunResult
from core import pipeline

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/", response_model=RunResult)
def create_run(config: RunConfig) -> RunResult:
    return pipeline.run(config)


@router.get("/", response_model=list[dict])
def list_runs() -> list[dict]:
    return pipeline.list_runs()


@router.get("/{run_id}", response_model=RunResult)
def get_run(run_id: str) -> RunResult:
    result = pipeline.load_result(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result
