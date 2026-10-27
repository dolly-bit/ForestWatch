"""Settings read from environment variables (see .env.example)."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    root_dir: Path            # folder that contains data/stacks and models/
    config_path: Path
    model_path: Path
    sync_jobs: bool           # run jobs inline (no Redis): for tests / quick local dev
    auto_create_tables: bool  # create tables without Alembic: for tests only
    cors_origins: list[str]


def get_settings() -> Settings:
    root = Path(os.getenv("ROOT_DIR", REPO_ROOT))
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{root / 'forestwatch.db'}"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        root_dir=root,
        config_path=Path(os.getenv("CONFIG_PATH", root / "configs" / "aravalli.yaml")),
        model_path=Path(os.getenv("MODEL_PATH", root / "models" / "unet_change.pt")),
        sync_jobs=os.getenv("SYNC_JOBS", "0") == "1",
        auto_create_tables=os.getenv("AUTO_CREATE_TABLES", "0") == "1",
        cors_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()],
    )
