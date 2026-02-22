from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class AppConfig:
    openai_api_key: str | None
    x_api_bearer_token: str | None
    x_source_accounts: list[str]
    x_filter_tags: list[str]
    x_filter_keywords: list[str]
    data_dir: Path
    log_level: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            x_api_bearer_token=os.getenv("X_API_BEARER_TOKEN"),
            x_source_accounts=_split_csv(os.getenv("X_SOURCE_ACCOUNTS", "")),
            x_filter_tags=_split_csv(os.getenv("X_FILTER_TAGS", "")),
            x_filter_keywords=_split_csv(os.getenv("X_FILTER_KEYWORDS", "")),
            data_dir=data_dir,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
