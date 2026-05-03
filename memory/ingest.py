from __future__ import annotations
import pandas as pd
from memory.chroma_client import upsert_content


REQUIRED_COLUMNS = {"content_id", "text", "platform", "niche", "likes", "shares", "comments"}


def ingest_csv(path: str) -> dict[str, int]:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    updated = 0
    skipped = 0
    for _, row in df.iterrows():
        try:
            engagement = int(row["likes"]) + 5 * int(row["shares"]) + 2 * int(row["comments"])
            upsert_content(
                content_id=str(row["content_id"]),
                text=str(row["text"]),
                platform=str(row["platform"]),
                niche=str(row["niche"]),
                predicted_score=float(row.get("predicted_score", 0)),
                engagement_score=float(engagement),
            )
            updated += 1
        except Exception:
            skipped += 1

    return {"updated": updated, "skipped": skipped}
