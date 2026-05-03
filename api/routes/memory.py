from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException
import tempfile, os
from memory.ingest import ingest_csv

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/ingest")
def ingest_performance(file: UploadFile = File(...)) -> dict:
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        stats = ingest_csv(tmp_path)
    finally:
        os.unlink(tmp_path)
    return {"status": "ok", **stats}
