from __future__ import annotations
import uuid
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


Platform = Literal["twitter", "linkedin", "instagram"]

PLATFORM_LIMITS = {
    "twitter": 280,
    "linkedin": 3000,
    "instagram": 2200,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    serper_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "Ripple/1.0"
    chroma_persist_dir: str = "./memory/performance_db"
    outputs_dir: str = "./outputs"
    gemini_model: str = "gemini-2.5-flash-lite"


class RunConfig(BaseModel):
    niche: str = Field(..., min_length=2, max_length=200)
    subreddits: list[str] = Field(default_factory=list)
    platforms: list[Platform] = Field(default=["twitter", "linkedin"])
    angles: int = Field(default=3, ge=1, le=10)
    variations: int = Field(default=2, ge=1, le=5)
    top_k_memory: int = Field(default=5, ge=1, le=20)
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])

    @field_validator("subreddits", mode="before")
    @classmethod
    def default_subreddits(cls, v: list[str], info) -> list[str]:
        return v if v else []

    @field_validator("platforms", mode="before")
    @classmethod
    def validate_platforms(cls, v: list[str]) -> list[Platform]:
        valid = set(PLATFORM_LIMITS.keys())
        for p in v:
            if p not in valid:
                raise ValueError(f"Platform must be one of {valid}")
        return v


class ContentPiece(BaseModel):
    platform: Platform
    angle: str
    hook: str
    body: str
    hashtags: list[str] = Field(default_factory=list)
    char_count: int = 0
    score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    recommended: bool = False
    variation_index: int = 0

    def full_text(self) -> str:
        tags = " ".join(f"#{t.lstrip('#')}" for t in self.hashtags)
        parts = [self.hook, self.body]
        if tags:
            parts.append(tags)
        return "\n\n".join(p for p in parts if p)


class RunResult(BaseModel):
    run_id: str
    niche: str
    platforms: list[Platform]
    pieces: list[ContentPiece] = Field(default_factory=list)
    trends_found: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    duration_seconds: float = 0.0
    error: str | None = None
