from __future__ import annotations
from fastapi import FastAPI
from api.routes import runs, memory

app = FastAPI(title="Ripple API", version="1.0.0")
app.include_router(runs.router)
app.include_router(memory.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
